from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True,
        extra="ignore", hide_input_in_errors=True,
    )

    APP_ENV: Literal["development", "test", "production"] = "development"
    DB_HOST: str = "localhost"
    DB_PORT: int = Field(default=3306, ge=1, le=65535)
    DB_NAME: str = "bdcalco_event_attendance"
    DB_USER: str = Field(min_length=1)
    DB_PASSWORD: SecretStr
    JWT_SECRET: SecretStr
    JWT_EXPIRE_MINUTES: int = Field(default=720, ge=1, le=10080)
    COOKIE_SECURE: bool = False
    TIMEZONE: Literal["America/Bogota"] = "America/Bogota"
    EVENT_CODE: str = Field(default="FIESTA_NINOS_2026", min_length=1, max_length=50)
    CORS_ORIGINS: list[str] = Field(default_factory=list)

    @field_validator("DB_USER")
    @classmethod
    def validate_db_user(cls, value: str) -> str:
        if value.strip().lower() in {"", "change-me"}:
            raise ValueError("Configure DB_USER con el usuario de la base existente.")
        return value

    @field_validator("DB_PASSWORD")
    @classmethod
    def validate_db_password(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().strip().lower() in {"", "change-me"}:
            raise ValueError("Configure DB_PASSWORD con la contraseña de la base existente.")
        return value

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw.encode("utf-8")) < 32 or raw.strip().lower() in {
            "change-me", "your-secret-key", "secret", "changeme",
        } or len(set(raw)) < 8:
            raise ValueError("JWT_SECRET debe ser aleatorio, privado y contener al menos 32 bytes.")
        return value

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.path or parsed.query or parsed.fragment
                or parsed.username or parsed.password or "*" in origin
            ):
                raise ValueError("CORS_ORIGINS admite únicamente orígenes completos sin rutas ni comodines.")
        return origins

    @model_validator(mode="after")
    def secure_production_cookie(self) -> "Settings":
        if self.APP_ENV == "production" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SECURE debe ser true en producción.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
