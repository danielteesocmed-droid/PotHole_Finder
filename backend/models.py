from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Enum, Boolean, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import enum

Base = declarative_base()


class SeverityEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class StatusEnum(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    resolved = "resolved"


def _now():
    return datetime.now(timezone.utc)


class Report(Base):
    __tablename__ = "reports"

    id              = Column(Integer, primary_key=True, index=True)
    ref_code        = Column(String(12), unique=True, index=True, nullable=False)
    address         = Column(String(500), nullable=False)
    landmark        = Column(String(300), nullable=True)
    latitude        = Column(Float, nullable=True)
    longitude       = Column(Float, nullable=True)
    severity        = Column(Enum(SeverityEnum), nullable=False, index=True)
    status          = Column(Enum(StatusEnum), default=StatusEnum.pending, index=True)
    description     = Column(Text, nullable=True)
    reporter_name   = Column(String(100), default="Anonymous")
    reporter_contact = Column(String(100), nullable=True)
    photo_path      = Column(String(500), nullable=True)
    admin_notes     = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), default=_now, index=True)
    updated_at      = Column(DateTime(timezone=True), default=_now)
    is_verified     = Column(Boolean, default=False)

    # Composite index for the most common admin filter (status + severity)
    __table_args__ = (
        Index("ix_reports_status_severity", "status", "severity"),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id              = Column(Integer, primary_key=True)
    username        = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(200))
    full_name       = Column(String(100))
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), default=_now)
