from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from backend.app.core.security import require, audit
from backend.app.db.session import get_db
from backend.app.db.models import Prescription, PrescriptionItem, Medication, Visit, PatientHospitalAccess, utcnow
from backend.app.schemas.requests import PrescriptionInput, CorrectionInput
from backend.app.services.access import get_or_404, visible_visit, local_record

router = APIRouter(prefix='/api')


def prescription_data(db, row):
    visit = db.get(Visit, row.visit_id)
    return {'id': row.id, 'visit_id': row.visit_id, 'patient_id': visit.patient_id,
            'hospital_id': visit.hospital_id, 'status': row.status, 'dispensed_by': row.dispensed_by,
            'dispensed_at': row.dispensed_at,
            'items': [{'medication_id': i.medication_id, 'name': db.get(Medication, i.medication_id).name,
                       'dose': i.dose, 'instructions': i.instructions} for i in row.items]}


@router.get('/medications')
def medications(employee=Depends(require('doctor', 'pharmacist')), db: Session = Depends(get_db, scope='function')):
    return [{'id': m.id, 'name': m.name} for m in db.scalars(select(Medication).order_by(Medication.id))]


@router.get('/prescriptions')
def prescriptions(patient_id: int | None = None, employee=Depends(require('doctor', 'pharmacist')),
                   db: Session = Depends(get_db, scope='function')):
    statement = select(Prescription).join(Visit).join(PatientHospitalAccess,
                  PatientHospitalAccess.patient_id == Visit.patient_id).where(
                      PatientHospitalAccess.hospital_id == employee.hospital_id,
                      PatientHospitalAccess.active.is_(True),
                      or_(Visit.hospital_id == employee.hospital_id, Visit.shared.is_(True)))
    if patient_id is not None:
        statement = statement.where(Visit.patient_id == patient_id)
    rows = db.scalars(statement.order_by(Prescription.id.desc()).limit(300)).all()
    for row in rows:
        visible_visit(db, employee, row.visit_id)
    audit(db, employee, 'prescription.read')
    return [prescription_data(db, row) for row in rows]


@router.post('/prescriptions', status_code=201)
def prescribe(data: PrescriptionInput, employee=Depends(require('doctor')), db: Session = Depends(get_db, scope='function')):
    visit = visible_visit(db, employee, data.visit_id, local=True)
    for item in data.items:
        get_or_404(db, Medication, item.medication_id)
    row = Prescription(visit_id=data.visit_id, items=[PrescriptionItem(**item.model_dump()) for item in data.items])
    db.add(row)
    db.flush()
    audit(db, employee, 'prescription.create', visit.patient_id, f'prescription:{row.id}')
    return prescription_data(db, row)


@router.post('/prescriptions/{id}/dispense')
def dispense(id: int, employee=Depends(require('pharmacist')), db: Session = Depends(get_db, scope='function')):
    row = get_or_404(db, Prescription, id, lock=True)
    visit = visible_visit(db, employee, row.visit_id)
    if row.status != 'Pending':
        raise HTTPException(409, 'الوصفة مصروفة بالفعل')
    row.status, row.dispensed_by, row.dispensed_at = 'Dispensed', employee.id, utcnow()
    audit(db, employee, 'prescription.dispense', visit.patient_id, f'prescription:{id}')
    return prescription_data(db, row)


@router.post('/prescriptions/{id}/correct')
def correct(id: int, data: CorrectionInput, employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    row = get_or_404(db, Prescription, id, lock=True)
    visit = local_record(get_or_404(db, Visit, row.visit_id), employee)
    if row.status != 'Dispensed':
        raise HTTPException(409, 'الوصفة ليست مصروفة')
    previous = f'prescription:{id};previous_pharmacist:{row.dispensed_by};previous_time:{row.dispensed_at}'
    row.status, row.dispensed_by, row.dispensed_at = 'Pending', None, None
    audit(db, employee, 'prescription.correct', visit.patient_id, previous + ';reason:' + data.reason)
    return {'id': id, 'status': row.status}
