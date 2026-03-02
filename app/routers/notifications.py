from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailDraft, EmailDraftStatus, SystemNotification
from app.services.email import run_inactive_scan, send_email

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_page_data(db: Session, status_filter: str = "all"):
    notifications = (
        db.query(SystemNotification)
        .order_by(SystemNotification.created_at.desc())
        .limit(10)
        .all()
    )
    unread_count = db.query(SystemNotification).filter(
        SystemNotification.is_read == False
    ).count()

    q = db.query(EmailDraft)
    if status_filter == "draft":
        q = q.filter(EmailDraft.status == EmailDraftStatus.draft)
    elif status_filter == "approved":
        q = q.filter(EmailDraft.status == EmailDraftStatus.approved)
    elif status_filter == "sent":
        q = q.filter(EmailDraft.status == EmailDraftStatus.sent)

    drafts = q.order_by(EmailDraft.created_at.desc()).all()

    counts = {
        "all": db.query(EmailDraft).count(),
        "draft": db.query(EmailDraft).filter(EmailDraft.status == EmailDraftStatus.draft).count(),
        "approved": db.query(EmailDraft).filter(EmailDraft.status == EmailDraftStatus.approved).count(),
        "sent": db.query(EmailDraft).filter(EmailDraft.status == EmailDraftStatus.sent).count(),
        "failed": db.query(EmailDraft).filter(EmailDraft.status == EmailDraftStatus.failed).count(),
    }

    return notifications, unread_count, drafts, counts


@router.get("/", response_class=HTMLResponse)
async def notifications_page(
    request: Request,
    status: str = "all",
    db: Session = Depends(get_db),
):
    notifications, unread_count, drafts, counts = _get_page_data(db, status)
    return templates.TemplateResponse("notifications.html", {
        "request": request,
        "notifications": notifications,
        "unread_count": unread_count,
        "drafts": drafts,
        "counts": counts,
        "status_filter": status,
    })


@router.post("/scan", response_class=HTMLResponse)
async def trigger_scan(request: Request, db: Session = Depends(get_db)):
    count = run_inactive_scan(db)
    notifications, unread_count, drafts, counts = _get_page_data(db)
    return templates.TemplateResponse("notifications.html", {
        "request": request,
        "notifications": notifications,
        "unread_count": unread_count,
        "drafts": drafts,
        "counts": counts,
        "status_filter": "all",
        "scan_result": count,
    })


@router.get("/drafts/{draft_id}/form", response_class=HTMLResponse)
async def draft_edit_form(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    return templates.TemplateResponse("partials/email_draft_detail.html", {
        "request": request,
        "draft": draft,
    })


@router.post("/drafts/{draft_id}/edit", response_class=HTMLResponse)
async def edit_draft(
    request: Request,
    draft_id: int,
    subject: str = Form(...),
    body: str = Form(...),
    recipient_email: str = Form(...),
    db: Session = Depends(get_db),
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if draft and draft.status == EmailDraftStatus.draft:
        draft.subject = subject
        draft.body = body
        draft.recipient_email = recipient_email
        db.commit()
        db.refresh(draft)

    return templates.TemplateResponse("partials/email_draft_detail.html", {
        "request": request,
        "draft": draft,
        "saved": True,
    })


@router.post("/drafts/{draft_id}/approve", response_class=HTMLResponse)
async def approve_draft(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if draft and draft.status == EmailDraftStatus.draft:
        draft.status = EmailDraftStatus.approved
        draft.scheduled_at = datetime.now() + timedelta(minutes=5)
        db.commit()
        db.refresh(draft)

    return templates.TemplateResponse("partials/email_draft_detail.html", {
        "request": request,
        "draft": draft,
        "approved": True,
    })


@router.post("/drafts/{draft_id}/send-now", response_class=HTMLResponse)
async def send_now(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    sent = False
    if draft and draft.status in (EmailDraftStatus.draft, EmailDraftStatus.approved):
        success = send_email(
            to=draft.recipient_email,
            subject=draft.subject,
            body=draft.body,
        )
        if success:
            draft.status = EmailDraftStatus.sent
            draft.sent_at = datetime.now()
            db.commit()
            db.refresh(draft)
            sent = True

    return templates.TemplateResponse("partials/email_draft_detail.html", {
        "request": request,
        "draft": draft,
        "sent_now": sent,
    })


@router.post("/drafts/{draft_id}/delete", response_class=HTMLResponse)
async def delete_draft(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if draft:
        db.delete(draft)
        db.commit()
    # Return empty response – HTMX will remove the row
    return HTMLResponse("")


@router.post("/read/{notif_id}", response_class=HTMLResponse)
async def mark_read(
    request: Request,
    notif_id: int,
    db: Session = Depends(get_db),
):
    notif = db.query(SystemNotification).filter(SystemNotification.id == notif_id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return HTMLResponse("")


@router.post("/read-all", response_class=HTMLResponse)
async def mark_all_read(request: Request, db: Session = Depends(get_db)):
    db.query(SystemNotification).filter(
        SystemNotification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return HTMLResponse("")
