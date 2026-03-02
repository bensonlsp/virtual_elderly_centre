import os
import base64
import logging
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session

from app.models import (
    Member, Registration, AttendanceStatus,
    EmailDraft, EmailDraftStatus, SystemNotification,
)

logger = logging.getLogger(__name__)

CENTRE_NAME = os.getenv("CENTRE_NAME", "快樂長者中心")
CENTRE_PHONE = os.getenv("CENTRE_PHONE", "2xxx-xxxx")

# ── Email templates ────────────────────────────────────────────────────────────

TEMPLATES = {
    "new_member": {
        "subject": f"【{CENTRE_NAME}】歡迎加入，期待與您相遇！",
        "body": """\
親愛的 {name}，

您好！感謝您成為{centre}的一員。

我們中心定期舉辦各類活動，包括興趣班、健康講座及社交聚會，希望您能夠積極參與，與中心的朋友們共度愉快時光。

如您有任何問題或需要協助，歡迎隨時聯絡我們：
電話：{phone}

期待在中心與您相見！

此致
{centre}職員團隊
""",
    },
    "health_care": {
        "subject": f"【{CENTRE_NAME}】健康關懷問候",
        "body": """\
親愛的 {name}，

您好！我們的職員一直掛念著您的健康狀況。

中心近期舉辦了多場健康講座及保健活動，內容涵蓋慢性病管理、防跌技巧及營養飲食等，相信對您會有所裨益。

歡迎您回來中心參加活動，與我們的醫護義工及職員交流。如有任何不適或需要，請隨時聯絡我們：
電話：{phone}

您的健康是我們最大的關心！

此致
{centre}職員團隊
""",
    },
    "long_absent": {
        "subject": f"【{CENTRE_NAME}】我們非常掛念您！",
        "body": """\
親愛的 {name}，

您好！好久不見，中心的職員和朋友們都非常想念您。

您上次參加活動已經有一段時間了，我們希望您一切安好。中心近期新增了不少精彩活動，誠邀您回來與大家重聚！

如您身體或生活上有任何困難，我們很樂意為您提供協助，請隨時聯絡我們：
電話：{phone}

期待盡快與您重逢！

此致
{centre}職員團隊
""",
    },
    "general": {
        "subject": f"【{CENTRE_NAME}】中心關懷問候",
        "body": """\
親愛的 {name}，

您好！感謝您一直以來對{centre}的支持。

我們中心持續舉辦各類活動，歡迎您隨時回來參與，與中心的朋友共度美好時光。

如有任何查詢，請致電：{phone}

祝您身體健康、生活愉快！

此致
{centre}職員團隊
""",
    },
}


def select_template(member: Member) -> str:
    """Pick the most suitable template key based on member profile."""
    today = date.today()
    joined = member.joined_date or today

    # New member: joined within 6 months
    if (today - joined).days <= 180:
        return "new_member"

    # Has attended activities before but gone quiet → long_absent
    ever_attended = any(
        r.attendance == AttendanceStatus.attended
        for r in member.registrations
    )
    if ever_attended:
        return "long_absent"

    # Has health conditions → health care
    if member.health_condition and member.health_condition.strip():
        return "health_care"

    return "general"


def _render_template(template_key: str, member: Member) -> tuple[str, str]:
    """Return (subject, body) filled with member data."""
    tmpl = TEMPLATES[template_key]
    ctx = {
        "name": member.name_zh,
        "centre": CENTRE_NAME,
        "phone": CENTRE_PHONE,
    }
    subject = tmpl["subject"]
    body = tmpl["body"].format(**ctx)
    return subject, body


# ── Gmail API ──────────────────────────────────────────────────────────────────

