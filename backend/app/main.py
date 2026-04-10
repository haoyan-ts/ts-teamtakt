from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import router as v1_router
from app.api.v1.social import limiter
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db.engine import async_session_factory
from app.db.seed import seed_initial_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as db:
        await seed_initial_data(db)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="ts-teamtakt", docs_url="/docs", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, cast(Any, _rate_limit_exceeded_handler))
app.add_middleware(SlowAPIMiddleware)
app.include_router(v1_router, prefix="/api/v1")
