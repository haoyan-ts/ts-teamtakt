from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.types import ExceptionHandler

from app.api.v1 import router as v1_router
from app.api.v1.social import limiter
from app.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db.engine import async_session_factory
from app.db.seed import seed_initial_data

_WEAK_PASSWORDS = {"admin", "password", "Admin", "Password", "123456", "test", "Test"}


def _check_admin_password_strength() -> None:
    """Refuse to start in non-local environments if ADMIN_PASSWORD is unset or weak."""
    is_local = (
        "localhost" in settings.DATABASE_URL or "127.0.0.1" in settings.DATABASE_URL
    )
    if is_local:
        return
    pwd = settings.ADMIN_PASSWORD
    if not pwd or pwd in _WEAK_PASSWORDS:
        raise RuntimeError(
            "ADMIN_PASSWORD is unset or too weak for a non-local environment. "
            "Set a strong password via the ADMIN_PASSWORD environment variable."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_admin_password_strength()
    async with async_session_factory() as db:
        await seed_initial_data(db)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="ts-teamtakt", docs_url="/docs", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded, cast(ExceptionHandler, _rate_limit_exceeded_handler)
)
app.add_middleware(SlowAPIMiddleware)
app.include_router(v1_router, prefix="/api/v1")
