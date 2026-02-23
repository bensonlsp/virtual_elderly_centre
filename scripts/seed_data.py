#!/usr/bin/env python3
"""
Seed script: generates realistic Hong Kong-style sample data.
Run: uv run python scripts/seed_data.py
"""
import sys
import os
import random
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from app.database import SessionLocal, engine
from app.models import (
    Base, Member, Activity, Registration, RespiteService,
    ActivityType, ActivityStatus, AttendanceStatus, SessionType, RespiteStatus
)

fake = Faker(["zh_TW", "en_US"])
Faker.seed(42)
random.seed(42)

# Hong Kong style data
HK_SURNAMES = ["陳", "李", "張", "劉", "黃", "吳", "趙", "鄭", "周", "王",
               "馮", "蔡", "林", "羅", "梁", "韓", "唐", "曾", "許", "何"]
HK_GIVEN_NAMES = ["志明", "家豪", "建華", "英明", "淑英", "美玲", "秀蘭", "玉珍",
                   "文輝", "國雄", "麗芳", "慧珍", "金鳳", "桂蓮", "廣業", "德興",
                   "榮光", "碧霞", "寶珠", "月嫦", "順利", "永康", "敬文", "翠明"]
HK_DISTRICTS = ["觀塘", "九龍城", "深水埗", "旺角", "油尖旺", "黃大仙", "西貢",
                 "沙田", "荃灣", "大埔", "元朗", "屯門", "中西區", "灣仔", "東區", "南區"]
HK_STREET_TYPES = ["道", "街", "路", "里", "徑", "大道"]
ACTIVITY_NAMES = {
    ActivityType.interest_class: [
        "書法班", "水彩畫班", "太極拳班", "粵曲欣賞班", "插花班", "攝影班",
        "手工藝班", "編織班", "瑜伽班", "卡拉OK班", "廚藝班", "棋藝班",
        "普通話班", "電腦入門班", "智能手機應用班", "歌唱班",
    ],
    ActivityType.health_talk: [
        "心臟健康講座", "骨質疏鬆預防講座", "糖尿病管理講座", "血壓管理工作坊",
        "防跌倒技巧講座", "中醫養生講座", "營養飲食講座", "認知障礙症早期識別",
        "視力保健講座", "牙齒護理講座", "睡眠質素改善工作坊", "情緒健康講座",
    ],
    ActivityType.social_event: [
        "新春聯歡晚會", "中秋節慶祝活動", "端午節糉子製作", "旅行參觀活動",
        "長者運動會", "聖誕聯歡會", "生日會", "歌唱表演", "同樂日",
        "義工服務日", "懷舊電影欣賞", "時裝表演", "書展參觀", "佛誕行花街",
    ],
}
LOCATIONS = [
    "活動室A", "活動室B", "多功能廳", "戶外花園", "電腦室", "圖書室",
    "康樂室", "禮堂", "會議室", "烹飪室",
]
HEALTH_CONDITIONS = [
    "高血壓", "糖尿病", "冠心病", "骨質疏鬆", "關節炎", "輕度認知障礙",
    "哮喘", "中風後遺症", "白內障（已手術）", "視力退化", "聽力退化", "行動不便（需拐杖）",
]
SPECIAL_NEEDS = [
    "需要輪椅", "需要助聽器", "對海鮮過敏", "素食", "需低鹽飲食", "需低糖飲食",
    "需要特別照顧", "視力障礙", "需要華語溝通", "行動緩慢，需更多時間",
]
RELATIONS = ["子女", "配偶", "孫子女", "兄弟姊妹", "姪甫女", "親戚"]


def hk_name():
    surname = random.choice(HK_SURNAMES)
    given = random.choice(HK_GIVEN_NAMES)
    return f"{surname}{given}"


def hk_address():
    district = random.choice(HK_DISTRICTS)
    block = random.choice(["A", "B", "C", "D"]) + str(random.randint(1, 9))
    floor = random.randint(1, 30)
    flat = random.randint(1, 20)
    return f"香港{district}XX邨{block}座{floor}樓{flat}號"


def hk_phone():
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    parts = [
        str(random.randint(1, 9)),
        random.choice(letters),
        str(random.randint(10, 99)),
        random.choice(letters),
        str(random.randint(10, 99)),
    ]
    return "".join(parts)


