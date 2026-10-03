"""Non-personal fixtures used only in tests, with no database connections."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.config import Settings


def test_settings(**overrides):
    values = {
        "APP_ENV": "test",
        "DB_HOST": "database.invalid",
        "DB_USER": "isolated_test_user",
        "DB_PASSWORD": "isolated-test-password@:/?#[]%",
        "JWT_SECRET": "isolated-test-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "COOKIE_SECURE": False,
    }
    return Settings(_env_file=None, **(values | overrides))


def database_session():
    return MagicMock(spec=Session)


def sample_operator(**overrides):
    values = {
        "user_id": 901,
        "document": "0000000002",
        "username": "0000000002",
        "full_name": "OPERADOR DE PRUEBA",
        "role": "LOGISTICS",
        "is_active": True,
        "last_login_at": None,
    }
    return SimpleNamespace(**(values | overrides))


def sample_event(**overrides):
    values = {
        "event_id": 801,
        "code": "FIESTA_NINOS_2026",
        "name": "Fiesta Niños 2026",
        "starts_on": date(2026, 10, 6),
        "ends_on": date(2026, 10, 7),
        "is_active": True,
    }
    return SimpleNamespace(**(values | overrides))


def attendance_body(**overrides):
    values = {
        "participant_id": 701,
        "actual_day_id": 601,
        "bus_id": 501,
        "members": [
            {"member_number": 0, "member_type": "TITULAR", "is_present": True},
            {"member_number": 1, "member_type": "COMPANION", "is_present": False},
            {"member_number": 2, "member_type": "COMPANION", "is_present": True},
        ],
    }
    return values | overrides


def previous_attendance(**overrides):
    values = {
        "attendance_id": 401,
        "actual_day_id": 601,
        "actual_date": date(2026, 10, 6),
        "actual_day": "Martes 6 de octubre",
        "bus_id": 501,
        "bus_number": 1,
        "checked_in_at": datetime(2026, 10, 6, 9, 30),
        "registered_by_name": "OPERADOR DE PRUEBA",
        "registered_by_document": "0000000002",
        "titular_present": True,
        "actual_companions": 1,
        "total_present": 2,
    }
    return values | overrides
