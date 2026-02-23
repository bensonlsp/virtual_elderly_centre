import json
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, Boolean,
    ForeignKey, Enum as SAEnum, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class ActivityType(str, enum.Enum):
    interest_class = "興趣班"
    health_talk = "健康講座"
    social_event = "社交活動"


class ActivityStatus(str, enum.Enum):
    upcoming = "即將舉行"
    ongoing = "進行中"
    completed = "已完成"
    cancelled = "已取消"


class AttendanceStatus(str, enum.Enum):
    registered = "已報名"
    attended = "已出席"
    absent = "缺席"
    cancelled = "已取消"


class SessionType(str, enum.Enum):
    full_day = "全日"
    morning = "早上"
    afternoon = "下午"


class RespiteStatus(str, enum.Enum):
    pending = "待處理"
    approved = "已批准"
    rejected = "已拒絕"


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    name_zh = Column(String(50), nullable=False, index=True)
    name_en = Column(String(100))
    dob = Column(Date)
    gender = Column(String(10), default="未知")
    phone = Column(String(20), index=True)
    address = Column(Text)
    health_condition = Column(Text)
    special_needs = Column(Text)
    _emergency_contact = Column("emergency_contact", Text)
    joined_date = Column(Date, default=datetime.now)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    registrations = relationship("Registration", back_populates="member", cascade="all, delete-orphan")
    respite_services = relationship("RespiteService", back_populates="member", cascade="all, delete-orphan")

    @property
    def emergency_contact(self):
        if self._emergency_contact:
            return json.loads(self._emergency_contact)
        return {}

    @emergency_contact.setter
    def emergency_contact(self, value):
        self._emergency_contact = json.dumps(value, ensure_ascii=False)

    @property
    def age(self):
        if self.dob:
            today = datetime.now().date()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    type = Column(SAEnum(ActivityType), nullable=False)
    description = Column(Text)
    datetime_start = Column(DateTime, nullable=False)
    datetime_end = Column(DateTime)
    location = Column(String(200))
    capacity = Column(Integer, default=20)
    fee = Column(Float, default=0.0)
    status = Column(SAEnum(ActivityStatus), default=ActivityStatus.upcoming)
    created_at = Column(DateTime, default=datetime.now)

    registrations = relationship("Registration", back_populates="activity", cascade="all, delete-orphan")

    @property
    def registered_count(self):
        return len([r for r in self.registrations if r.attendance != AttendanceStatus.cancelled])

    @property
    def remaining_slots(self):
        return max(0, self.capacity - self.registered_count)


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    registered_at = Column(DateTime, default=datetime.now)
    attendance = Column(SAEnum(AttendanceStatus), default=AttendanceStatus.registered)
    feedback = Column(Text)

    member = relationship("Member", back_populates="registrations")
    activity = relationship("Activity", back_populates="registrations")


class RespiteService(Base):
    __tablename__ = "respite_services"

    TOTAL_CAPACITY = 4  # Physical slots; full_day counts against both morning and afternoon

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    session = Column(SAEnum(SessionType), nullable=False)
    status = Column(SAEnum(RespiteStatus), default=RespiteStatus.pending)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    member = relationship("Member", back_populates="respite_services")
