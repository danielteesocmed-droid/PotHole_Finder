import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, AdminUser
from auth import hash_password

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pothole.db")

# Railway PostgreSQL uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = "sqlite" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # For PostgreSQL: use a connection pool with reasonable limits
    pool_pre_ping=True,           # detect stale connections
    pool_recycle=1800 if not _is_sqlite else -1,  # recycle every 30 min on pg
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

    # Seed default admin only if none exists
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter_by(username="admin").first()
        if not existing:
            admin_password = os.getenv("ADMIN_PASSWORD", "")
            if not admin_password:
                import secrets
                admin_password = secrets.token_urlsafe(16)
                print(
                    f"[INIT] No ADMIN_PASSWORD env var set. "
                    f"Generated password: {admin_password}  ← save this!"
                )
            admin = AdminUser(
                username="admin",
                hashed_password=hash_password(admin_password),
                full_name="Road Admin",
            )
            db.add(admin)
            db.commit()
            print("[INIT] Default admin account created.")
    finally:
        db.close()
