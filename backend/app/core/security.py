"""
Password hashing and JWT tokens live here.

Why bcrypt? The Security Policy (Section 5.1) requires a modern password
hashing algorithm - never plain text, never simple MD5/SHA1.

Why short-lived access tokens? Section 6 of the Security Policy requires
access tokens to have a short lifetime (we use 15 minutes by default).
"""
import hashlib
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("purpose"):  # e.g. a password-reset token - never a login
            return None
        return payload.get("sub")
    except jwt.JWTError:
        return None


# --- Password reset tokens ---------------------------------------------
# A signed, short-lived token that needs no database table. It carries a
# fingerprint of the user's CURRENT password hash, so it stops working the
# moment the password changes: every link is single-use, and older links
# die with the first successful reset. "purpose" keeps a reset token from
# ever being accepted as a login token (decode_access_token rejects any
# token that has one).
RESET_PURPOSE = "password_reset"


def _password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def create_password_reset_token(email: str, hashed_password: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "exp": expire,
        "purpose": RESET_PURPOSE,
        "pwf": _password_fingerprint(hashed_password),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def read_password_reset_token(token: str) -> tuple[str, str] | None:
    """Returns (email, password_fingerprint), or None if the token is
    invalid, expired, or not a reset token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.JWTError:
        return None
    if payload.get("purpose") != RESET_PURPOSE or not payload.get("sub") or not payload.get("pwf"):
        return None
    return payload["sub"], payload["pwf"]


def reset_token_matches_user(fingerprint: str, hashed_password: str) -> bool:
    return fingerprint == _password_fingerprint(hashed_password)
