from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import RespiteService, SessionType, RespiteStatus

TOTAL_CAPACITY = 4  # Physical slots available at any one time


def _get_half_session_used(db: Session, query_date: date, half: SessionType) -> int:
    """
    Count occupied slots for a half-session (morning or afternoon).
    Full-day bookings count against both half-sessions.
    """
    full_day_count = (
        db.query(func.count(RespiteService.id))
        .filter(
            RespiteService.date == query_date,
            RespiteService.session == SessionType.full_day,
            RespiteService.status == RespiteStatus.approved,
        )
        .scalar()
    )
    half_count = (
        db.query(func.count(RespiteService.id))
        .filter(
            RespiteService.date == query_date,
            RespiteService.session == half,
            RespiteService.status == RespiteStatus.approved,
        )
        .scalar()
    )
    return full_day_count + half_count


def get_remaining_slots(db: Session, query_date: date, session: SessionType) -> int:
    """Calculate remaining slots for a given date and session type."""
    if session == SessionType.full_day:
        # Full-day needs a free slot in both morning AND afternoon
        morning_used = _get_half_session_used(db, query_date, SessionType.morning)
        afternoon_used = _get_half_session_used(db, query_date, SessionType.afternoon)
        return max(0, min(TOTAL_CAPACITY - morning_used, TOTAL_CAPACITY - afternoon_used))
    elif session == SessionType.morning:
        return max(0, TOTAL_CAPACITY - _get_half_session_used(db, query_date, SessionType.morning))
    else:  # afternoon
        return max(0, TOTAL_CAPACITY - _get_half_session_used(db, query_date, SessionType.afternoon))


def get_daily_summary(db: Session, query_date: date) -> dict:
    """Get slot summary for morning and afternoon on a given date."""
    morning_used = _get_half_session_used(db, query_date, SessionType.morning)
    afternoon_used = _get_half_session_used(db, query_date, SessionType.afternoon)
    return {
        "早上": {
            "capacity": TOTAL_CAPACITY,
            "used": morning_used,
            "remaining": max(0, TOTAL_CAPACITY - morning_used),
        },
        "下午": {
            "capacity": TOTAL_CAPACITY,
            "used": afternoon_used,
            "remaining": max(0, TOTAL_CAPACITY - afternoon_used),
        },
    }


def get_heatmap_data(db: Session, days_past: int = 7, days_future: int = 7) -> list:
    """Get respite usage stats for a heatmap spanning past and future days."""
    from datetime import timedelta, date as dt_date
    from sqlalchemy.orm import joinedload

    today = dt_date.today()
    start_date = today - timedelta(days=days_past)
    end_date = today + timedelta(days=days_future)

    records = (
        db.query(RespiteService)
        .options(joinedload(RespiteService.member))
        .filter(
            RespiteService.date >= start_date,
            RespiteService.date <= end_date,
            RespiteService.status == RespiteStatus.approved,
        )
        .all()
    )

    heatmap = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        display_date = current_date.strftime("%m/%d")
        if current_date == today:
            display_date += "(今)"

        sessions_data = {
            "早上": {"capacity": TOTAL_CAPACITY, "used": 0, "utilization": 0, "conditions": {}},
            "下午": {"capacity": TOTAL_CAPACITY, "used": 0, "utilization": 0, "conditions": {}},
        }

        heatmap.append({
            "date": current_date,
            "date_str": date_str,
            "display": display_date,
            "sessions": sessions_data,
        })
        current_date += timedelta(days=1)

    date_to_idx = {h["date"]: i for i, h in enumerate(heatmap)}

    for record in records:
        idx = date_to_idx.get(record.date)
        if idx is None:
            continue

        condition = record.member.health_condition
        cond_key = condition.strip() if condition and condition.strip() else "一般"
        if len(cond_key) > 15:
            cond_key = cond_key[:12] + "..."

        # Full-day bookings count against both half-sessions
        affected = []
        if record.session == SessionType.full_day:
            affected = ["早上", "下午"]
        elif record.session == SessionType.morning:
            affected = ["早上"]
        else:
            affected = ["下午"]

        for half in affected:
            sess_data = heatmap[idx]["sessions"][half]
            sess_data["used"] += 1
            sess_data["utilization"] = round(sess_data["used"] / sess_data["capacity"] * 100)
            sess_data["conditions"][cond_key] = sess_data["conditions"].get(cond_key, 0) + 1

    return heatmap


def get_days_data(db: Session, dates: list) -> dict:
    """
    Returns {date: {morning: {...}, afternoon: {...}}} for an arbitrary list of dates.
    Full-day bookings count against both half-sessions.
    """
    if not dates:
        return {}

    date_set = set(dates)
    records = (
        db.query(RespiteService)
        .filter(
            RespiteService.date >= min(dates),
            RespiteService.date <= max(dates),
        )
        .all()
    )

    raw = {
        d: {"morning": {"approved": 0, "pending": 0}, "afternoon": {"approved": 0, "pending": 0}}
        for d in dates
    }
    for rec in records:
        if rec.date not in date_set:
            continue
        halves = (
            ["morning", "afternoon"] if rec.session == SessionType.full_day
            else ["morning"] if rec.session == SessionType.morning
            else ["afternoon"]
        )
        for hs in halves:
            if rec.status == RespiteStatus.approved:
                raw[rec.date][hs]["approved"] += 1
            elif rec.status == RespiteStatus.pending:
                raw[rec.date][hs]["pending"] += 1

    result = {}
    for d, data in raw.items():
        result[d] = {}
        for hs in ("morning", "afternoon"):
            ac = data[hs]["approved"]
            result[d][hs] = {
                "approved_count": ac,
                "pending_count": data[hs]["pending"],
                "remaining": max(0, TOTAL_CAPACITY - ac),
                "capacity": TOTAL_CAPACITY,
            }
    return result


def get_monthly_data(db: Session, year: int, month: int) -> dict:
    """
    Returns {date: {morning: {...}, afternoon: {...}}} for every day in the month.
    Only stores counts (not full member objects) – detail is fetched on demand.
    Full-day bookings count against both morning and afternoon.
    """
    from calendar import monthrange
    from datetime import date

    first_day = date(year, month, 1)
    _, last_num = monthrange(year, month)
    last_day = date(year, month, last_num)

    records = (
        db.query(RespiteService)
        .filter(
            RespiteService.date >= first_day,
            RespiteService.date <= last_day,
        )
        .all()
    )

    raw: dict = {}
    for d in range(1, last_num + 1):
        raw[date(year, month, d)] = {
            "morning": {"approved": 0, "pending": 0},
            "afternoon": {"approved": 0, "pending": 0},
        }

    for rec in records:
        halves = (
            ["morning", "afternoon"] if rec.session == SessionType.full_day
            else ["morning"] if rec.session == SessionType.morning
            else ["afternoon"]
        )
        for hs in halves:
            if rec.status == RespiteStatus.approved:
                raw[rec.date][hs]["approved"] += 1
            elif rec.status == RespiteStatus.pending:
                raw[rec.date][hs]["pending"] += 1

    result = {}
    for d, data in raw.items():
        result[d] = {}
        for hs in ("morning", "afternoon"):
            ac = data[hs]["approved"]
            result[d][hs] = {
                "approved_count": ac,
                "pending_count": data[hs]["pending"],
                "remaining": max(0, TOTAL_CAPACITY - ac),
                "capacity": TOTAL_CAPACITY,
            }
    return result