def main():
    print("🌱 開始生成資料...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if data already seeded
    if db.query(Member).count() > 0:
        print("⚠️ 資料已存在，跳過。若需重置請刪除 eldercrm.db 後重新執行。")
        db.close()
        return

    # ── 1. Members ──────────────────────────────────────────────
    print("👥 生成 50 位會員...")
    members = []
    for i in range(50):
        name_zh = hk_name()
        name_en = fake["en_US"].name()
        age_years = random.randint(60, 90)
        dob = date.today() - timedelta(days=age_years * 365 + random.randint(0, 364))
        joined = date.today() - timedelta(days=random.randint(30, 1825))
        num_conditions = random.randint(0, 3)
        health = "、".join(random.sample(HEALTH_CONDITIONS, k=num_conditions)) if num_conditions > 0 else ""
        num_needs = random.randint(0, 2)
        needs = "、".join(random.sample(SPECIAL_NEEDS, k=num_needs)) if num_needs > 0 else ""
        ec = {
            "name": hk_name(),
            "phone": hk_phone(),
            "relation": random.choice(RELATIONS),
        }
        m = Member(
            name_zh=name_zh,
            name_en=name_en,
            dob=dob,
            gender=random.choice(["男", "女", "男", "女", "女"]),
            phone=hk_phone(),
            address=hk_address(),
            health_condition=health,
            special_needs=needs,
            joined_date=joined,
            is_active=random.random() > 0.08,
        )
        m.emergency_contact = ec
        db.add(m)
        members.append(m)

    db.commit()
    for m in members:
        db.refresh(m)
    print(f"  ✅ {len(members)} 位會員已建立")

    # ── 2. Activities ────────────────────────────────────────────
    print("📅 生成 200 筆活動...")
    activities = []
    for i in range(200):
        act_type = random.choice(list(ActivityType))
        name = random.choice(ACTIVITY_NAMES[act_type])
        days_offset = random.randint(-180, 60)
        start_dt = datetime.now().replace(hour=random.choice([9, 10, 14, 15, 16]), minute=0, second=0) + timedelta(days=days_offset)
        duration_hours = random.choice([1, 1.5, 2, 2.5])
        end_dt = start_dt + timedelta(hours=duration_hours)

        if days_offset < -3:
            status = ActivityStatus.completed
        elif days_offset < 0:
            status = random.choice([ActivityStatus.completed, ActivityStatus.ongoing])
        elif days_offset == 0:
            status = ActivityStatus.ongoing
        else:
            status = ActivityStatus.upcoming

        if random.random() < 0.05:
            status = ActivityStatus.cancelled

        a = Activity(
            name=name,
            type=act_type,
            description=f"本中心舉辦的{name}，歡迎各會員積極參與。",
            datetime_start=start_dt,
            datetime_end=end_dt,
            location=random.choice(LOCATIONS),
            capacity=random.choice([10, 15, 20, 25, 30]),
            fee=random.choice([0, 0, 0, 20, 30, 50]),
            status=status,
        )
        db.add(a)
        activities.append(a)

    db.commit()
    for a in activities:
        db.refresh(a)
    print(f"  ✅ {len(activities)} 筆活動已建立")

    # ── 3. Registrations ─────────────────────────────────────────
    print("📋 生成報名記錄...")
    reg_count = 0
    used_pairs = set()
    for activity in activities:
        num_regs = min(random.randint(3, activity.capacity), len(members))
        selected = random.sample(members, num_regs)
        for member in selected:
            pair = (member.id, activity.id)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            if activity.status == ActivityStatus.completed:
                attendance = random.choices(
                    [AttendanceStatus.attended, AttendanceStatus.absent, AttendanceStatus.cancelled],
                    weights=[70, 20, 10]
                )[0]
            elif activity.status == ActivityStatus.ongoing:
                attendance = random.choice([AttendanceStatus.registered, AttendanceStatus.attended])
            elif activity.status == ActivityStatus.cancelled:
                attendance = AttendanceStatus.cancelled
            else:
                attendance = AttendanceStatus.registered

            reg_time = activity.datetime_start - timedelta(days=random.randint(1, 30))
            feedback = None
            if attendance == AttendanceStatus.attended and random.random() < 0.4:
                feedback = random.choice([
                    "活動非常精彩，期待下次！", "導師非常專業，受益良多。",
                    "與同伴互動愉快，感謝中心安排。", "很開心能參加，下次希望能繼續。",
                    "活動安排妥善，十分滿意。", "希望以後多辦類似活動！",
                ])
            r = Registration(
                member_id=member.id,
                activity_id=activity.id,
                registered_at=reg_time,
                attendance=attendance,
                feedback=feedback,
            )
            db.add(r)
            reg_count += 1

    db.commit()
    print(f"  ✅ {reg_count} 筆報名記錄已建立")

    # ── 4. Respite Services ──────────────────────────────────────
    # Capacity: 4 physical slots; full_day counts against both morning and afternoon.
    # Track occupancy as {date: {"morning": n, "afternoon": n}} for approved records.
    CAPACITY = 4
    print("🏥 生成暫託記錄...")
    notes_pool = [
        "", "", "需要陪同服藥", "行動不便，需輪椅", "對花生過敏",
        "家屬下午4時接回", "需要低鹽餐食", "早上視力較差，需特別留意",
    ]
    occupancy = {}  # date -> {"morning": int, "afternoon": int}

    def get_occ(d):
        return occupancy.setdefault(d, {"morning": 0, "afternoon": 0})

    respite_count = 0
    attempts = 0
    used_member_dates = set()
    while respite_count < 40 and attempts < 400:
        attempts += 1
        member = random.choice(members)
        days_offset = random.randint(-14, 14)
        rec_date = date.today() + timedelta(days=days_offset)
        session = random.choice(list(SessionType))
        status = random.choice([RespiteStatus.approved, RespiteStatus.approved,
                                 RespiteStatus.pending, RespiteStatus.rejected])

        # Avoid same member booked twice on the same date
        if (member.id, rec_date) in used_member_dates:
            continue

        # Check capacity for approved records only
        if status == RespiteStatus.approved:
            occ = get_occ(rec_date)
            if session == SessionType.full_day:
                if occ["morning"] >= CAPACITY or occ["afternoon"] >= CAPACITY:
                    continue
                occ["morning"] += 1
                occ["afternoon"] += 1
            elif session == SessionType.morning:
                if occ["morning"] >= CAPACITY:
                    continue
                occ["morning"] += 1
            else:  # afternoon
                if occ["afternoon"] >= CAPACITY:
                    continue
                occ["afternoon"] += 1

        used_member_dates.add((member.id, rec_date))
        r = RespiteService(
            member_id=member.id,
            date=rec_date,
            session=session,
            status=status,
            notes=random.choice(notes_pool),
        )
        db.add(r)
        respite_count += 1

    db.commit()
    print(f"  ✅ {respite_count} 筆暫託記錄已建立")
    db.close()
    print("\n🎉 資料生成完成！可以啟動伺服器：uv run uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
