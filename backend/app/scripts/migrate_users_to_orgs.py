"""
One-time data migration: creates a 1-person Organization for every
existing user, copying over their current plan/Stripe data, and links
the user to it as its "owner".

Run once via:
    docker compose exec backend python -m app.scripts.migrate_users_to_orgs

Safe to re-run - only processes users who don't already have an
organization_id set, so running it twice does nothing harmful the
second time.
"""
from app.db.database import SessionLocal
from app.models.user import User
from app.models.organization import Organization


def run():
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.organization_id.is_(None)).all()
        print(f"Found {len(users)} user(s) needing migration.")

        for user in users:
            org_name = user.full_name or user.email.split("@")[0]
            org = Organization(
                name=f"{org_name}'s Organization",
                plan=user.plan,
                plan_started_at=user.plan_started_at,
                stripe_customer_id=user.stripe_customer_id,
                stripe_subscription_id=user.stripe_subscription_id,
                subscription_status=user.subscription_status,
            )
            db.add(org)
            db.flush()  # assigns org.id without a full commit yet

            user.organization_id = org.id
            user.org_role = "owner"

            print(f"  - {user.email}: created org #{org.id} (plan={user.plan})")

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    run()