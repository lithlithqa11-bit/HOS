"""Idempotent synthetic demonstration seed; password supplied through .env, never in source."""
import os
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import select
from backend.app.core.security import ROLES, hash_password
from backend.app.db.models import (Hospital, Department, Role, Employee, Patient, PatientHospitalAccess,
                                   HospitalConnection, Medication)
from backend.app.db.session import SessionLocal


def seed(db, password):
    if len(password) < 12:
        raise ValueError('DEMO_PASSWORD must contain at least 12 characters')
    if db.scalar(select(Hospital.id).limit(1)):
        return False
    hospitals = [Hospital(name='Hospital A — مستشفى النور التعليمي', city='بغداد'),
                 Hospital(name='Hospital B — مستشفى الأمل التعليمي', city='بغداد')]
    roles = [Role(name=name) for name in ROLES]
    db.add_all(hospitals + roles)
    db.flush()
    employees = []
    for suffix, hospital in zip(('a', 'b'), hospitals):
        db.add(Department(hospital_id=hospital.id, name='العيادة التعليمية'))
        for role in roles:
            staff = Employee(hospital_id=hospital.id, username=f'{role.name}.{suffix}',
                             full_name=f'{role.name} — موظف تجريبي {suffix.upper()}',
                             password_hash=hash_password(password), roles=[role])
            employees.append(staff)
            db.add(staff)
    db.flush()
    for i, name in enumerate(('مريض تجريبي أحمد', 'مريضة تجريبية سارة', 'مريض تجريبي علي')):
        patient = Patient(full_name=name, birth_date=date(2000 + i, 1, 1),
                          sex='female' if i == 1 else 'male', phone='00000000000')
        db.add(patient)
        db.flush()
        for hospital in hospitals:
            db.add(PatientHospitalAccess(patient_id=patient.id, hospital_id=hospital.id,
                                         granted_by=employees[0].id))
    db.add_all([HospitalConnection(source_id=hospitals[0].id, destination_id=hospitals[1].id),
                HospitalConnection(source_id=hospitals[1].id, destination_id=hospitals[0].id),
                Medication(name='دواء تدريبي A (غير مخصص للاستخدام)'),
                Medication(name='دواء تدريبي B (غير مخصص للاستخدام)')])
    return True


if __name__ == '__main__':
    load_dotenv()
    with SessionLocal.begin() as db:
        created = seed(db, os.environ['DEMO_PASSWORD'])
    print('Synthetic seed created.' if created else 'Seed already exists; left unchanged.')
    print('Accounts: admin.a / doctor.a / nurse.a / pharmacist.a / receptionist.a (and .b). Password in .env')
