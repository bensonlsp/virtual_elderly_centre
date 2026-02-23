import os
import logging
import smtplib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Member, Registration, AttendanceStatus
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")


def mock_send_email(to: str, subject: str, body: str) -> dict:
    """Simulate sending an email by logging it."""
    logger.info("=" * 60)
    logger.info(f"📧 [MOCK EMAIL] To: {to}")
    logger.info(f"📧 [MOCK EMAIL] Subject: {subject}")
    logger.info(f"📧 [MOCK EMAIL] Body:\n{body}")
    logger.info("=" * 60)
    return {
        "success": True,
        "message": f"模擬郵件已成功發送至 {to}",
        "to": to,
        "subject": subject,
        "timestamp": datetime.now().isoformat(),
    }


def send_activity_reminder(member_name: str, activity_name: str, activity_datetime: str) -> dict:
    subject = f"【快樂長者中心】活動提醒：{activity_name}"
    body = f"""親愛的 {member_name} 會員，

您好！提醒您已報名參加以下活動：

活動名稱：{activity_name}
活動時間：{activity_datetime}

如有任何查詢，請致電中心 2xxx-xxxx。

此致
快樂長者中心
"""
    return mock_send_email(TEST_EMAIL, subject, body)


def send_respite_confirmation(member_name: str, date: str, session: str) -> dict:
    subject = f"【快樂長者中心】暫託服務確認"
    body = f"""親愛的 {member_name} 家屬，

您的暫託服務申請已獲批准：

日期：{date}
時段：{session}

如需更改，請提前48小時聯絡中心。

此致
快樂長者中心
"""
    return mock_send_email(TEST_EMAIL, subject, body)


def get_inactive_members(db: Session, days: int = 30) -> list:
    """Find members who haven't participated in any activity in the last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    all_members = db.query(Member).filter(Member.is_active == True).all()
    inactive = []
    for member in all_members:
        recent_attendance = [
            r for r in member.registrations
            if r.attendance == AttendanceStatus.attended
            and r.registered_at >= cutoff
        ]
        if not recent_attendance:
            inactive.append(member)
    return inactive


def generate_care_message(member: Member) -> str:
    """Generate a personalized care message for an inactive member."""
    name = member.name_zh
    messages = [
        f"親愛的 {name}，您好！好久不見，我們非常掛念您。中心最近有不少精彩活動，歡迎您回來參與！",
        f"{name}，我們的職員一直記掛著您。如您身體或生活上有任何需要，請隨時聯絡我們。",
        f"親愛的 {name}，中心最近新增了多項健康講座及興趣班，誠邀您報名參加，讓我們一起度過愉快時光！",
    ]
    import hashlib
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(messages)
    return messages[idx]
