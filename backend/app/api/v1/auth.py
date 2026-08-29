from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.schemas.user import Token, UserCreate, UserOut
from app.core.limiter import limiter
from app.services import usage_service

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