from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Enum, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
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

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    ref_code = Column(String(12), unique=True, index=True)
    address = Column(String(300), nullable=False)
    landmark = Column(String(300), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    severity = Column(Enum(SeverityEnum), nullable=False)
    status = Column(Enum(StatusEnum), default=StatusEnum.pending)
    description = Column(Text, nullable=True)
    reporter_name = Column(String(100), default="Anonymous")
    reporter_contact = Column(String(50), nullable=True)
    photo_path = Column(String(500), nullable=True)
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_verified = Column(Boolean, default=False)

class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(200))
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
