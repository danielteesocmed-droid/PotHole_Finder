from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models import SeverityEnum, StatusEnum


class ReportCreate(BaseModel):
    address:          str            = Field(..., max_length=500)
    landmark:         Optional[str]  = Field(None, max_length=300)
    latitude:         Optional[float] = None
    longitude:        Optional[float] = None
    severity:         SeverityEnum
    description:      Optional[str]  = Field(None, max_length=1000)
    reporter_name:    Optional[str]  = Field("Anonymous", max_length=100)
    reporter_contact: Optional[str]  = Field(None, max_length=100)


class ReportOut(BaseModel):
    id:           int
    ref_code:     str
    address:      str
    landmark:     Optional[str]
    latitude:     Optional[float]
    longitude:    Optional[float]
    severity:     SeverityEnum
    status:       StatusEnum
    description:  Optional[str]
    reporter_name: str
    # reporter_contact intentionally excluded from public output
    photo_path:   Optional[str]
    admin_notes:  Optional[str]
    is_verified:  bool
    created_at:   datetime
    updated_at:   datetime

    class Config:
        from_attributes = True


class ReportUpdate(BaseModel):
    status:      Optional[StatusEnum] = None
    admin_notes: Optional[str]        = Field(None, max_length=2000)
    is_verified: Optional[bool]       = None


class AdminLogin(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=200)


class StatsOut(BaseModel):
    total:       int
    pending:     int
    in_progress: int
    resolved:    int
    high:        int
    medium:      int
    low:         int
    verified:    int


class PaginatedReports(BaseModel):
    total: int
    skip:  int
    limit: int
    items: list[ReportOut]
