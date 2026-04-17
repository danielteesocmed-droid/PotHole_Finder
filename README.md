# PotHole Finder

A civic web app for citizens to report road potholes, and for road agencies to monitor and manage repairs.

**Built with:** FastAPI · SQLite/PostgreSQL · Vanilla JS · Railway-ready

---

## Features

### Citizen App (`/`)
- Photo upload — camera opens directly on mobile
- GPS auto-detect with accuracy indicator
- Landmark field for citizens without GPS
- Severity levels: Minor / Moderate / Severe
- Reference code issued on submission (e.g. `PH-A1B2C3D`)
- Public reports list with filters
- Stats dashboard
- Report tracker by reference code

### Admin Panel (`/admin`)
- JWT-secured login
- Full reports table with search and filters
- Edit status: Pending → In Progress → Resolved
- Admin notes (visible to citizens on Track tab)
- Verified badge system
- Delete reports with photo cleanup
- Google Maps link for GPS-tagged reports
- Live stats cards

---

## Project Structure

```
pothole-finder/
├── backend/
│   ├── main.py          # FastAPI app + all routes
│   ├── models.py        # SQLAlchemy models
│   ├── database.py      # DB setup + admin seeding
│   ├── auth.py          # JWT + bcrypt helpers
│   └── schemas.py       # Pydantic schemas
├── frontend/
│   └── public/
│       ├── index.html   # Citizen app
│       └── admin.html   # Admin panel
├── uploads/             # Uploaded photos (auto-created)
├── requirements.txt
├── railway.toml
├── Procfile
└── .env.example
```

---

## Deploy to Railway

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit - PotHole Finder"
git remote add origin https://github.com/YOUR_USERNAME/pothole-finder.git
git push -u origin main
```

### Step 2 — Create Railway Project
1. Go to railway.app → New Project
2. Select "Deploy from GitHub repo" → pick `pothole-finder`
3. Railway auto-detects Python and installs from `requirements.txt`

### Step 3 — Set Environment Variables
In Railway dashboard → your service → Variables:

| Variable | Value |
|---|---|
| `SECRET_KEY` | Run: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD` | Your admin password |

### Step 4 — (Optional) Add PostgreSQL
1. Railway project → + New → Database → PostgreSQL
2. Railway auto-injects `DATABASE_URL` — the app picks it up automatically

### Step 5 — Done
Railway deploys on every `git push`. Live at:
- Citizen app: `https://your-app.up.railway.app/`
- Admin panel: `https://your-app.up.railway.app/admin`

---

## Run Locally

```bash
pip install -r requirements.txt
cp .env.example .env        # edit SECRET_KEY and ADMIN_PASSWORD
cd backend
uvicorn main:app --reload --port 8000
# Open http://localhost:8000
# Admin: http://localhost:8000/admin
# API docs: http://localhost:8000/docs
```

---

## Default Admin Login

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin1234` |

Change it by setting `ADMIN_PASSWORD` in Railway environment variables before deploying.

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/reports` | Public | Submit report (multipart form + optional photo) |
| GET | `/api/reports` | Public | List reports (filter: severity, status) |
| GET | `/api/reports/{ref_code}` | Public | Get single report by ref code |
| GET | `/api/stats` | Public | Summary statistics |
| POST | `/api/admin/login` | — | Login, returns JWT |
| GET | `/api/admin/reports` | JWT | List with search + filters |
| PATCH | `/api/admin/reports/{id}` | JWT | Update status / notes / verified |
| DELETE | `/api/admin/reports/{id}` | JWT | Delete report + photo file |
| GET | `/health` | Public | Health check (used by Railway) |
| GET | `/docs` | Public | Swagger UI |

---

## Photo Storage Note

Photos are saved in `/uploads/` and auto-resized to max 1200px.

Railway's filesystem is ephemeral — photos are lost on redeploy unless you add a Volume:
1. Railway dashboard → your service → Volumes
2. Mount path: `/home/claude/pothole-finder/uploads`
3. Photos now persist across deploys

For higher scale, swap `save_photo()` in `main.py` with Cloudinary or S3 upload.

---

## Customization Tips

- **Agency branding:** Edit the topbar in `index.html` and `admin.html`
- **Primary color:** Search/replace `#E8510A` in both HTML files
- **Map view:** Replace the map placeholder in the Stats tab with Leaflet.js — lat/lng is already stored
- **Notifications:** Add email/SMS in `create_report()` in `main.py`
