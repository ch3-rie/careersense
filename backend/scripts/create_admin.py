"""Create the first CareerSense administrator when none exists.

Run from the backend folder:

    py -3 scripts/create_admin.py --email oaaps.admin@auf.edu.ph --first-name OAAPS --last-name Admin
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal  # noqa: E402
from app.models import Account  # noqa: E402
from app.security import generate_temp_password, hash_password  # noqa: E402
from app.services.validation import normalize_email  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first CareerSense administrator.")
    parser.add_argument("--email", required=True, help="Administrator email")
    parser.add_argument("--first-name", default="OAAPS", help="First name")
    parser.add_argument("--last-name", default="Admin", help="Last name")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing_admin = db.query(Account).filter(Account.role == "Admin").first()
        if existing_admin:
            print("An administrator account already exists. Sign in with that account to create additional admins.")
            return 1
        email = normalize_email(args.email)
        if db.query(Account).filter(Account.personal_email == email).first():
            print("An account with this email already exists.")
            return 1
        password = generate_temp_password(14)
        admin = Account(
            personal_email=email,
            password_hash=hash_password(password),
            role="Admin",
            status="Active",
            first_name=args.first_name.strip(),
            last_name=args.last_name.strip(),
            must_change_password=True,
            privacy_consent=True,
        )
        db.add(admin)
        db.commit()
        print("Administrator created.")
        print(f"Email: {email}")
        print(f"Temporary password: {password}")
        print("Sign in and change this password immediately. It will not be shown again.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
