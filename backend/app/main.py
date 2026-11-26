"""Carsem PO Tracker - FastAPI backend.

Run locally:  uvicorn app.main:app --reload --port 8000
API docs:     http://localhost:8000/docs
"""
import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings, today
from app.routers import attachments, auth, dashboard, discrepancies, notifications, pos, shipments, users, vendors
from app.services.errors import ServiceError
from app.services.overdue import run_overdue_check


async def _overdue_loop(minutes: int) -> None:
    """Simple background task (spec 7.3): check for overdue POs/shipments every few minutes."""
    while True:
        await asyncio.to_thread(run_overdue_check, today())
        await asyncio.sleep(minutes * 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    minutes = get_settings().overdue_check_minutes
    task = asyncio.create_task(_overdue_loop(minutes)) if minutes > 0 else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)

# Only needed when the Vite dev server calls the API directly; in Docker nginx serves both on one origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
def service_error(_: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


api = APIRouter(prefix="/api")
for module in (auth, vendors, users, pos, shipments, attachments, discrepancies, notifications, dashboard):
    api.include_router(module.router)


@api.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(api)
