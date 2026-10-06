from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, JSON, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


Id = BIGINT(unsigned=True)
DateTime = DATETIME(fsp=6)


class Event(Base):
    __tablename__ = "event"
    event_id: Mapped[int] = mapped_column(Id, primary_key=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class EventDay(Base):
    __tablename__ = "event_day"
    event_day_id: Mapped[int] = mapped_column(Id, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.event_id"))
    event_date: Mapped[date] = mapped_column(Date)
    day_label: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Bus(Base):
    __tablename__ = "bus"
    bus_id: Mapped[int] = mapped_column(Id, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.event_id"))
    bus_number: Mapped[int] = mapped_column(TINYINT(unsigned=True))
    display_name: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class AppUser(Base):
    __tablename__ = "app_user"
    user_id: Mapped[int] = mapped_column(Id, primary_key=True)
    document: Mapped[str] = mapped_column(String(20))
    username: Mapped[str] = mapped_column(String(50))
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Enum("ADMIN", "LOGISTICS"))
    is_active: Mapped[bool] = mapped_column(Boolean)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Participant(Base):
    __tablename__ = "participant"
    participant_id: Mapped[int] = mapped_column(Id, primary_key=True)
    document: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ImportBatch(Base):
    __tablename__ = "import_batch"
    import_batch_id: Mapped[int] = mapped_column(Id, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.event_id"))
    batch_code: Mapped[str] = mapped_column(String(80))
    source_file_name: Mapped[str] = mapped_column(String(255))
    source_sheet: Mapped[str] = mapped_column(String(100))
    total_rows: Mapped[int] = mapped_column(Integer)
    imported_rows: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class EventRegistration(Base):
    __tablename__ = "event_registration"
    registration_id: Mapped[int] = mapped_column(Id, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.event_id"))
    participant_id: Mapped[int] = mapped_column(ForeignKey("participant.participant_id"))
    planned_day_id: Mapped[int] = mapped_column(ForeignKey("event_day.event_day_id"))
    planned_companion_count: Mapped[int] = mapped_column(TINYINT(unsigned=True))
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batch.import_batch_id"), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Attendance(Base):
    __tablename__ = "attendance"
    attendance_id: Mapped[int] = mapped_column(Id, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.event_id"))
    participant_id: Mapped[int] = mapped_column(ForeignKey("participant.participant_id"))
    actual_day_id: Mapped[int] = mapped_column(ForeignKey("event_day.event_day_id"))
    bus_id: Mapped[int] = mapped_column(ForeignKey("bus.bus_id"))
    registered_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"))
    checked_in_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class AttendanceMember(Base):
    __tablename__ = "attendance_member"
    attendance_member_id: Mapped[int] = mapped_column(Id, primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.attendance_id"))
    member_number: Mapped[int] = mapped_column(TINYINT(unsigned=True))
    member_type: Mapped[str] = mapped_column(Enum("TITULAR", "COMPANION"))
    is_present: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class AuditLog(Base):
    __tablename__ = "audit_log"
    audit_log_id: Mapped[int] = mapped_column(Id, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.user_id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Id, nullable=True)
    old_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
