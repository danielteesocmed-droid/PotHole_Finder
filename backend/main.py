import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_db
from auth import hash_password, verify_password, create_access_token, decode_token

# ── setup ──────────────────────────────────────────────────────────────────
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PotHole Finder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
def startup():
    init_db()


# ── static files ───────────────────────────────────────────────────────────
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_citizen():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/admin")
def serve_admin():
    return FileResponse(str(FRONTEND_DIR / "admin.html"))


# ── health ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── auth ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/admin/login")
def admin_login(req: LoginRequest):
    db = get_db()
    row = db.execute("SELECT * FROM admins WHERE username = ?", (req.username,)).fetchone()
    db.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": req.username})
    return {"access_token": token, "token_type": "bearer"}


def require_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["sub"]


# ── reports ────────────────────────────────────────────────────────────────
@app.post("/api/reports")
async def create_report(
    reporter_name: str = Form(""),
    contact: str = Form(""),
    address: str = Form(...),
    landmark: str = Form(""),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    severity: str = Form("moderate"),
    description: str = Form(""),
    photo: Optional[UploadFile] = File(None),
):
    photo_path = None
    if photo and photo.filename:
        ext = Path(photo.filename).suffix.lower() or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / filename
        with dest.open("wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_path = f"/uploads/{filename}"

    now = datetime.utcnow().isoformat()
    db = get_db()
    cur = db.execute(
        """INSERT INTO reports
           (reporter_name, contact, address, landmark, latitude, longitude,
            severity, description, photo_path, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,'pending',?,?)""",
        (reporter_name, contact, address, landmark, latitude, longitude,
         severity, description, photo_path, now, now)
    )
    db.commit()
    report_id = cur.lastrowid
    db.close()
    return {"id": report_id, "message": "Report submitted successfully"}


@app.get("/api/reports")
def list_reports(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    db = get_db()
    query = "SELECT * FROM reports WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = db.execute(query, params).fetchall()
    total = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    db.close()
    return {"total": total, "reports": [dict(r) for r in rows]}


@app.get("/api/reports/{report_id}")
def get_report(report_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return dict(row)


class UpdateReport(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None


@app.patch("/api/reports/{report_id}")
def update_report(report_id: int, body: UpdateReport, admin=Depends(require_admin)):
    db = get_db()
    row = db.execute("SELECT id FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Report not found")
    fields, params = [], []
    if body.status is not None:
        fields.append("status = ?")
        params.append(body.status)
    if body.admin_notes is not None:
        fields.append("admin_notes = ?")
        params.append(body.admin_notes)
    fields.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(report_id)
    db.execute(f"UPDATE reports SET {', '.join(fields)} WHERE id = ?", params)
    db.commit()
    db.close()
    return {"message": "Updated"}


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: int, admin=Depends(require_admin)):
    db = get_db()
    db.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    db.commit()
    db.close()
    return {"message": "Deleted"}


# ── stats ──────────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM reports WHERE status='pending'").fetchone()[0]
    in_progress = db.execute("SELECT COUNT(*) FROM reports WHERE status='in_progress'").fetchone()[0]
    resolved = db.execute("SELECT COUNT(*) FROM reports WHERE status='resolved'").fetchone()[0]
    minor = db.execute("SELECT COUNT(*) FROM reports WHERE severity='minor'").fetchone()[0]
    moderate = db.execute("SELECT COUNT(*) FROM reports WHERE severity='moderate'").fetchone()[0]
    severe = db.execute("SELECT COUNT(*) FROM reports WHERE severity='severe'").fetchone()[0]
    recent = db.execute(
        "SELECT * FROM reports ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    db.close()
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "severity": {"minor": minor, "moderate": moderate, "severe": severe},
        "recent": [dict(r) for r in recent],
    }
