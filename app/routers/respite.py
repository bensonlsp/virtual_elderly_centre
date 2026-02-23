from calendar import monthrange
from datetime import date, datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import RespiteService, Member, SessionType, RespiteStatus
from app.services.respite_scheduler import (
    get_daily_summary, get_remaining_slots, get_monthly_data, TOTAL_CAPACITY
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MONTH_NAMES = ["一月", "二月", "三月", "四月", "五月", "六月",
               "七月", "八月", "九月", "十月", "十一月", "十二月"]


def _build_calendar_weeks(year: int, month: int, monthly_data: dict) -> list:
    """Return a list of 7-element week rows (None = padding cell)."""
    first = date(year, month, 1)
    _, last_num = monthrange(year, month)
    today = date.today()

    start_offset = first.weekday()  # Monday = 0
    weeks, week = [], [None] * start_offset
    for d in range(1, last_num + 1):
        day_date = date(year, month, d)
        week.append({
            "date": day_date,
            "date_str": day_date.strftime("%Y-%m-%d"),
            "day": d,
            "data": monthly_data.get(day_date, {}),
            "is_today": day_date == today,
        })
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        week.extend([None] * (7 - len(week)))
        weeks.append(week)
    return weeks


@router.get("/", response_class=HTMLResponse)
async def list_respite(
    request: Request,
    db: Session = Depends(get_db),
    status: str = "all",
    page: int = 1,
    year: int = 0,
    month: int = 0,
):
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month

    monthly_data = get_monthly_data(db, year, month)
    weeks = _build_calendar_weeks(year, month, monthly_data)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    page_size = 20
    query = db.query(RespiteService)
    if status != "all":
        query = query.filter(RespiteService.status == RespiteStatus(status))
    total = query.count()
    records = (
        query.order_by(RespiteService.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = max(1, (total + page_size - 1) // page_size)

    return templates.TemplateResponse("respite/list.html", {
        "request": request,
        "records": records,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status": status,
        "RespiteStatus": RespiteStatus,
        "today": today,
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES[month - 1],
        "weeks": weeks,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_respite_form(request: Request, db: Session = Depends(get_db)):
    members = db.query(Member).filter(Member.is_active == True).order_by(Member.name_zh).all()
    return templates.TemplateResponse("respite/form.html", {
        "request": request,
        "record": None,
        "members": members,
        "SessionType": SessionType,
        "RespiteStatus": RespiteStatus,
        "action": "/respite/",
        "method": "POST",
    })


@router.get("/day-detail", response_class=HTMLResponse)
async def day_detail(
    request: Request,
    db: Session = Depends(get_db),
    date_str: str = "",
    session: str = "morning",
):
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        query_date = date.today()

    if session == "morning":
        sessions_filter = [SessionType.morning, SessionType.full_day]
        session_label = "早上"
    else:
        sessions_filter = [SessionType.afternoon, SessionType.full_day]
        session_label = "下午"

    records = (
        db.query(RespiteService)
        .options(joinedload(RespiteService.member))
        .filter(
            RespiteService.date == query_date,
            RespiteService.session.in_(sessions_filter),
        )
        .order_by(RespiteService.status, RespiteService.id)
        .all()
    )

    approved = [r for r in records if r.status == RespiteStatus.approved]
    pending = [r for r in records if r.status == RespiteStatus.pending]
    remaining = max(0, TOTAL_CAPACITY - len(approved))

    return templates.TemplateResponse("partials/respite_day_detail.html", {
        "request": request,
        "query_date": query_date,
        "session": session,
        "session_label": session_label,
        "approved": approved,
        "pending": pending,
        "remaining": remaining,
        "capacity": TOTAL_CAPACITY,
    })


@router.get("/slots", response_class=HTMLResponse)
async def get_slots(request: Request, db: Session = Depends(get_db), date_str: str = ""):
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        query_date = date.today()
    slots = get_daily_summary(db, query_date)
    return templates.TemplateResponse("partials/respite_slots.html", {
        "request": request,
        "today_slots": slots,
    })


@router.post("/", response_class=HTMLResponse)
async def create_respite(
    request: Request,
    db: Session = Depends(get_db),
    member_id: int = Form(...),
    date_str: str = Form(...),
    session: str = Form(...),
    status: str = Form("pending"),
    notes: str = Form(""),
):
    record = RespiteService(
        member_id=member_id,
        date=datetime.strptime(date_str, "%Y-%m-%d").date(),
        session=SessionType(session),
        status=RespiteStatus(status),
        notes=notes,
    )
    db.add(record)
    db.commit()
    return HTMLResponse(status_code=303, headers={"Location": "/respite/"})


@router.get("/{record_id}/edit", response_class=HTMLResponse)
async def edit_respite_form(request: Request, record_id: int, db: Session = Depends(get_db)):
    record = db.query(RespiteService).filter(RespiteService.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    members = db.query(Member).filter(Member.is_active == True).order_by(Member.name_zh).all()
    return templates.TemplateResponse("respite/form.html", {
        "request": request,
        "record": record,
        "members": members,
        "SessionType": SessionType,
        "RespiteStatus": RespiteStatus,
        "action": f"/respite/{record_id}/edit",
        "method": "POST",
    })


@router.post("/{record_id}/edit", response_class=HTMLResponse)
async def update_respite(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    member_id: int = Form(...),
    date_str: str = Form(...),
    session: str = Form(...),
    status: str = Form("pending"),
    notes: str = Form(""),
):
    record = db.query(RespiteService).filter(RespiteService.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    record.member_id = member_id
    record.date = datetime.strptime(date_str, "%Y-%m-%d").date()
    record.session = SessionType(session)
    record.status = RespiteStatus(status)
    record.notes = notes
    db.commit()
    return HTMLResponse(status_code=303, headers={"Location": "/respite/"})


@router.post("/{record_id}/delete", response_class=HTMLResponse)
async def delete_respite(request: Request, record_id: int, db: Session = Depends(get_db)):
    record = db.query(RespiteService).filter(RespiteService.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return HTMLResponse(status_code=303, headers={"Location": "/respite/"})


@router.post("/{record_id}/approve", response_class=HTMLResponse)
async def approve_respite(request: Request, record_id: int, db: Session = Depends(get_db)):
    record = db.query(RespiteService).filter(RespiteService.id == record_id).first()
    if record:
        record.status = RespiteStatus.approved
        db.commit()
    return HTMLResponse(status_code=303, headers={"Location": "/respite/"})
