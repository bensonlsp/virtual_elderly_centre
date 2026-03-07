import csv
import io
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Member

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def list_members(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    status: str = "all",
    page: int = 1,
):
    page_size = 20
    query = db.query(Member)
    if q:
        query = query.filter(
            or_(
                Member.name_zh.contains(q),
                Member.name_en.contains(q),
                Member.phone.contains(q),
            )
        )
    if status == "active":
        query = query.filter(Member.is_active == True)
    elif status == "inactive":
        query = query.filter(Member.is_active == False)

    total = query.count()
    members = query.order_by(Member.name_zh).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size

    is_htmx = request.headers.get("HX-Request")
    if is_htmx:
        return templates.TemplateResponse("partials/members_table.html", {
            "request": request,
            "members": members,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "q": q,
            "status": status,
        })

    return templates.TemplateResponse("members/list.html", {
        "request": request,
        "members": members,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "status": status,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_member_form(request: Request):
    return templates.TemplateResponse("members/form.html", {
        "request": request,
        "member": None,
        "action": "/members/",
        "method": "POST",
    })


@router.post("/", response_class=HTMLResponse)
async def create_member(
    request: Request,
    db: Session = Depends(get_db),
    name_zh: str = Form(...),
    name_en: str = Form(""),
    dob: Optional[str] = Form(None),
    gender: str = Form("未知"),
    phone: str = Form(""),
    address: str = Form(""),
    health_condition: str = Form(""),
    special_needs: str = Form(""),
    ec_name: str = Form(""),
    ec_phone: str = Form(""),
    ec_relation: str = Form(""),
    notes: str = Form(""),
):
    from datetime import date
    dob_date = datetime.strptime(dob, "%Y-%m-%d").date() if dob else None
    member = Member(
        name_zh=name_zh,
        name_en=name_en,
        dob=dob_date,
        gender=gender,
        phone=phone,
        address=address,
        health_condition=health_condition,
        special_needs=special_needs,
        notes=notes,
        joined_date=date.today(),
    )
    member.emergency_contact = {"name": ec_name, "phone": ec_phone, "relation": ec_relation}
    db.add(member)
    db.commit()
    db.refresh(member)
    return HTMLResponse(
        status_code=303,
        headers={"Location": f"/members/{member.id}"},
    )


@router.get("/{member_id}", response_class=HTMLResponse)
async def member_detail(request: Request, member_id: int, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return templates.TemplateResponse("members/detail.html", {
        "request": request,
        "member": member,
    })


@router.get("/{member_id}/edit", response_class=HTMLResponse)
async def edit_member_form(request: Request, member_id: int, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return templates.TemplateResponse("members/form.html", {
        "request": request,
        "member": member,
        "action": f"/members/{member_id}/edit",
        "method": "POST",
    })


@router.post("/{member_id}/edit", response_class=HTMLResponse)
async def update_member(
    request: Request,
    member_id: int,
    db: Session = Depends(get_db),
    name_zh: str = Form(...),
    name_en: str = Form(""),
    dob: Optional[str] = Form(None),
    gender: str = Form("未知"),
    phone: str = Form(""),
    address: str = Form(""),
    health_condition: str = Form(""),
    special_needs: str = Form(""),
    ec_name: str = Form(""),
    ec_phone: str = Form(""),
    ec_relation: str = Form(""),
    is_active: Optional[str] = Form(None),
    notes: str = Form(""),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    member.name_zh = name_zh
    member.name_en = name_en
    member.dob = datetime.strptime(dob, "%Y-%m-%d").date() if dob else None
    member.gender = gender
    member.phone = phone
    member.address = address
    member.health_condition = health_condition
    member.special_needs = special_needs
    member.notes = notes
    member.is_active = is_active == "on"
    member.emergency_contact = {"name": ec_name, "phone": ec_phone, "relation": ec_relation}
    db.commit()
    return HTMLResponse(
        status_code=303,
        headers={"Location": f"/members/{member_id}"},
    )


@router.post("/import", response_class=HTMLResponse)
async def import_members(
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    from datetime import date
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handle BOM from Excel
    except UnicodeDecodeError:
        text = content.decode("big5", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    imported, skipped, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):  # row 1 is header
        name_zh = row.get("name_zh", "").strip()
        if not name_zh:
            errors.append(f"第 {i} 行：缺少中文姓名，已略過")
            skipped += 1
            continue

        # Skip duplicate by phone or name_zh
        phone = row.get("phone", "").strip()
        existing = db.query(Member).filter(Member.name_zh == name_zh).first()
        if not existing and phone:
            existing = db.query(Member).filter(Member.phone == phone).first()
        if existing:
            skipped += 1
            continue

        def parse_date(val):
            val = val.strip() if val else ""
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
            return None

        def s(key):
            return (row.get(key) or "").strip()

        member = Member(
            name_zh=name_zh,
            name_en=s("name_en"),
            dob=parse_date(s("dob")),
            gender=s("gender") or "未知",
            phone=phone,
            address=s("address"),
            health_condition=s("health_condition"),
            special_needs=s("special_needs"),
            notes=s("notes"),
            joined_date=parse_date(s("joined_date")) or date.today(),
        )
        member.emergency_contact = {
            "name": s("ec_name"),
            "phone": s("ec_phone"),
            "relation": s("ec_relation"),
        }
        db.add(member)
        imported += 1

    db.commit()

    return templates.TemplateResponse("partials/import_result.html", {
        "request": request,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    })


@router.post("/{member_id}/delete", response_class=HTMLResponse)
async def delete_member(request: Request, member_id: int, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    return HTMLResponse(status_code=303, headers={"Location": "/members/"})
