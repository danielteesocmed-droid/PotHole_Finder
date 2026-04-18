import os, uuid, random, string
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case
from PIL import Image
import aiofiles

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import get_db, init_db
from models import Report, AdminUser, SeverityEnum, StatusEnum
from schemas import ReportOut, ReportUpdate, AdminLogin, StatsOut, PaginatedReports
from auth import verify_password, create_access_token, decode_token
from notifications import notify_report_submitted, notify_status_changed

# ── Config ────────────────────────────────────────────────────────────────────
MAX_PHOTO_BYTES   = 15 * 1024 * 1024
ALLOWED_MIMETYPES   = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
NEARBY_RADIUS_KM    = float(os.getenv("NEARBY_RADIUS_KM", "0.05"))  # 50 metres
ALLOWED_ORIGINS   = os.getenv("ALLOWED_ORIGINS", "*").split(",")

BASE_DIR     = Path(__file__).parent.parent
UPLOAD_DIR   = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
FRONTEND_DIR = BASE_DIR / "frontend" / "public"

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])

app = FastAPI(title="PotHole Finder API", version="1.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static",  StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Helpers ───────────────────────────────────────────────────────────────────
def gen_ref_code(db: Session) -> str:
    for _ in range(10):
        code = "PH-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
        if not db.query(Report).filter_by(ref_code=code).first():
            return code
    raise RuntimeError("Could not generate a unique reference code.")


def check_nearby_duplicate(db: Session, lat: float, lng: float, radius_km: float) -> bool:
    """Return True if an open report exists within radius_km of the given coordinates."""
    import math
    reports = db.query(Report).filter(
        Report.latitude.isnot(None),
        Report.longitude.isnot(None),
        Report.status != StatusEnum.resolved,
    ).all()
    for r in reports:
        dlat = math.radians(r.latitude - lat)
        dlng = math.radians(r.longitude - lng)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat)) * math.cos(math.radians(r.latitude)) *
             math.sin(dlng / 2) ** 2)
        km = 6371 * 2 * math.asin(math.sqrt(a))
        if km <= radius_km:
            return True
    return False


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> AdminUser:
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    admin = db.query(AdminUser).filter_by(username=payload.get("sub")).first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin not found or inactive")
    return admin


