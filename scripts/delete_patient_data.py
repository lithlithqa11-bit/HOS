"""Administrative hard-delete tool for a confirmed demo patient id."""
import sys
from sqlalchemy import text
from backend.app.db.session import SessionLocal


TABLES = [
    ('prescription_items', 'prescription_id IN (SELECT id FROM prescriptions WHERE visit_id IN (SELECT id FROM visits WHERE patient_id = :id))'),
    ('prescriptions', 'visit_id IN (SELECT id FROM visits WHERE patient_id = :id)'),
    ('diagnoses', 'visit_id IN (SELECT id FROM visits WHERE patient_id = :id)'),
    ('payments', 'invoice_id IN (SELECT id FROM invoices WHERE patient_id = :id)'),
    ('invoice_items', 'invoice_id IN (SELECT id FROM invoices WHERE patient_id = :id)'),
    ('invoices', 'patient_id = :id'),
    ('appointments', 'patient_id = :id'),
    ('emergency_cases', 'patient_id = :id'),
    ('referrals', 'patient_id = :id'),
    ('visits', 'patient_id = :id'),
    ('allergies', 'patient_id = :id'),
    ('chronic_conditions', 'patient_id = :id'),
    ('nfc_cards', 'patient_id = :id'),
    ('patient_hospital_access', 'patient_id = :id'),
]


def main():
    patient_id = int(sys.argv[1])
    deleted = {}
    with SessionLocal.begin() as db:
        row = db.execute(text('SELECT full_name FROM patients WHERE id = :id'), {'id': patient_id}).first()
        if not row:
            raise SystemExit(f'Patient {patient_id} not found')
        for table, where in TABLES:
            result = db.execute(text(f'DELETE FROM {table} WHERE {where}'), {'id': patient_id})
            deleted[table] = result.rowcount
        db.execute(text('UPDATE audit_logs SET patient_id = NULL WHERE patient_id = :id'), {'id': patient_id})
        db.execute(text('DELETE FROM patients WHERE id = :id'), {'id': patient_id})
    print(f'Deleted patient {patient_id}: {row[0]}')
    print(deleted)


if __name__ == '__main__':
    main()
