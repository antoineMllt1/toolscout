"""
JWT authentication utilities.
- Passwords hashed with bcrypt
- Tokens: HS256 JWT, 30-day expiry
- Secret key auto-generated and persisted in SECRET_KEY file
"""
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from jose import JWTError, jwt

ALGORITHM  = "HS256"
TOKEN_DAYS = 30

# Load or generate a persistent secret key
_KEY_FILE = os.path.join(os.path.dirname(__file__), ".secret_key")

def _load_secret() -> str:
    if os.path.exists(_KEY_FILE):
        return open(_KEY_FILE).read().strip()
    key = secrets.token_hex(32)
    with open(_KEY_FILE, "w") as f:
        f.write(key)
    return key

SECRET_KEY = os.environ.get("SECRET_KEY") or _load_secret()

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must be 72 bytes or fewer")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
