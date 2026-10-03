import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app import database
from tests.helpers import test_settings


class ConfigurationTests(unittest.TestCase):
    def tearDown(self):
        database.get_engine.cache_clear()

    def test_rejects_missing_placeholder_and_weak_configuration(self):
        cases = (
            {"DB_USER": "change-me"},
            {"DB_PASSWORD": "change-me"},
            {"JWT_SECRET": "change-me"},
            {"JWT_SECRET": "a" * 64},
            {"DB_PORT": 0},
            {"TIMEZONE": "UTC"},
            {"CORS_ORIGINS": ["*"]},
            {"CORS_ORIGINS": ["https://example.invalid/path"]},
            {"APP_ENV": "production", "COOKIE_SECURE": False},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                test_settings(**overrides)

    def test_configuration_does_not_expose_secrets_in_repr(self):
        settings = test_settings()
        self.assertNotIn(settings.DB_PASSWORD.get_secret_value(), repr(settings))
        self.assertNotIn(settings.JWT_SECRET.get_secret_value(), repr(settings))

    def test_engine_preserves_special_password_and_has_capacity_without_connecting(self):
        settings = test_settings()
        database.get_engine.cache_clear()
        with patch.object(database, "get_settings", return_value=settings), patch.object(
            database, "create_engine", return_value=MagicMock()
        ) as create_engine:
            engine = database.get_engine()
            self.assertIs(engine, database.get_engine())
        create_engine.assert_called_once()
        args, options = create_engine.call_args
        url = args[0]
        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual(url.password, settings.DB_PASSWORD.get_secret_value())
        self.assertEqual(url.database, "bdcalco_event_attendance")
        self.assertTrue(options["pool_pre_ping"])
        self.assertTrue(options["hide_parameters"])
        self.assertGreaterEqual(options["pool_size"] + options["max_overflow"], 30)
        self.assertGreater(options["pool_recycle"], 0)

    def test_each_request_owns_and_closes_a_separate_session(self):
        first, second = MagicMock(), MagicMock()
        with patch.object(database, "get_engine", return_value=MagicMock()), patch.object(
            database, "Session", side_effect=[first, second]
        ):
            request_one = database.get_db()
            request_two = database.get_db()
            self.assertIsNot(next(request_one), next(request_two))
            request_one.close()
            request_two.close()
        first.__exit__.assert_called_once()
        second.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
