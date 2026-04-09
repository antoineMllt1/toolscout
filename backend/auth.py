"""
JWT authentication utilities.
- Passwords hashed with bcrypt (passlib)
- Tokens: HS256 JWT, 30-day expiry
- Secret key auto-generated and persisted in SECRET_KEY file
"""
import os
import secrets
from datetime import datetime, timedelta

import warnings
warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")

from jose import JWTError, jwt
from passlib.context import CryptContext

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

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
