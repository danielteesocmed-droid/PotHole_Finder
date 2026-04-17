import os, uuid, random, string, shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import desc
from PIL import Image
import aiofiles

from database import get_db, init_db
from models import Report, AdminUser, SeverityEnum, StatusEnum
from schemas import ReportOut, ReportUpdate, AdminLogin, StatsOut
from auth import verify_password, create_access_token, decode_token

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
FRONTEND_DIR = BASE_DIR / "frontend" / "public"

app = FastAPI(title="PotHole Finder API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# ── Helpers ───────────────────────────────────────────────────────────────────
def gen_ref_code():
    return "PH-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))

def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    admin = db.query(AdminUser).filter_by(username=payload.get("sub")).first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin

async def save_photo(file: UploadFile) -> str:
    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".heic"]:
        ext = ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    async with aiofiles.open(dest, "wb") as f:
        content = await file.read()
        await f.write(content)
    # Resize to max 1200px to save space
    try:
        img = Image.open(dest)
        img.thumbnail((1200, 1200), Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dest, "JPEG", quality=82)
        filename = Path(dest).stem + ".jpg"
        dest.rename(UPLOAD_DIR / filename)
    except Exception:
        pass
    return filename

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()

# ── Frontend Serving ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_app():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=index.read_text(), status_code=200)

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    admin_page = FRONTEND_DIR / "admin.html"
    return HTMLResponse(content=admin_page.read_text(), status_code=200)

# ── Public Routes ─────────────────────────────────────────────────────────────
@app.post("/api/reports", response_model=ReportOut)
async def create_report(
    address: str = Form(...),
    landmark: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    severity: SeverityEnum = Form(...),
    description: Optional[str] = Form(None),
    reporter_name: Optional[str] = Form("Anonymous"),
    reporter_contact: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    photo_path = None
    if photo and photo.filename:
        photo_path = await save_photo(photo)

    report = Report(
        ref_code=gen_ref_code(),
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
    return report

@app.get("/api/reports", response_model=List[ReportOut])
async def list_reports(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    q = db.query(Report)
    if severity and severity in ["low", "medium", "high"]:
        q = q.filter(Report.severity == severity)
    if status and status in ["pending", "in_progress", "resolved"]:
        q = q.filter(Report.status == status)
    return q.order_by(desc(Report.created_at)).offset(skip).limit(limit).all()

@app.get("/api/reports/{ref_code}", response_model=ReportOut)
async def get_report(ref_code: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.ref_code == ref_code).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@app.get("/api/stats", response_model=StatsOut)
async def get_stats(db: Session = Depends(get_db)):
    all_r = db.query(Report).all()
    return {
        "total": len(all_r),
        "pending": sum(1 for r in all_r if r.status == StatusEnum.pending),
        "in_progress": sum(1 for r in all_r if r.status == StatusEnum.in_progress),
        "resolved": sum(1 for r in all_r if r.status == StatusEnum.resolved),
        "high": sum(1 for r in all_r if r.severity == SeverityEnum.high),
        "medium": sum(1 for r in all_r if r.severity == SeverityEnum.medium),
        "low": sum(1 for r in all_r if r.severity == SeverityEnum.low),
        "verified": sum(1 for r in all_r if r.is_verified),
    }

# ── Admin Routes ──────────────────────────────────────────────────────────────
@app.post("/api/admin/login")
async def admin_login(body: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter_by(username=body.username).first()
    if not admin or not verify_password(body.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.username})
    return {"access_token": token, "token_type": "bearer", "full_name": admin.full_name}

@app.get("/api/admin/reports", response_model=List[ReportOut])
async def admin_list_reports(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    q = db.query(Report)
    if severity and severity in ["low", "medium", "high"]:
        q = q.filter(Report.severity == severity)
    if status and status in ["pending", "in_progress", "resolved"]:
        q = q.filter(Report.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            Report.address.ilike(like) |
            Report.landmark.ilike(like) |
            Report.ref_code.ilike(like)
        )
    return q.order_by(desc(Report.created_at)).offset(skip).limit(limit).all()

@app.patch("/api/admin/reports/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: int,
    update: ReportUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Not found")
    if update.status is not None:
        report.status = update.status
    if update.admin_notes is not None:
        report.admin_notes = update.admin_notes
    if update.is_verified is not None:
        report.is_verified = update.is_verified
    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report

@app.delete("/api/admin/reports/{report_id}")
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Not found")
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
