from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy.dialects import mysql

from app import services
from tests.helpers import database_session, test_settings


class SearchAndDayTests(unittest.TestCase):
    def test_suggests_only_the_current_event_day_without_hardcoded_ids(self):
        days = [
            SimpleNamespace(event_day_id=601, event_date=date(2026, 10, 6)),
            SimpleNamespace(event_day_id=602, event_date=date(2026, 10, 7)),
        ]
        self.assertEqual(services.suggested_day_id(days, date(2026, 10, 6)), 601)
        self.assertEqual(services.suggested_day_id(days, date(2026, 10, 7)), 602)
        self.assertIsNone(services.suggested_day_id(days, date(2026, 10, 3)))

    def test_local_day_uses_bogota_at_utc_midnight_boundary(self):
        fixed = datetime(2026, 10, 7, 2, 0, tzinfo=timezone.utc)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed.astimezone(tz)

        with patch.object(services, "datetime", Clock):
            self.assertEqual(services.now_local(test_settings()).date(), date(2026, 10, 6))

    def test_typed_search_is_parameterized_and_searches_all_event_days(self):
        db = database_session()
        db.execute.return_value.mappings.return_value.all.return_value = []
        value = "prueba_%' OR 1=1"
        self.assertEqual(services.search_participants(db, 801, value, 30, date(2026, 10, 6)), [])
        statement = db.execute.call_args.args[0]
        compiled = statement.compile(dialect=mysql.dialect())
        sql = str(compiled)
        where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
        self.assertNotIn(value, sql)
        self.assertIn("event_registration.event_id", where_clause)
        self.assertIn("participant.document LIKE", where_clause)
        self.assertIn("participant.full_name LIKE", where_clause)
        self.assertNotIn("event_day.event_date", where_clause)
        self.assertIn("LIMIT", sql)
        self.assertIn(30, compiled.params.values())
        self.assertIn("prueba/_/%' OR 1=1", compiled.params.values())

    def test_empty_search_prioritizes_pending_today_without_excluding_other_days(self):
        db = database_session()
        db.execute.return_value.mappings.return_value.all.return_value = []
        services.search_participants(db, 801, " ", 30, date(2026, 10, 7))
        statement = db.execute.call_args.args[0]
        compiled = statement.compile(dialect=mysql.dialect())
        sql = str(compiled)
        self.assertIn(date(2026, 10, 7), compiled.params.values())
        self.assertIn("attendance.attendance_id IS NULL", sql.split("ORDER BY", 1)[1])
        self.assertNotIn("event_day.event_date", sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0])


if __name__ == "__main__":
    unittest.main()
