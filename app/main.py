import os
import logging
from datetime import datetime, date, timedelta
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database import engine, Base, SessionLocal
from app.routers import dashboard, members, activities, respite, notifications

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="長者中心 CRM", version="1.0.0")

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
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")
