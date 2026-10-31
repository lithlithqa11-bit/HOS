"""Import doctor names from the legacy AlShifa SQLite demo into MediLink PostgreSQL."""
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.db.models import Employee, Hospital, Role
from backend.app.db.session import SessionLocal


SOURCE = Path(r"C:\Users\krar9\Desktop\jjti\AlShifaHospital.db")


def main() -> None:
    load_dotenv()
    with sqlite3.connect(SOURCE) as source:
        source.row_factory = sqlite3.Row
        doctors = source.execute(
            "SELECT Doctor_ID, Name, Specialization FROM Doctors ORDER BY Doctor_ID"
        ).fetchall()
    with SessionLocal.begin() as db:
        hospital = db.scalar(select(Hospital).order_by(Hospital.id))
        role = db.scalar(select(Role).where(Role.name == 'doctor'))
        if not hospital or not role:
            raise RuntimeError('Run migrations and seed before importing doctors')
        password_hash = hash_password(os.environ['DEMO_PASSWORD'])
        added = 0
        for row in doctors:
            username = f"dr{row['Doctor_ID']}.a"
            if db.scalar(select(Employee.id).where(Employee.username == username)):
                continue
            specialization = row['Specialization'] or 'طبيب عام'
            employee = Employee(
                hospital_id=hospital.id,
                username=username,
                full_name=f"{row['Name']} — {specialization}",
                password_hash=password_hash,
                roles=[role],
            )
            db.add(employee)
            added += 1
    print(f'Imported {added} doctors from {SOURCE}')


if __name__ == '__main__':
    main()
