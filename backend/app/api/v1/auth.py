from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    hash_password,
    read_password_reset_token,
    reset_token_matches_user,
    verify_password,
)
from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest, Token, UserCreate, UserOut
from app.core.limiter import limiter
from app.services import email_service, usage_service

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        # Deliberately vague error - don't reveal *why* it failed to an attacker
        raise HTTPException(status_code=400, detail="Could not create account")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()  # assigns user.id without a full commit yet

    # Every user belongs to an organization from day one (even a solo
    # free account) - keeps one consistent code path instead of two
    # (see models/organization.py docstring). This is what the old
    # one-time migration script did for EXISTING accounts; new signups
    # need the same thing done automatically here.
    org_name = user.full_name or user.email.split("@")[0]
    org = Organization(name=f"{org_name}'s Organization", plan="free")
    db.add(org)
    db.flush()

    user.organization_id = org.id
    user.org_role = "owner"

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/15minutes")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    # Same error whether the email doesn't exist or the password is wrong -
    # this stops attackers from figuring out which emails are registered.
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token(subject=user.email)
    return Token(access_token=token)


@router.post("/forgot-password")
@limiter.limit("3/15minutes")
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Step 1 of a password reset. Always answers with the same message, so
    nobody can use this endpoint to find out which emails have accounts
    (same reasoning as the login error above).
    """
    minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = create_password_reset_token(user.email, user.hashed_password)
        link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        greeting = f"Hello {user.full_name}," if user.full_name else "Hello,"
        text = (
            f"{greeting}\n\n"
            "Someone asked to reset the password of your OCRDocFlow account. "
            f"To choose a new password, open this link within {minutes} minutes:\n\n"
            f"{link}\n\n"
            "If you did not ask for this, ignore this email - your password stays as it is.\n\n"
            "OCRDocFlow by Qumaxa"
        )
        html = (
            f"<p>{greeting}</p>"
            "<p>Someone asked to reset the password of your OCRDocFlow account. "
            f"To choose a new password, use this button within {minutes} minutes:</p>"
            f'<p><a href="{link}" style="background:#2563eb;color:#fff;padding:10px 18px;'
            'border-radius:6px;text-decoration:none;display:inline-block">Choose a new password</a></p>'
            f'<p style="font-size:13px;color:#555">Or paste this address into your browser:<br>{link}</p>'
            "<p>If you did not ask for this, ignore this email - your password stays as it is.</p>"
            "<p>OCRDocFlow by Qumaxa</p>"
        )
        sent = email_service.send_email(user.email, "Reset your OCRDocFlow password", text, html)
        if not sent:
            # No mail provider configured (or it failed): leave the link in
            # the server log so the operator can pass it to the user. The
            # log stays on the server; the link expires and is single-use.
            logger.warning("Password reset link for %s (email not sent): %s", user.email, link)
    return {
        "message": "If an account exists for that email, we have sent a link to choose a new password. "
                   f"It works for {minutes} minutes."
    }


@router.post("/reset-password")
@limiter.limit("10/15minutes")
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Step 2: the token from the link plus the new password."""
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(payload.new_password.encode()) > 72:  # bcrypt's own limit
        raise HTTPException(status_code=400, detail="Password is too long (72 characters at most).")

    invalid = HTTPException(
        status_code=400,
        detail="This reset link is invalid, has expired or was already used. Please request a new one.",
    )
    parsed = read_password_reset_token(payload.token)
    if not parsed:
        raise invalid
    email, fingerprint = parsed
    user = db.query(User).filter(User.email == email).first()
    if not user or not reset_token_matches_user(fingerprint, user.hashed_password):
        raise invalid

    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    logger.info("Password reset completed for %s", user.email)
    return {"message": "Your password has been changed. You can log in now."}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Lets the frontend check who's currently logged in, their role, and
    their organization's plan/usage - used to decide what to show
    (Admin Panel link, current plan badge, usage bar, etc). The backend
    admin endpoints (api/v1/admin.py) and usage_service.py enforce the
    real checks independently - this is just for the UI to know what
    to display.
    """
    is_admin = current_user.role == "admin"
    org = current_user.organization

    if is_admin or org is None:
        return {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "plan": org.plan if org else "free",
            "invoices_this_period": None,
            "billing_period_limit": None,
            "billing_period_start": None,
        }

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "plan": org.plan,
        "invoices_this_period": usage_service.get_usage_this_period(db, org),
        "billing_period_limit": usage_service.get_plan_limit(org),
        "billing_period_start": usage_service.get_period_start(org),
    }