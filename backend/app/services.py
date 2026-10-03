from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from .config import Settings
from .models import AppUser, Attendance, AttendanceMember, AuditLog, Bus, Event, EventDay, EventRegistration, Participant
from .schemas import AttendanceCreate, AttendanceSummary, ParticipantResponse

BOGOTA = ZoneInfo("America/Bogota")
DUPLICATE_MESSAGE = "Esta persona ya fue registrada previamente."


def now_local(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.TIMEZONE))


def get_event(db: Session, settings: Settings) -> Event:
    event = db.scalar(select(Event).where(Event.code == settings.EVENT_CODE, Event.is_active.is_(True)))
    if event is None:
        raise HTTPException(status_code=404, detail="No se encontró el evento activo.")
    return event


def suggested_day_id(days: list[EventDay], today: date) -> int | None:
    return next((day.event_day_id for day in days if day.event_date == today), None)


def member_totals():
    return select(
        AttendanceMember.attendance_id,
        func.max(case((and_(AttendanceMember.member_type == "TITULAR", AttendanceMember.is_present.is_(True)), 1), else_=0)).label("titular_present"),
        func.sum(case((and_(AttendanceMember.member_type == "COMPANION", AttendanceMember.is_present.is_(True)), 1), else_=0)).label("actual_companions"),
        func.sum(case((AttendanceMember.is_present.is_(True), 1), else_=0)).label("total_present"),
    ).group_by(AttendanceMember.attendance_id).subquery()


def summary_statement(event_id: int) -> Select:
    totals = member_totals()
    return select(
        Attendance.participant_id, Attendance.attendance_id, Attendance.actual_day_id,
        EventDay.event_date.label("actual_date"), EventDay.day_label.label("actual_day"),
        Attendance.bus_id, Bus.bus_number, Attendance.checked_in_at,
        AppUser.document.label("registered_by_document"), AppUser.full_name.label("registered_by_name"),
        func.coalesce(totals.c.titular_present, 0).label("titular_present"),
        func.coalesce(totals.c.actual_companions, 0).label("actual_companions"),
        func.coalesce(totals.c.total_present, 0).label("total_present"),
    ).join(EventDay, EventDay.event_day_id == Attendance.actual_day_id).join(
        Bus, Bus.bus_id == Attendance.bus_id,
    ).join(AppUser, AppUser.user_id == Attendance.registered_by_user_id).outerjoin(
        totals, totals.c.attendance_id == Attendance.attendance_id,
    ).where(Attendance.event_id == event_id)


def serialize_summary(row) -> AttendanceSummary:
    values = dict(row)
    moment = values["checked_in_at"]
    # Existing DATETIME values store Colombian local time without a timezone.
    values["checked_in_at"] = moment.replace(tzinfo=BOGOTA) if moment.tzinfo is None else moment.astimezone(BOGOTA)
    return AttendanceSummary.model_validate(values)


def attendance_summary(db: Session, event_id: int, participant_id: int) -> AttendanceSummary | None:
    row = db.execute(summary_statement(event_id).where(Attendance.participant_id == participant_id)).mappings().first()
    return serialize_summary(row) if row else None


class AttendanceAlreadyExists(Exception):
    def __init__(self, attendance: AttendanceSummary):
        self.attendance = attendance
        super().__init__(DUPLICATE_MESSAGE)


def participant_statement(event_id: int) -> Select:
    return select(
        Participant.participant_id, Participant.document, Participant.full_name,
        EventRegistration.registration_id, EventRegistration.planned_day_id,
        EventDay.event_date.label("planned_date"), EventDay.day_label.label("planned_day"),
        EventRegistration.planned_companion_count,
    ).select_from(EventRegistration).join(
        Participant, Participant.participant_id == EventRegistration.participant_id,
    ).join(EventDay, EventDay.event_day_id == EventRegistration.planned_day_id).outerjoin(
        Attendance, and_(Attendance.event_id == EventRegistration.event_id, Attendance.participant_id == EventRegistration.participant_id),
    ).where(EventRegistration.event_id == event_id)


def participants_with_attendance(db: Session, event_id: int, rows) -> list[ParticipantResponse]:
    if not rows:
        return []
    identifiers = [row["participant_id"] for row in rows]
    attendance_rows = db.execute(summary_statement(event_id).where(Attendance.participant_id.in_(identifiers))).mappings().all()
    summaries = {row["participant_id"]: serialize_summary(row) for row in attendance_rows}
    return [ParticipantResponse(**dict(row), already_attended=row["participant_id"] in summaries,
                                attendance=summaries.get(row["participant_id"])) for row in rows]


def search_participants(db: Session, event_id: int, search: str, limit: int, today: date) -> list[ParticipantResponse]:
    statement = participant_statement(event_id)
    search = search.strip()
    if search:
        statement = statement.where(or_(Participant.document.contains(search, autoescape=True), Participant.full_name.contains(search, autoescape=True)))
        statement = statement.order_by(case((Participant.document == search, 0), else_=1), Participant.full_name, Participant.participant_id)
    else:
        statement = statement.order_by(case(
            (and_(Attendance.attendance_id.is_(None), EventDay.event_date == today), 0),
            (Attendance.attendance_id.is_(None), 1), else_=2,
        ), Participant.full_name, Participant.participant_id)
    rows = db.execute(statement.limit(limit)).mappings().all()
    return participants_with_attendance(db, event_id, rows)


