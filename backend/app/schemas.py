from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(InputModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    document: str
    full_name: str
    role: Literal["ADMIN", "LOGISTICS"]


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: int
    code: str
    name: str


class DayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_day_id: int
    event_date: date
    day_label: str


class BusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bus_id: int
    bus_number: int


class EventContext(BaseModel):
    event: EventResponse
    days: list[DayResponse]
    buses: list[BusResponse]
    suggested_day_id: int | None
    today: date


class AttendanceSummary(BaseModel):
    attendance_id: int
    actual_day_id: int
    actual_date: date
    actual_day: str
    bus_id: int
    bus_number: int
    checked_in_at: datetime
    registered_by_document: str
    registered_by_name: str
    titular_present: bool
    actual_companions: int
    total_present: int


class ParticipantResponse(BaseModel):
    participant_id: int
    document: str
    full_name: str
    registration_id: int
    planned_day_id: int
    planned_date: date
    planned_day: str
    planned_companion_count: int
    already_attended: bool
    attendance: AttendanceSummary | None


class MemberInput(InputModel):
    member_number: StrictInt = Field(ge=0, le=50)
    member_type: Literal["TITULAR", "COMPANION"]
    is_present: StrictBool


class AttendanceCreate(InputModel):
    participant_id: StrictInt = Field(gt=0)
    actual_day_id: StrictInt = Field(gt=0)
    bus_id: StrictInt = Field(gt=0)
    members: list[MemberInput] = Field(min_length=1, max_length=51)

    @model_validator(mode="after")
    def validate_members(self) -> "AttendanceCreate":
        numbers = [member.member_number for member in self.members]
        if len(set(numbers)) != len(numbers):
            raise ValueError("No se permiten números de miembro duplicados.")
        titular = [member for member in self.members if member.member_type == "TITULAR"]
        if len(titular) != 1 or titular[0].member_number != 0:
            raise ValueError("Debe existir un único titular con número 0.")
        if any(member.member_number == 0 for member in self.members if member.member_type == "COMPANION"):
            raise ValueError("Los acompañantes deben tener un número mayor o igual a 1.")
        if sorted(numbers) != list(range(len(numbers))):
            raise ValueError("Los números de los miembros deben ser consecutivos desde 0.")
        if not any(member.is_present for member in self.members):
            raise ValueError("Debe estar presente al menos una persona.")
        return self
