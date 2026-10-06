from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app import services
from app.models import Attendance, AttendanceMember, AuditLog, Bus
from app.schemas import AttendanceCreate, AttendanceSummary
from tests.helpers import (
    attendance_body, database_session, previous_attendance, sample_event, sample_operator,
    test_settings,
)


class AttendanceTests(unittest.TestCase):
    def setUp(self):
        self.db = database_session()
        self.event = sample_event()
        self.operator = sample_operator()
        self.settings = test_settings()
        self.payload = AttendanceCreate.model_validate(attendance_body())
        self.registration = SimpleNamespace(planned_companion_count=2)
        self.day = SimpleNamespace(
            event_day_id=601, event_date=date(2026, 10, 6), day_label="Martes 6 de octubre"
        )
        self.bus = SimpleNamespace(bus_id=501, bus_number=1, display_name="Bus 1")
        self.db.scalar.side_effect = [self.registration, self.day, self.bus]
        self.created = []
        self.db.add.side_effect = self.created.append

        def assign_id():
            for record in self.created:
                if isinstance(record, Attendance):
                    record.attendance_id = 401

        self.db.flush.side_effect = assign_id
        self.previous = AttendanceSummary.model_validate(previous_attendance())

    def create(self):
        return services.create_attendance(
            self.db, self.event, self.operator, self.payload, self.settings
        )

    def test_records_attendance_members_and_audit_in_one_commit(self):
        moment = datetime(2026, 10, 6, 9, 30, tzinfo=ZoneInfo("America/Bogota"))
        with patch.object(services, "attendance_summary", return_value=None), patch.object(
            services, "now_local", return_value=moment
        ):
            result = self.create()
        self.assertEqual(len(self.created), 2)
        attendance, audit = self.created
        self.assertIsInstance(attendance, Attendance)
        self.assertEqual(attendance.registered_by_user_id, self.operator.user_id)
        self.assertEqual(attendance.checked_in_at, moment.replace(tzinfo=None))
        members = self.db.add_all.call_args.args[0]
        self.assertTrue(all(isinstance(member, AttendanceMember) for member in members))
        self.assertEqual([(m.member_number, m.is_present) for m in members], [(0, True), (1, False), (2, True)])
        self.assertTrue(all(member.attendance_id == 401 for member in members))
        self.assertIsInstance(audit, AuditLog)
        self.assertEqual(audit.action, "ATTENDANCE_CREATED")
        self.assertEqual(audit.entity_type, "ATTENDANCE")
        self.assertEqual(audit.entity_id, 401)
        self.assertEqual(audit.user_id, self.operator.user_id)
        self.assertEqual(audit.new_data["total_present"], 2)
        self.assertTrue({"password", "token", "password_hash"}.isdisjoint(audit.new_data))
        mutations = [call[0] for call in self.db.method_calls if call[0] in {"add", "flush", "add_all", "commit", "rollback"}]
        self.assertEqual(mutations, ["add", "flush", "add_all", "add", "commit"])
        self.assertEqual(result.total_present, 2)
        self.assertEqual(result.actual_companions, 1)
        self.assertEqual(result.checked_in_at.utcoffset().total_seconds(), -18000)

    def test_no_aplica_keeps_real_bus_id_and_internal_number(self):
        self.bus.bus_id = 516
        self.bus.bus_number = 16
        self.bus.display_name = "No aplica"
        self.payload = AttendanceCreate.model_validate(attendance_body(bus_id=516))
        with patch.object(services, "attendance_summary", return_value=None):
            result = self.create()

        attendance, audit = self.created
        self.assertEqual(attendance.bus_id, 516)
        self.assertEqual(audit.new_data["bus_id"], 516)
        self.assertEqual(result.bus_id, 516)
        self.assertEqual(result.bus_number, 16)
        self.assertEqual(result.display_name, "No aplica")
        self.db.commit.assert_called_once()

    def test_existing_attendance_reads_bus_display_name(self):
        self.db.execute.return_value.mappings.return_value.first.return_value = previous_attendance(
            bus_id=516, bus_number=16, display_name="No aplica"
        )
        result = services.attendance_summary(self.db, self.event.event_id, self.payload.participant_id)

        self.assertEqual(result.bus_id, 516)
        self.assertEqual(result.bus_number, 16)
        self.assertEqual(result.display_name, "No aplica")
        statement = self.db.execute.call_args.args[0]
        self.assertTrue(statement.selected_columns.display_name.shares_lineage(Bus.display_name))

    def test_duplicate_found_before_insert_is_not_written(self):
        with patch.object(services, "attendance_summary", return_value=self.previous):
            with self.assertRaises(services.AttendanceAlreadyExists) as error:
                self.create()
        self.assertEqual(error.exception.attendance.attendance_id, 401)
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.rollback.assert_called_once()

    def test_concurrent_duplicate_rolls_back_before_reading_winner(self):
        self.db.flush.side_effect = IntegrityError("insert attendance", {}, Exception(1062, "duplicate"))
        reads = []

        def summary(*_):
            reads.append(self.db.rollback.called)
            return None if len(reads) == 1 else self.previous

        with patch.object(services, "attendance_summary", side_effect=summary):
            with self.assertRaises(services.AttendanceAlreadyExists) as error:
                self.create()
        self.assertEqual(reads, [False, True])
        self.assertEqual(str(error.exception), "Esta persona ya fue registrada previamente.")
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()
        self.db.add_all.assert_not_called()

    def test_audit_failure_rolls_back_everything_and_cannot_commit(self):
        def failing_add(record):
            if isinstance(record, AuditLog):
                raise RuntimeError("isolated audit failure")
            self.created.append(record)

        self.db.add.side_effect = failing_add
        with patch.object(services, "attendance_summary", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "isolated audit failure"):
                self.create()
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_other_integrity_failures_are_not_misreported_as_duplicates(self):
        self.db.flush.side_effect = IntegrityError("insert attendance", {}, Exception(1452, "foreign key"))
        with patch.object(services, "attendance_summary", return_value=None) as summary:
            with self.assertRaises(IntegrityError):
                self.create()
        self.db.rollback.assert_called_once()
        summary.assert_called_once()

    def test_rejects_participant_day_and_bus_outside_valid_event_scope(self):
        for values, status in (
            ([None], 404),
            ([self.registration, None], 400),
            ([self.registration, self.day, None], 400),
        ):
            with self.subTest(status=status, count=len(values)):
                self.db.reset_mock()
                self.db.scalar.side_effect = values
                with patch.object(services, "attendance_summary", return_value=None):
                    with self.assertRaises(HTTPException) as error:
                        self.create()
                self.assertEqual(error.exception.status_code, status)
                self.db.add.assert_not_called()
                self.db.commit.assert_not_called()
                self.db.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
