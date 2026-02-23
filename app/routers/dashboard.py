import os
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import Member, Activity, Registration, RespiteService, RespiteStatus, ActivityStatus, AttendanceStatus
from app.services.respite_scheduler import get_days_data

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard")
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    week_offset: int = 0,
    day_offset: int = 0,
):
    today = date.today()

    # KPI Stats
    total_members = db.query(func.count(Member.id)).filter(Member.is_active == True).scalar()
    today_respite_approved = (
        db.query(func.count(RespiteService.id))
        .filter(RespiteService.date == today, RespiteService.status == RespiteStatus.approved)
        .scalar()
    )
    pending_respite = (
        db.query(func.count(RespiteService.id))
        .filter(RespiteService.status == RespiteStatus.pending)
        .scalar()
    )

    # Activities for the viewed day
    viewed_date = today + timedelta(days=day_offset)
    day_activities = (
        db.query(Activity)
        .filter(func.date(Activity.datetime_start) == viewed_date)
        .order_by(Activity.datetime_start)
        .all()
    )

    # KPI: today's activity count always reflects today
    today_activities_count = (
        db.query(func.count(Activity.id))
        .filter(func.date(Activity.datetime_start) == today)
        .scalar()
    )

    # Week (Mon–Sun) respite data
    _DOW = ["一", "二", "三", "四", "五", "六", "日"]
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    days_data = get_days_data(db, week_dates)
    week_days = [
        {
            "date": d,
            "date_str": d.strftime("%Y-%m-%d"),
            "date_display": d.strftime("%m/%d"),
            "dow": _DOW[d.weekday()],
            "is_today": d == today,
            "data": days_data.get(d, {}),
        }
        for d in week_dates
    ]

    centre_name = os.getenv("CENTRE_NAME", "快樂長者中心")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "centre_name": centre_name,
        "total_members": total_members,
        "today_activities_count": today_activities_count,
        "today_respite_approved": today_respite_approved,
        "pending_respite": pending_respite,
        "day_activities": day_activities,
        "viewed_date": viewed_date,
        "day_offset": day_offset,
        "week_days": week_days,
        "week_offset": week_offset,
        "today": today,
    })


@router.get("/dashboard/activity-detail/{activity_id}", response_class=HTMLResponse)
async def activity_detail(request: Request, activity_id: int, db: Session = Depends(get_db)):
    activity = (
        db.query(Activity)
        .options(joinedload(Activity.registrations).joinedload(Registration.member))
        .filter(Activity.id == activity_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    attended = [r for r in activity.registrations if r.attendance == AttendanceStatus.attended]
    registered = [r for r in activity.registrations if r.attendance == AttendanceStatus.registered]
    absent = [r for r in activity.registrations if r.attendance == AttendanceStatus.absent]
    cancelled = [r for r in activity.registrations if r.attendance == AttendanceStatus.cancelled]

    return templates.TemplateResponse("partials/activity_detail.html", {
        "request": request,
        "act": activity,
        "attended": attended,
        "registered": registered,
        "absent": absent,
        "cancelled": cancelled,
    })
