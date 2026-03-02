import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from app.database import engine, Base
from app.routers import dashboard, members, activities, respite, notifications
from app.services.scheduler import start_scheduler, stop_scheduler

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(title="長者中心 CRM", version="1.0.0", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(dashboard.router)
app.include_router(members.router, prefix="/members", tags=["members"])
app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(respite.router, prefix="/respite", tags=["respite"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
