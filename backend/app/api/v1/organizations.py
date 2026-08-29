"""
Organization / team member management.

Plans are shared across a company's team members (Professional = up to
5, Business = up to 15 - see PLAN_MAX_MEMBERS in models/organization.py).
Only the organization's "owner" can invite or remove members.

MVP scope: inviting someone means moving an EXISTING OCRDocFlow account
into your organization by email - there's no "invite an unregistered
email" flow yet, since that needs real email sending (SendGrid, planned
next). For now, the person being invited must already have registered
their own account first.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.organization import Organization, PLAN_MAX_MEMBERS
from app.models.user import User

router = APIRouter(prefix="/api/v1/organization", tags=["organization"])


def _require_owner(current_user: User) -> Organization:
    if current_user.organization is None:
        raise HTTPException(status_code=400, detail="No organization found for this account.")
    if current_user.org_role != "owner":
        raise HTTPException(status_code=403, detail="Only the organization's owner can manage members.")
    return current_user.organization


@router.get("/me")
def get_my_organization(current_user: User = Depends(get_current_user)):
    org = current_user.organization
    if org is None:
        raise HTTPException(status_code=400, detail="No organization found for this account.")
    return {
        "id": org.id,
        "name": org.name,
        "plan": org.plan,
        "max_members": PLAN_MAX_MEMBERS.get(org.plan, 1),
        "member_count": len(org.members),
        "my_role": current_user.org_role,
    }


@router.get("/members")
def list_members(current_user: User = Depends(get_current_user)):
    if current_user.organization is None:
        raise HTTPException(status_code=400, detail="No organization found for this account.")
    return [
        {
            "id": m.id,
            "email": m.email,
            "full_name": m.full_name,
            "org_role": m.org_role,
        }
        for m in current_user.organization.members
    ]


class InviteRequest(BaseModel):
    email: str


@router.post("/invite")
def invite_member(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _require_owner(current_user)

    max_members = PLAN_MAX_MEMBERS.get(org.plan, 1)
    current_count = db.query(User).filter(User.organization_id == org.id).count()
    if current_count >= max_members:
        raise HTTPException(
            status_code=400,
            detail=f"Your {org.plan} plan allows up to {max_members} member(s). Upgrade your plan to add more.",
        )

    target = db.query(User).filter(User.email == payload.email).first()
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No account found with that email. They need to create a free "
                "OCRDocFlow account first, then you can add them to your team."
            ),
        )

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You're already in this organization.")

    if target.organization_id == org.id:
        raise HTTPException(status_code=400, detail="This person is already a member of your organization.")

    # Safety check: don't silently pull someone out of an org that has
    # OTHER members - only move them if they're on their own (a solo
    # free/starter account), to avoid disrupting another team.
    if target.organization is not None:
        other_members = [m for m in target.organization.members if m.id != target.id]
        if other_members:
            raise HTTPException(
                status_code=400,
                detail="This person already belongs to another organization with other members.",
            )

    target.organization_id = org.id
    target.org_role = "member"
    db.commit()

    return {"status": "added", "email": target.email}


@router.delete("/members/{user_id}")
def remove_member(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _require_owner(current_user)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself as the owner.")

    target = db.query(User).filter(User.id == user_id, User.organization_id == org.id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found in your organization.")

    # Give them their own fresh solo organization rather than leaving
    # them with no organization at all.
    new_org = Organization(name=f"{target.full_name or target.email}'s Organization", plan="free")
    db.add(new_org)
    db.flush()

    target.organization_id = new_org.id
    target.org_role = "owner"
    db.commit()

    return {"status": "removed", "email": target.email}