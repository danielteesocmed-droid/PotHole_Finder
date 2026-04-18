import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY", "")
_DEFAULT_KEY = "pothole-finder-secret-key-change-in-prod"

# Refuse to boot in production with a weak/default secret key
if not SECRET_KEY or SECRET_KEY == _DEFAULT_KEY:
    import sys
    _db_url = os.getenv("DATABASE_URL", "")
    if "postgres" in _db_url:
        raise RuntimeError(
            "FATAL: SECRET_KEY env var is missing or set to the default value.\n"
            "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    else:
        print("[WARNING] SECRET_KEY not set — using insecure default. Dev only!", file=sys.stderr)
    SECRET_KEY = _DEFAULT_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
