import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, AdminUser
from auth import hash_password

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pothole.db")

# Railway PostgreSQL uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
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
    # Seed default admin
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter_by(username="admin").first()
        if not existing:
            admin_password = os.getenv("ADMIN_PASSWORD", "admin1234")
            admin = AdminUser(
                username="admin",
                hashed_password=hash_password(admin_password),
                full_name="Road Admin"
            )
            db.add(admin)
            db.commit()
            print(f"[INIT] Default admin created. Password: {admin_password}")
    finally:
        db.close()