def _build_gmail_service():
    """Build an authenticated Gmail API service using stored OAuth2 tokens."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GMAIL_REFRESH_TOKEN"),
        client_id=os.getenv("GMAIL_CLIENT_ID"),
        client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send email via Gmail API. Returns True on success."""
    client_id = os.getenv("GMAIL_CLIENT_ID")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    test_recipient = os.getenv("TEST_RECIPIENT", "")

    if not client_id or not refresh_token:
        logger.warning("Gmail API credentials not set – logging mock email")
        logger.info("=" * 60)
        logger.info(f"[MOCK EMAIL] To: {to}")
        logger.info(f"[MOCK EMAIL] Subject: {subject}")
        logger.info(f"[MOCK EMAIL] Body:\n{body}")
        logger.info("=" * 60)
        return True  # treat mock as success so workflow proceeds

    # Always redirect to test recipient during testing
    actual_to = test_recipient if test_recipient else to

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.getenv("GMAIL_USER", "me")
    msg["To"] = actual_to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        service = _build_gmail_service()
        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        logger.info(f"Gmail API: sent → {actual_to} | {subject}")
        return True
    except Exception as e:
        logger.error(f"Gmail API send failed: {e}")
        return False


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

def get_inactive_members(db: Session, days: int = 14) -> list[Member]:
    """Active members with no attended activity in the last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    all_members = db.query(Member).filter(Member.is_active == True).all()
    inactive = []
    for member in all_members:
        recent = [
            r for r in member.registrations
            if r.attendance == AttendanceStatus.attended
            and r.registered_at >= cutoff
        ]
        if not recent:
            inactive.append(member)
    return inactive


def run_inactive_scan(db: Session) -> int:
    """
    Scan for inactive members and create EmailDraft records.
    Returns the number of new drafts created.
    """
    today = datetime.now()
    # batch_id = Monday of the current week, e.g. scan_2026-02-23
    monday = today - timedelta(days=today.weekday())
    batch_id = f"scan_{monday.strftime('%Y-%m-%d')}"

    # Avoid duplicate scans in the same week
    existing = db.query(EmailDraft).filter(
        EmailDraft.batch_id == batch_id
    ).first()
    if existing:
        logger.info(f"Scan {batch_id} already run – skipping")
        return 0

    inactive = get_inactive_members(db, days=14)
    if not inactive:
        logger.info("No inactive members found")
        return 0

    drafts_created = 0
    for member in inactive:
        tmpl_key = select_template(member)
        subject, body = _render_template(tmpl_key, member)
        test_recipient = os.getenv("TEST_RECIPIENT", "")
        recipient = test_recipient if test_recipient else (member.phone or "")

        draft = EmailDraft(
            member_id=member.id,
            subject=subject,
            body=body,
            template_type=tmpl_key,
            status=EmailDraftStatus.draft,
            recipient_email=recipient,
            batch_id=batch_id,
        )
        db.add(draft)
        drafts_created += 1

    # Create a system notification for staff
    notif = SystemNotification(
        title=f"電郵草稿已生成（{batch_id}）",
        message=(
            f"系統已為 {drafts_created} 位兩週未出席的會員生成關懷電郵草稿，"
            f"請前往「通知管理」審閱並批准發送。"
        ),
        notif_type="email_scan",
    )
    db.add(notif)
    db.commit()

    logger.info(f"Scan {batch_id}: created {drafts_created} drafts")
    return drafts_created


def process_scheduled_sends(db: Session) -> int:
    """
    Send any approved drafts whose scheduled_at has passed.
    Returns the number of emails sent.
    """
    now = datetime.now()
    due_drafts = db.query(EmailDraft).filter(
        EmailDraft.status == EmailDraftStatus.approved,
        EmailDraft.scheduled_at <= now,
    ).all()

    sent_count = 0
    for draft in due_drafts:
        success = send_email(
            to=draft.recipient_email,
            subject=draft.subject,
            body=draft.body,
        )
        if success:
            draft.status = EmailDraftStatus.sent
            draft.sent_at = now
            sent_count += 1
        else:
            draft.status = EmailDraftStatus.failed

    if sent_count > 0:
        notif = SystemNotification(
            title=f"電郵已成功發送（{sent_count} 封）",
            message=f"系統已完成發送 {sent_count} 封關懷電郵至測試信箱。",
            notif_type="email_sent",
        )
        db.add(notif)

    db.commit()
    return sent_count
