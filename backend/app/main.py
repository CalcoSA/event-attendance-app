from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db, get_engine
from .exports import build_workbook
from .models import AppUser, Bus, EventDay
from .schemas import AttendanceCreate, AttendanceSummary, EventContext, LoginRequest, ParticipantResponse, UserResponse
from .security import COOKIE_NAME, create_access_token, dummy_hash, get_current_user, verify_password
from .services import AttendanceAlreadyExists, DUPLICATE_MESSAGE, create_attendance, export_rows, get_event, get_participant, now_local, search_participants, suggested_day_id


class ConfiguredCORSMiddleware:
    """Load validated origins at startup while keeping module imports side-effect free."""

    def __init__(self, app, settings: Settings | None = None):
        self.app = app
        self.settings = settings
        self.wrapped = None

    async def __call__(self, scope, receive, send):
        if self.wrapped is None:
            settings = self.settings or get_settings()
            self.wrapped = CORSMiddleware(
                self.app, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Requested-With"],
                expose_headers=["Content-Disposition"],
            )
        await self.wrapped(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        settings or get_settings()  # Fail at startup for missing/insecure configuration.
        yield
        if get_engine.cache_info().currsize:
            get_engine().dispose()
            get_engine.cache_clear()

    application = FastAPI(title="Fiesta Niños 2026", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: settings

    @application.middleware("http")
    async def protect_requests(request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/api/"):
            # A cross-origin site cannot add this header without an allowed CORS preflight.
            if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return JSONResponse(status_code=403, content={"detail": "Solicitud no autorizada."}, headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    # Outer CORS middleware handles OPTIONS before CSRF checks.
    application.add_middleware(ConfiguredCORSMiddleware, settings=settings)

    @application.exception_handler(AttendanceAlreadyExists)
    async def duplicate_handler(request: Request, exc: AttendanceAlreadyExists):
        return JSONResponse(status_code=409, content={"detail": DUPLICATE_MESSAGE, "attendance": exc.attendance.model_dump(mode="json")})

    @application.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # FastAPI's default errors include submitted values, including passwords.
        details = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": details})

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=500, content={"detail": "No fue posible completar la operación. Intenta nuevamente."}, headers={"Cache-Control": "no-store"})

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": "Ocurrió un error interno. Intenta nuevamente."}, headers={"Cache-Control": "no-store"})

    @application.get("/healthz")
    def health(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.rollback()
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok"}

    @application.post("/api/auth/login", response_model=UserResponse)
    def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
        username = payload.username.strip()
        user = db.scalar(select(AppUser).where(AppUser.username == username))
        password_valid = verify_password(payload.password, user.password_hash if user else dummy_hash())
        if user is None or not password_valid or not user.is_active or user.role not in {"ADMIN", "LOGISTICS"}:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
        user.last_login_at = now_local(settings).replace(tzinfo=None)
        db.commit()
        response.set_cookie(
            key=COOKIE_NAME, value=create_access_token(user.user_id, settings),
            max_age=settings.JWT_EXPIRE_MINUTES * 60, httponly=True, secure=settings.COOKIE_SECURE,
            samesite="lax", path="/",
        )
        return user

    @application.get("/api/auth/me", response_model=UserResponse)
    def me(user: AppUser = Depends(get_current_user)):
        return user

    @application.post("/api/auth/logout")
    def logout(response: Response, settings: Settings = Depends(get_settings)):
        response.delete_cookie(key=COOKIE_NAME, path="/", secure=settings.COOKIE_SECURE, httponly=True, samesite="lax")
        return {"message": "Sesión cerrada."}

    @application.get("/api/event/context", response_model=EventContext)
    def context(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
        event = get_event(db, settings)
        days = list(db.scalars(select(EventDay).where(EventDay.event_id == event.event_id).order_by(EventDay.event_date)))
        buses = list(db.scalars(select(Bus).where(Bus.event_id == event.event_id, Bus.is_active.is_(True)).order_by(Bus.bus_number)))
        today = now_local(settings).date()
        return {"event": event, "days": days, "buses": buses, "suggested_day_id": suggested_day_id(days, today), "today": today}

    @application.get("/api/participants", response_model=list[ParticipantResponse])
    def participants(
        search: str = Query(default="", max_length=160), limit: int = Query(default=30, ge=1, le=30),
        user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
    ):
        event = get_event(db, settings)
        return search_participants(db, event.event_id, search, limit, now_local(settings).date())

    @application.get("/api/participants/{document}", response_model=ParticipantResponse)
    def participant(document: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
        if not document or len(document) > 20:
            raise HTTPException(status_code=422, detail="La cédula debe tener entre 1 y 20 caracteres.")
        event = get_event(db, settings)
        return get_participant(db, event.event_id, document.strip())

    @application.post("/api/attendance", response_model=AttendanceSummary, status_code=201)
    def attendance(payload: AttendanceCreate, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
        return create_attendance(db, get_event(db, settings), user, payload, settings)

    @application.get("/api/export/attendance.xlsx")
    def export(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
        event = get_event(db, settings)
        stream = build_workbook(export_rows(db, event.event_id))
        filename = f"asistencia_fiesta_ninos_2026_{now_local(settings):%Y%m%d_%H%M}.xlsx"
        return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})

    return application


app = create_app()
