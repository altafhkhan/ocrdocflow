"""
Runs the invoice retention job once and prints what it did.

    python -m app.scripts.retention_run --dry-run   # report only, changes nothing
    python -m app.scripts.retention_run             # follows RETENTION_MODE

On the server:
    docker exec ocrdocflow-api python -m app.scripts.retention_run --dry-run
"""
import sys

from app.core.config import settings
from app.db.database import SessionLocal
from app.services import retention_service


def main() -> None:
    dry_run = True if "--dry-run" in sys.argv else None
    db = SessionLocal()
    try:
        report = retention_service.run_once(db, dry_run=dry_run)
    finally:
        db.close()
    print(f"RETENTION_MODE={settings.RETENTION_MODE}  dry run: {report['dry_run']}")
    for title in ("emails", "deletions", "problems"):
        print(f"{title}: {len(report[title])}")
        for line in report[title]:
            print("  -", line)


if __name__ == "__main__":
    main()
