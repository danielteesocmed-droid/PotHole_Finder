# 🕳️ PotHole Finder

A civic tech web app for citizens to report road potholes — mobile-friendly, with GPS detection, photo uploads, severity tagging, and a full admin dashboard.

---

## Features

### Citizen App (`/`)
- 📷 Camera photo upload (opens camera directly on mobile)
- 📡 One-tap GPS coordinate capture
- 📌 Landmark input (for citizens without GPS-enabled cameras)
- 🟡🟠🔴 Severity selector (Minor / Moderate / Severe)
- 📋 Report list with filters by status and severity
- 🗺️ Live map of all geotagged reports (OpenStreetMap)

### Admin Panel (`/admin`)
- 🔐 JWT-secured login
- 📊 Dashboard with live stats and severity breakdown
- 📋 Reports table with search, filter, pagination
- ✏️ Update report status (Pending → In Progress → Resolved)
- 🗒️ Admin notes per report
- 🗺️ Map view of all reports
- 🗑️ Delete reports

---

## Deploy to Railway

### 1. Push to GitHub
```bash
cd pothole-finder
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/pothole-finder.git
git push -u origin main
```

### 2. Create Railway Project
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo
3. Select `pothole-finder`

### 3. Add Environment Variables in Railway
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourStrongPasswordHere
SECRET_KEY=some-random-string-minimum-32-chars
PASS_SALT=another-random-salt-string
```

### 4. Add a Volume (for persistent photo uploads)
1. Railway project → Add Volume
2. Mount path: `/app/uploads`
3. Set env var: `UPLOAD_DIR=/app/uploads`

Similarly add a volume for the DB:
- Mount path: `/app/data`
- Set env var: `DB_PATH=/app/data/pothole.db`

---

## Local Development

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your values
uvicorn main:app --reload --port 8000
```

Then open:
- Citizen app: http://localhost:8000
- Admin panel: http://localhost:8000/admin

Default admin credentials: `admin` / `admin1234`

---

## Stack
- **Backend**: FastAPI + SQLite
- **Frontend**: Vanilla JS (no build step)
- **Maps**: Leaflet.js + OpenStreetMap (free, no API key needed)
- **Auth**: JWT tokens
- **Deploy**: Railway