async def save_photo(file: UploadFile) -> str:
    if file.content_type and file.content_type not in ALLOWED_MIMETYPES:
        raise HTTPException(status_code=400, detail="Invalid image type. Allowed: JPEG, PNG, WEBP, HEIC.")

    # Read with size guard
    content = b""
    async for chunk in file:
        content += chunk
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Photo too large. Maximum size is {MAX_PHOTO_BYTES // (1024*1024)} MB."
            )

    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_tmp"
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)

    try:
        # Verify it's a real image (rejects disguised HTML/SVG/etc.)
        img = Image.open(tmp_path)
        img.verify()
        img = Image.open(tmp_path)  # re-open after verify
        img.thumbnail((1200, 1200), Image.LANCZOS)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        final_name = f"{uuid.uuid4().hex}.jpg"
        final_path = UPLOAD_DIR / final_name
        img.save(final_path, "JPEG", quality=82, optimize=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process image: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    return final_name


def _now():
    return datetime.now(timezone.utc)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()


# ── Frontend Serving ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return HTMLResponse(content=(FRONTEND_DIR / "index.html").read_text(), status_code=200)


@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    return HTMLResponse(content=(FRONTEND_DIR / "admin.html").read_text(), status_code=200)


# ── Public Routes ─────────────────────────────────────────────────────────────
@app.post("/api/reports", response_model=ReportOut, status_code=201)
@limiter.limit("10/minute")          # max 10 submissions per IP per minute
async def create_report(
    request:          Request,
    address:          str                  = Form(..., max_length=500),
    landmark:         Optional[str]        = Form(None, max_length=300),
    latitude:         Optional[float]      = Form(None),
    longitude:        Optional[float]      = Form(None),
    severity:         SeverityEnum         = Form(...),
    description:      Optional[str]        = Form(None, max_length=1000),
    reporter_name:    Optional[str]        = Form("Anonymous", max_length=100),
    reporter_contact: Optional[str]        = Form(None, max_length=100),
    photo:            Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    photo_path = None
    if photo and photo.filename:
        photo_path = await save_photo(photo)

    # Duplicate detection — warn if an open report exists within 50 m
    if latitude and longitude:
        if check_nearby_duplicate(db, latitude, longitude, NEARBY_RADIUS_KM):
            raise HTTPException(
                status_code=409,
                detail="A pothole has already been reported very close to this location. "
                       "Check existing reports or use a more specific address."
            )

    report = Report(
        ref_code=gen_ref_code(db),
        address=address,
        landmark=landmark,
        latitude=latitude,
        longitude=longitude,
        severity=severity,
        description=description,
        reporter_name=reporter_name or "Anonymous",
        reporter_contact=reporter_contact,
        photo_path=photo_path,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    # Non-blocking email confirmation (fails silently if RESEND_API_KEY not set)
    await notify_report_submitted(report.ref_code, report.address, report.reporter_contact)
    return report


@app.get("/api/reports", response_model=PaginatedReports)
@limiter.limit("60/minute")
async def list_reports(
    request:  Request,
    severity: Optional[str] = None,
    status:   Optional[str] = None,
    skip:     int           = 0,
    limit:    int           = 50,
    db: Session = Depends(get_db),
):
    limit = min(limit, 100)
    q = db.query(Report)
    if severity and severity in ("low", "medium", "high"):
        q = q.filter(Report.severity == severity)
    if status and status in ("pending", "in_progress", "resolved"):
        q = q.filter(Report.status == status)
    total = q.count()
    items = q.order_by(desc(Report.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@app.get("/api/reports/{ref_code}", response_model=ReportOut)
@limiter.limit("30/minute")
async def get_report(request: Request, ref_code: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.ref_code == ref_code.upper()).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/stats", response_model=StatsOut)
@limiter.limit("30/minute")
async def get_stats(request: Request, db: Session = Depends(get_db)):
    total = db.query(func.count(Report.id)).scalar() or 0
    rows = db.query(
        func.sum(case((Report.status == StatusEnum.pending,      1), else_=0)),
        func.sum(case((Report.status == StatusEnum.in_progress,  1), else_=0)),
        func.sum(case((Report.status == StatusEnum.resolved,     1), else_=0)),
        func.sum(case((Report.severity == SeverityEnum.high,     1), else_=0)),
        func.sum(case((Report.severity == SeverityEnum.medium,   1), else_=0)),
        func.sum(case((Report.severity == SeverityEnum.low,      1), else_=0)),
        func.sum(case((Report.is_verified == True,               1), else_=0)),
    ).one()
    pending, in_progress, resolved, high, medium, low, verified = (int(v or 0) for v in rows)
    return {
        "total": total, "pending": pending, "in_progress": in_progress,
        "resolved": resolved, "high": high, "medium": medium,
        "low": low, "verified": verified,
    }


# ── Admin Routes ──────────────────────────────────────────────────────────────
@app.post("/api/admin/login")
@limiter.limit("10/minute")          # brute-force protection
async def admin_login(request: Request, body: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter_by(username=body.username).first()
    if not admin or not verify_password(body.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.username})
    return {"access_token": token, "token_type": "bearer", "full_name": admin.full_name}


@app.get("/api/admin/reports", response_model=PaginatedReports)
async def admin_list_reports(
    severity: Optional[str] = None,
    status:   Optional[str] = None,
    search:   Optional[str] = None,
    skip:     int           = 0,
    limit:    int           = 100,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    limit = min(limit, 200)
    q = db.query(Report)
    if severity and severity in ("low", "medium", "high"):
        q = q.filter(Report.severity == severity)
    if status and status in ("pending", "in_progress", "resolved"):
        q = q.filter(Report.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            Report.address.ilike(like)  |
            Report.landmark.ilike(like) |
            Report.ref_code.ilike(like)
        )
    total = q.count()
    items = q.order_by(desc(Report.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@app.patch("/api/admin/reports/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: int,
    update: ReportUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if update.status is not None:
        report.status = update.status
    if update.admin_notes is not None:
        report.admin_notes = update.admin_notes
    if update.is_verified is not None:
        report.is_verified = update.is_verified
    report.updated_at = _now()
    db.commit()
    db.refresh(report)
    # Notify reporter if status changed and they provided an email
    if update.status is not None:
        await notify_status_changed(
            report.ref_code, report.address,
            report.status.value, report.admin_notes, report.reporter_contact
        )
    return report


@app.delete("/api/admin/reports/{report_id}", status_code=200)
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.photo_path:
        photo = UPLOAD_DIR / report.photo_path
        if photo.exists():
            photo.unlink()
    db.delete(report)
    db.commit()
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pothole-finder"}
