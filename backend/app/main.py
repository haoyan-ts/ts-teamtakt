from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.db.engine import async_session_factory
from app.db.seed import seed_initial_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as db:
        await seed_initial_data(db)
    yield


app = FastAPI(title="ts-teamtakt", docs_url="/docs", lifespan=lifespan)
app.include_router(v1_router, prefix="/api/v1")
