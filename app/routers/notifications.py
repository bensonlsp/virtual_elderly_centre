import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.email import (
    mock_send_email, send_activity_reminder, send_respite_confirmation,
    get_inactive_members, generate_care_message
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    inactive = get_inactive_members(db, days=30)
    care_messages = [(m, generate_care_message(m)) for m in inactive]
    return templates.TemplateResponse("notifications.html", {
        "request": request,
        "care_messages": care_messages,
        "test_email": os.getenv("TEST_EMAIL", "test@example.com"),
    })


@router.post("/send-care-batch", response_class=HTMLResponse)
async def send_care_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    inactive = get_inactive_members(db, days=30)
    results = []

    def send_all():
        for member in inactive:
            msg = generate_care_message(member)
            result = mock_send_email(
                to=os.getenv("TEST_EMAIL", "test@example.com"),
                subject=f"【關懷郵件】{member.name_zh} 您好",
                body=msg,
            )
            results.append(result)

    background_tasks.add_task(send_all)

    return templates.TemplateResponse("partials/notification_toast.html", {
        "request": request,
        "message": f"已排程發送 {len(inactive)} 封關懷郵件！請查看伺服器日誌確認發送詳情。",
        "success": True,
    })


@router.post("/send-test", response_class=HTMLResponse)
async def send_test_email(
    request: Request,
    background_tasks: BackgroundTasks,
    subject: str = Form("測試郵件"),
    body: str = Form("這是一封來自長者中心 CRM 的測試郵件。"),
):
    def _send():
        mock_send_email(os.getenv("TEST_EMAIL", "test@example.com"), subject, body)

    background_tasks.add_task(_send)

    return templates.TemplateResponse("partials/notification_toast.html", {
        "request": request,
        "message": f"模擬郵件已發送至 {os.getenv('TEST_EMAIL')}！請查看伺服器日誌。",
        "success": True,
    })
