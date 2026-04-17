from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from models import SeverityEnum, StatusEnum

class ReportCreate(BaseModel):
    address: str
    landmark: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    severity: SeverityEnum
    description: Optional[str] = None
    reporter_name: Optional[str] = "Anonymous"
    reporter_contact: Optional[str] = None

class ReportOut(BaseModel):
    id: int
    ref_code: str
    address: str
    landmark: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    severity: SeverityEnum
    status: StatusEnum
    description: Optional[str]
    reporter_name: str
    photo_path: Optional[str]
    admin_notes: Optional[str]
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReportUpdate(BaseModel):
    status: Optional[StatusEnum] = None
    admin_notes: Optional[str] = None
    is_verified: Optional[bool] = None

class AdminLogin(BaseModel):
    username: str
    password: str

class StatsOut(BaseModel):
    total: int
    pending: int
    in_progress: int
    resolved: int
    high: int
    medium: int
    low: int
    verified: int
