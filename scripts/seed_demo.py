"""ProcessFoundry AI: Demo Accounts and Project Seeding Script (Part 7.10)."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.repositories.database import db
from app.services.permissions import hash_password

DEMO_USERS = [
    {"name": "Aditi Sharma", "email": "aditi@example.com", "role": "analyst"},
    {"name": "Rao Mehta", "email": "rao@example.com", "role": "process_owner"},
    {"name": "Anil Kapoor", "email": "anil@example.com", "role": "technical_reviewer"}
]

DEMO_PASSWORD = "Process123!"

def seed_demo_data():
    print("Seeding ProcessFoundry AI demo data...")
    user_ids = {}

    for u in DEMO_USERS:
        email = u["email"].lower()
        existing = db.get_user_by_email(email)
        if not existing:
            pwd_hash = hash_password(DEMO_PASSWORD)
            created = db.create_user(u["name"], email, pwd_hash)
            user_ids[email] = created["id"]
            print(f"Created demo account: {u['name']} <{email}> (Role: {u['role']})")
        else:
            user_ids[email] = existing["id"]
            print(f"Demo account already exists: {u['name']} <{email}>")

    # Check if demo project exists
    aditi_id = user_ids["aditi@example.com"]
    projects = db.list_user_projects(aditi_id)
    demo_proj = next((p for p in projects if p["name"] == "Test process"), None)

    if not demo_proj:
        new_proj = db.create_project(
            name="Test process",
            user_id=aditi_id,
            role="analyst",
            process_type="scholarship",
            description="Institutional scholarship application and disbursement process.",
            department="Student Affairs",
            goals="Eliminate processing delays and ambiguity.",
            constraints="Must comply with university scholarship charter."
        )
        print(f"Created demo project: 'Test process' (ID: {new_proj['id']}) with Aditi as creator & Analyst.")
        print("No other members have been added so the invitation flow can be demonstrated live.")
    else:
        print(f"Demo project 'Test process' already exists (ID: {demo_proj['id']}).")

    print("\n[SUCCESS] Seeding complete!")
    print(f"All demo accounts use password: {DEMO_PASSWORD}")
    print("1. Aditi Sharma   (aditi@example.com) -> Analyst")
    print("2. Rao Mehta       (rao@example.com)   -> Process Owner")
    print("3. Anil Kapoor     (anil@example.com)  -> Technical Reviewer")

if __name__ == "__main__":
    seed_demo_data()
