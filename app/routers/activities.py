from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Activity, Registration, Member, ActivityType, ActivityStatus, AttendanceStatus

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def list_activities(
    request: Request,
    db: Session = Depends(get_db),
    type: str = "all",
    status: str = "all",
    page: int = 1,
):
    page_size = 20
    query = db.query(Activity)
    if type != "all":
        query = query.filter(Activity.type == type)
    if status != "all":
        query = query.filter(Activity.status == status)
    total = query.count()
    activities = query.order_by(Activity.datetime_start.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size
    return templates.TemplateResponse("activities/list.html", {
        "request": request,
        "activities": activities,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "type": type,
        "status": status,
        "ActivityType": ActivityType,
        "ActivityStatus": ActivityStatus,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_activity_form(request: Request):
    return templates.TemplateResponse("activities/form.html", {
        "request": request,
        "activity": None,
        "ActivityType": ActivityType,
        "ActivityStatus": ActivityStatus,
        "action": "/activities/",
        "method": "POST",
    })


@router.post("/", response_class=HTMLResponse)
async def create_activity(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    type: str = Form(...),
    description: str = Form(""),
    datetime_start: str = Form(...),
    datetime_end: Optional[str] = Form(None),
    location: str = Form(""),
    capacity: int = Form(20),
    fee: float = Form(0.0),
    status: str = Form("upcoming"),
):
    activity = Activity(
        name=name,
        type=ActivityType(type),
        description=description,
        datetime_start=datetime.strptime(datetime_start, "%Y-%m-%dT%H:%M"),
        datetime_end=datetime.strptime(datetime_end, "%Y-%m-%dT%H:%M") if datetime_end else None,
        location=location,
        capacity=capacity,
        fee=fee,
        status=ActivityStatus(status),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return HTMLResponse(status_code=303, headers={"Location": f"/activities/{activity.id}"})


@router.get("/{activity_id}", response_class=HTMLResponse)
async def activity_detail(request: Request, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    available_members = db.query(Member).filter(Member.is_active == True).all()
    return templates.TemplateResponse("activities/detail.html", {
        "request": request,
        "activity": activity,
        "available_members": available_members,
        "AttendanceStatus": AttendanceStatus,
    })


@router.get("/{activity_id}/edit", response_class=HTMLResponse)
async def edit_activity_form(request: Request, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return templates.TemplateResponse("activities/form.html", {
        "request": request,
        "activity": activity,
        "ActivityType": ActivityType,
        "ActivityStatus": ActivityStatus,
        "action": f"/activities/{activity_id}/edit",
        "method": "POST",
    })


@router.post("/{activity_id}/edit", response_class=HTMLResponse)
async def update_activity(
    request: Request,
    activity_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    type: str = Form(...),
    description: str = Form(""),
    datetime_start: str = Form(...),
    datetime_end: Optional[str] = Form(None),
    location: str = Form(""),
    capacity: int = Form(20),
    fee: float = Form(0.0),
    status: str = Form("upcoming"),
):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    activity.name = name
    activity.type = ActivityType(type)
    activity.description = description
    activity.datetime_start = datetime.strptime(datetime_start, "%Y-%m-%dT%H:%M")
    activity.datetime_end = datetime.strptime(datetime_end, "%Y-%m-%dT%H:%M") if datetime_end else None
    activity.location = location
    activity.capacity = capacity
    activity.fee = fee
    activity.status = ActivityStatus(status)
    db.commit()
    return HTMLResponse(status_code=303, headers={"Location": f"/activities/{activity_id}"})


@router.post("/{activity_id}/delete", response_class=HTMLResponse)
async def delete_activity(request: Request, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()
    return HTMLResponse(status_code=303, headers={"Location": "/activities/"})


@router.post("/{activity_id}/register", response_class=HTMLResponse)
async def register_member(
    request: Request,
    activity_id: int,
    db: Session = Depends(get_db),
    member_id: int = Form(...),
):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    existing = db.query(Registration).filter(
        Registration.activity_id == activity_id,
        Registration.member_id == member_id,
        Registration.attendance != AttendanceStatus.cancelled,
    ).first()
    if not existing:
        reg = Registration(activity_id=activity_id, member_id=member_id)
        db.add(reg)
        db.commit()
    return HTMLResponse(status_code=303, headers={"Location": f"/activities/{activity_id}"})


@router.post("/{activity_id}/registrations/{reg_id}/attendance", response_class=HTMLResponse)
async def update_attendance(
    request: Request,
    activity_id: int,
    reg_id: int,
    db: Session = Depends(get_db),
    attendance: str = Form(...),
    feedback: str = Form(""),
):
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if reg:
        reg.attendance = AttendanceStatus(attendance)
        reg.feedback = feedback
        db.commit()
    return HTMLResponse(status_code=303, headers={"Location": f"/activities/{activity_id}"})