def get_participant(db: Session, event_id: int, document: str) -> ParticipantResponse:
    row = db.execute(participant_statement(event_id).where(Participant.document == document)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="No se encontró esta cédula en el evento.")
    return participants_with_attendance(db, event_id, [row])[0]


def create_attendance(db: Session, event: Event, user: AppUser, payload: AttendanceCreate, settings: Settings) -> AttendanceSummary:
    event_id = event.event_id
    participant_id = payload.participant_id
    try:
        registration = db.scalar(select(EventRegistration).where(
            EventRegistration.event_id == event_id, EventRegistration.participant_id == participant_id,
        ))
        if registration is None:
            raise HTTPException(status_code=404, detail="El participante no está registrado en este evento.")
        previous = attendance_summary(db, event_id, participant_id)
        if previous:
            raise AttendanceAlreadyExists(previous)
        day = db.scalar(select(EventDay).where(EventDay.event_day_id == payload.actual_day_id, EventDay.event_id == event_id))
        if day is None:
            raise HTTPException(status_code=400, detail="El día seleccionado no pertenece al evento.")
        bus = db.scalar(select(Bus).where(Bus.bus_id == payload.bus_id, Bus.event_id == event_id, Bus.is_active.is_(True)))
        if bus is None:
            raise HTTPException(status_code=400, detail="Selecciona un bus activo de este evento.")
        if len(payload.members) < registration.planned_companion_count + 1:
            raise HTTPException(status_code=400, detail="Debes indicar la asistencia del titular y de todos los acompañantes programados.")
        titular_present = next(member.is_present for member in payload.members if member.member_type == "TITULAR")
        actual_companions = sum(member.is_present for member in payload.members if member.member_type == "COMPANION")
        total_present = int(titular_present) + actual_companions
        timestamp = now_local(settings)
        attendance = Attendance(
            event_id=event_id, participant_id=participant_id, actual_day_id=day.event_day_id,
            bus_id=bus.bus_id, registered_by_user_id=user.user_id, checked_in_at=timestamp.replace(tzinfo=None),
        )
        db.add(attendance)
        db.flush()
        db.add_all([AttendanceMember(attendance_id=attendance.attendance_id, **member.model_dump()) for member in payload.members])
        db.add(AuditLog(
            user_id=user.user_id, action="ATTENDANCE_CREATED", entity_type="ATTENDANCE", entity_id=attendance.attendance_id,
            new_data={"participant_id": participant_id, "actual_day_id": day.event_day_id, "bus_id": bus.bus_id,
                      "titular_present": titular_present, "actual_companions": actual_companions, "total_present": total_present},
            created_at=timestamp.replace(tzinfo=None),
        ))
        result = AttendanceSummary(
            attendance_id=attendance.attendance_id, actual_day_id=day.event_day_id, actual_date=day.event_date,
            actual_day=day.day_label, bus_id=bus.bus_id, bus_number=bus.bus_number, checked_in_at=timestamp,
            registered_by_document=user.document, registered_by_name=user.full_name,
            titular_present=titular_present, actual_companions=actual_companions, total_present=total_present,
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        # Only MySQL duplicate-key errors may represent concurrent attendance.
        # A rollback also drops MySQL's old REPEATABLE READ snapshot.
        error_args = getattr(exc.orig, "args", ())
        if error_args and error_args[0] == 1062:
            previous = attendance_summary(db, event_id, participant_id)
            if previous:
                raise AttendanceAlreadyExists(previous) from None
        raise
    except Exception:
        db.rollback()
        raise


def export_rows(db: Session, event_id: int):
    planned_day = aliased(EventDay)
    actual_day = aliased(EventDay)
    totals = member_totals()
    statement = select(
        Participant.document, Participant.full_name, planned_day.event_date.label("planned_date"),
        planned_day.day_label.label("planned_day"), EventRegistration.planned_companion_count,
        actual_day.event_date.label("actual_date"), actual_day.day_label.label("actual_day"), Bus.bus_number,
        func.coalesce(totals.c.titular_present, 0).label("titular_present"),
        func.coalesce(totals.c.actual_companions, 0).label("actual_companions"),
        func.coalesce(totals.c.total_present, 0).label("total_present"),
        AppUser.document.label("registered_by_document"), AppUser.full_name.label("registered_by_name"), Attendance.checked_in_at,
    ).select_from(Attendance).join(Participant, Participant.participant_id == Attendance.participant_id).join(
        EventRegistration, and_(EventRegistration.event_id == Attendance.event_id, EventRegistration.participant_id == Attendance.participant_id),
    ).join(planned_day, planned_day.event_day_id == EventRegistration.planned_day_id).join(
        actual_day, actual_day.event_day_id == Attendance.actual_day_id,
    ).join(Bus, Bus.bus_id == Attendance.bus_id).join(AppUser, AppUser.user_id == Attendance.registered_by_user_id).outerjoin(
        totals, totals.c.attendance_id == Attendance.attendance_id,
    ).where(Attendance.event_id == event_id).order_by(Bus.bus_number, actual_day.event_date, Attendance.checked_in_at, Attendance.attendance_id)
    return db.execute(statement).mappings().all()
