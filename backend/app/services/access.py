from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from backend.app.core.security import audit
from backend.app.db.models import Patient, PatientHospitalAccess, Visit, Allergy, ChronicCondition


def permitted_patient_ids(hospital_id):
    return select(PatientHospitalAccess.patient_id).where(
        PatientHospitalAccess.hospital_id == hospital_id, PatientHospitalAccess.active.is_(True))


def get_or_404(db, model, id, lock=False):
    statement = select(model).where(model.id == id)
    if lock:
        statement = statement.with_for_update()
    result = db.scalar(statement)
    if result is None:
        raise HTTPException(404, 'السجل غير موجود')
    return result


def patient_access(db, employee, patient_id):
    access = db.get(PatientHospitalAccess, (patient_id, employee.hospital_id))
    if access is None or not access.active:
        raise HTTPException(403, 'ملف المريض غير متاح لهذا المستشفى')
    return get_or_404(db, Patient, patient_id)


def local_record(record, employee):
    if record.hospital_id != employee.hospital_id:
        raise HTTPException(403, 'التعديل متاح للمستشفى المصدر فقط')
    return record


def visible_visit(db, employee, visit_id, local=False):
    visit = get_or_404(db, Visit, visit_id)
    patient_access(db, employee, visit.patient_id)
    if local:
        local_record(visit, employee)
    elif visit.hospital_id != employee.hospital_id:
        if not visit.shared:
            raise HTTPException(403, 'هذه الزيارة غير مسموح بمشاركتها')
        audit(db, employee, 'cross_hospital.read', visit.patient_id, f'visit:{visit.id};source:{visit.hospital_id}')
    return visit


def demographics(patient):
    return {key: getattr(patient, key) for key in ('id', 'full_name', 'birth_date', 'sex', 'phone')}


def patient_profile(db, employee, patient_id):
    patient = patient_access(db, employee, patient_id)
    result = demographics(patient)
    for name, model in [('allergies', Allergy), ('chronic_conditions', ChronicCondition)]:
        facts = db.scalars(select(model).where(model.patient_id == patient_id,
                           or_(model.hospital_id == employee.hospital_id, model.shared.is_(True)))).all()
        result[name] = [{'id': f.id, 'description': f.description, 'hospital_id': f.hospital_id,
                         'shared': f.shared} for f in facts]
        for fact in facts:
            if fact.hospital_id != employee.hospital_id:
                audit(db, employee, 'cross_hospital.read', patient_id, f'{name}:{fact.id};source:{fact.hospital_id}')
    visits = db.scalars(select(Visit).options(selectinload(Visit.diagnoses)).where(Visit.patient_id == patient_id,
                        or_(Visit.hospital_id == employee.hospital_id, Visit.shared.is_(True)))
                        .order_by(Visit.created_at.desc(), Visit.id.desc())).all()
    result['visits'] = []
    for visit in visits:
        result['visits'].append({'id': visit.id, 'hospital_id': visit.hospital_id, 'notes': visit.notes,
                                'shared': visit.shared, 'created_at': visit.created_at,
                                'diagnoses': [d.description for d in visit.diagnoses]})
        if visit.hospital_id != employee.hospital_id:
            audit(db, employee, 'cross_hospital.read', patient_id, f'visit:{visit.id};source:{visit.hospital_id}')
    audit(db, employee, 'patient.read', patient_id)
    return result
