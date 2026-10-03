from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from .config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    url = URL.create(
        "mysql+pymysql", username=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(), host=settings.DB_HOST,
        port=settings.DB_PORT, database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url, pool_pre_ping=True, pool_recycle=1800, pool_size=20,
        max_overflow=20, pool_timeout=30, echo=False, hide_parameters=True,
        connect_args={
            "connect_timeout": 5, "read_timeout": 30, "write_timeout": 30,
            "init_command": "SET time_zone = '-05:00'",
        },
    )


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine(), autoflush=False, expire_on_commit=False) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
