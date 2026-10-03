import unittest

from pydantic import ValidationError

from app.schemas import AttendanceCreate
from tests.helpers import attendance_body


class AttendanceValidationTests(unittest.TestCase):
    def assert_invalid(self, body):
        with self.assertRaises(ValidationError):
            AttendanceCreate.model_validate(body)

    def test_accepts_absent_titular_and_present_extra_companion(self):
        members = [
            {"member_number": 0, "member_type": "TITULAR", "is_present": False},
            {"member_number": 1, "member_type": "COMPANION", "is_present": True},
            {"member_number": 2, "member_type": "COMPANION", "is_present": True},
        ]
        payload = AttendanceCreate.model_validate(attendance_body(members=members))
        self.assertFalse(payload.members[0].is_present)
        self.assertEqual(sum(member.is_present for member in payload.members), 2)

    def test_requires_at_least_one_person(self):
        members = attendance_body()["members"]
        for member in members:
            member["is_present"] = False
        self.assert_invalid(attendance_body(members=members))

    def test_requires_exactly_one_titular_at_zero(self):
        cases = [
            [{"member_number": 1, "member_type": "COMPANION", "is_present": True}],
            [
                {"member_number": 0, "member_type": "TITULAR", "is_present": True},
                {"member_number": 1, "member_type": "TITULAR", "is_present": True},
            ],
            [
                {"member_number": 0, "member_type": "COMPANION", "is_present": True},
                {"member_number": 1, "member_type": "TITULAR", "is_present": True},
            ],
        ]
        for members in cases:
            with self.subTest(members=members):
                self.assert_invalid(attendance_body(members=members))

    def test_rejects_duplicate_and_out_of_schema_member_numbers(self):
        for number in (0, -1, 51):
            members = attendance_body()["members"]
            members[1]["member_number"] = number
            with self.subTest(number=number):
                self.assert_invalid(attendance_body(members=members))

    def test_client_cannot_supply_operator_or_checkin_time(self):
        for field, value in (
            ("registered_by_user_id", 999),
            ("checked_in_at", "2026-10-06T09:00:00"),
            ("user", "OPERADOR DE PRUEBA"),
        ):
            with self.subTest(field=field):
                self.assert_invalid(attendance_body(**{field: value}))

    def test_requires_positive_server_identifiers(self):
        for field in ("participant_id", "actual_day_id", "bus_id"):
            with self.subTest(field=field):
                self.assert_invalid(attendance_body(**{field: 0}))


if __name__ == "__main__":
    unittest.main()
