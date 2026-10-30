import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.security import (audit, current_employee, hash_password, issue_token,
                                      require, role_names, verify_password)
from backend.app.db.session import get_db
from backend.app.db.models import (Employee, Patient, PatientHospitalAccess, NFCCard, Visit, Diagnosis,
                                   Allergy, ChronicCondition, Hospital, Role, AuditLog, utcnow)
from backend.app.schemas.requests import (Login, PatientInput, TokenInput, VisitInput, FactInput,
                                          AccessInput, ShareInput, HospitalInput, EmployeeInput, EmployeeUpdate)
from backend.app.services.access import patient_profile, patient_access, get_or_404, visible_visit, demographics
from backend.app.services.nfc import card_cache, token_hash

router = APIRouter(prefix='/api')
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def staff_info(employee):
    return {'id': employee.id, 'username': employee.username, 'full_name': employee.full_name,
            'hospital_id': employee.hospital_id, 'roles': sorted(role_names(employee)), 'active': employee.active}


@router.post('/auth/login')
def login(data: Login, db: Session = Depends(get_db, scope='function')):
    employee = db.scalar(select(Employee).where(Employee.username == data.username))
    valid = verify_password(data.password, employee.password_hash if employee else DUMMY_HASH)
    if not employee or not valid or not employee.active:
        audit(db, None, 'auth.failed')
        db.commit()
        raise HTTPException(401, 'اسم المستخدم أو كلمة المرور غير صحيحة')
    audit(db, employee, 'auth.login')
    return {'access_token': issue_token(employee), 'token_type': 'bearer', 'employee': staff_info(employee)}


@router.get('/auth/me')
def me(employee=Depends(current_employee)):
    return staff_info(employee)


@router.get('/hospitals')
def hospitals(employee=Depends(current_employee), db: Session = Depends(get_db, scope='function')):
    return [{'id': h.id, 'name': h.name, 'city': h.city} for h in db.scalars(select(Hospital).order_by(Hospital.id))]


@router.get('/doctors')
def doctors(employee=Depends(current_employee), db: Session = Depends(get_db, scope='function')):
    return [staff_info(e) for e in db.scalars(select(Employee).where(
        Employee.hospital_id == employee.hospital_id, Employee.active.is_(True),
        Employee.roles.any(Role.name == 'doctor')).order_by(Employee.id))]


@router.post('/patients', status_code=201)
def create_patient(data: PatientInput, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    patient = Patient(**data.model_dump())
    db.add(patient)
    db.flush()
    db.add(PatientHospitalAccess(patient_id=patient.id, hospital_id=employee.hospital_id, granted_by=employee.id))
    audit(db, employee, 'patient.create', patient.id)
    return demographics(patient)


@router.get('/patients')
def search_patients(q: str = Query('', max_length=150), employee=Depends(current_employee),
                    db: Session = Depends(get_db, scope='function')):
    statement = select(Patient).join(PatientHospitalAccess).where(
        PatientHospitalAccess.hospital_id == employee.hospital_id, PatientHospitalAccess.active.is_(True))
    if q:
        statement = statement.where(Patient.id == int(q)) if q.isdecimal() and len(q) < 10 else statement.where(
            Patient.full_name.icontains(q, autoescape=True))
    patients = db.scalars(statement.order_by(Patient.id.desc()).limit(100)).all()
    audit(db, employee, 'patient.search', detail=f'count:{len(patients)}')
    return [demographics(p) for p in patients]


@router.get('/patients/{patient_id}')
def get_patient(patient_id: int, employee=Depends(current_employee), db: Session = Depends(get_db, scope='function')):
    return patient_profile(db, employee, patient_id)


@router.put('/patients/{patient_id}')
def update_patient(patient_id: int, data: PatientInput, employee=Depends(require('receptionist')),
                   db: Session = Depends(get_db, scope='function')):
    patient = patient_access(db, employee, patient_id)
    for name, value in data.model_dump().items():
        setattr(patient, name, value)
    audit(db, employee, 'patient.update', patient_id)
    return demographics(patient)


@router.post('/patients/{patient_id}/cards', status_code=201)
def issue_card(patient_id: int, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    patient_access(db, employee, patient_id)
    get_or_404(db, Patient, patient_id, lock=True)
    old_cards = db.scalars(select(NFCCard).where(NFCCard.patient_id == patient_id, NFCCard.active.is_(True))).all()
    for old in old_cards:
        old.active, old.revoked_at = False, utcnow()
        card_cache.invalidate(old.token_hash)
    db.flush()
    token = secrets.token_hex(32)
    card = NFCCard(patient_id=patient_id, token_hash=token_hash(token))
    db.add(card)
    db.flush()
    audit(db, employee, 'nfc.replace' if old_cards else 'nfc.issue', patient_id, f'card:{card.id}')
    return {'card_id': card.id, 'token': token, 'patient_id': patient_id}


@router.delete('/patients/{patient_id}/cards')
def revoke_card(patient_id: int, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    patient_access(db, employee, patient_id)
    get_or_404(db, Patient, patient_id, lock=True)
    for card in db.scalars(select(NFCCard).where(NFCCard.patient_id == patient_id, NFCCard.active.is_(True))):
        card.active, card.revoked_at = False, utcnow()
        card_cache.invalidate(card.token_hash)
    audit(db, employee, 'nfc.revoke', patient_id)
    return {'ok': True}


@router.post('/nfc/scan')
def scan(data: TokenInput, employee=Depends(current_employee), db: Session = Depends(get_db, scope='function')):
    try:
        card = card_cache.lookup(db, data.token)
        result = patient_profile(db, employee, card.patient_id)
    except HTTPException:
        audit(db, employee, 'nfc.denied')
        db.commit()
        raise
    audit(db, employee, 'nfc.scan', card.patient_id, f'card:{card.id}')
    return result


@router.post('/visits', status_code=201)
def create_visit(data: VisitInput, employee=Depends(require('doctor')), db: Session = Depends(get_db, scope='function')):
    patient_access(db, employee, data.patient_id)
    visit = Visit(patient_id=data.patient_id, hospital_id=employee.hospital_id, doctor_id=employee.id,
                  notes=data.notes, shared=data.shared)
    db.add(visit)
    db.flush()
    if data.diagnosis:
        db.add(Diagnosis(visit_id=visit.id, description=data.diagnosis))
    audit(db, employee, 'visit.create', data.patient_id, f'visit:{visit.id}')
    return {'id': visit.id, 'hospital_id': visit.hospital_id}


@router.patch('/visits/{visit_id}/sharing')
def share_visit(visit_id: int, data: ShareInput, employee=Depends(require('doctor')), db: Session = Depends(get_db, scope='function')):
    visit = visible_visit(db, employee, visit_id, local=True)
    visit.shared = data.shared
    audit(db, employee, 'visit.sharing', visit.patient_id, f'visit:{visit.id};shared:{data.shared}')
    return {'ok': True}


@router.post('/patients/{patient_id}/facts', status_code=201)
def add_fact(patient_id: int, data: FactInput, employee=Depends(require('doctor', 'nurse')),
             db: Session = Depends(get_db, scope='function')):
    patient_access(db, employee, patient_id)
    fact = (Allergy if data.kind == 'allergy' else ChronicCondition)(patient_id=patient_id,
        hospital_id=employee.hospital_id, description=data.description, shared=data.shared)
    db.add(fact)
    db.flush()
    audit(db, employee, f'{data.kind}.create', patient_id)
    return {'id': fact.id}


@router.put('/admin/patients/{patient_id}/access')
def grant_access(patient_id: int, data: AccessInput, employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    get_or_404(db, Patient, patient_id)
    get_or_404(db, Hospital, data.hospital_id)
    access = db.get(PatientHospitalAccess, (patient_id, data.hospital_id))
    if access is None:
        access = PatientHospitalAccess(patient_id=patient_id, hospital_id=data.hospital_id, granted_by=employee.id)
        db.add(access)
    access.active = data.active
    audit(db, employee, 'access.change', patient_id, f'hospital:{data.hospital_id};active:{data.active}')
    return {'ok': True}


@router.post('/admin/hospitals', status_code=201)
def add_hospital(data: HospitalInput, employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    hospital = Hospital(**data.model_dump())
    db.add(hospital)
    db.flush()
    audit(db, employee, 'hospital.create', detail=f'hospital:{hospital.id}')
    return {'id': hospital.id}


@router.get('/admin/employees')
def employees(employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    return [staff_info(e) for e in db.scalars(select(Employee).order_by(Employee.id))]


@router.post('/admin/employees', status_code=201)
def add_employee(data: EmployeeInput, employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    get_or_404(db, Hospital, data.hospital_id)
    staff = Employee(username=data.username, full_name=data.full_name, hospital_id=data.hospital_id,
                     password_hash=hash_password(data.password), roles=list(db.scalars(
                         select(Role).where(Role.name.in_(data.roles)))))
    db.add(staff)
    db.flush()
    audit(db, employee, 'employee.create', detail=f'employee:{staff.id}')
    return staff_info(staff)


@router.put('/admin/employees/{employee_id}')
def update_employee(employee_id: int, data: EmployeeUpdate, employee=Depends(require('admin')),
                    db: Session = Depends(get_db, scope='function')):
    staff = get_or_404(db, Employee, employee_id, lock=True)
    if staff.id == employee.id:
        raise HTTPException(409, 'لا يمكنك تغيير صلاحيات حسابك الإداري الحالي')
    staff.active = data.active
    staff.roles = list(db.scalars(select(Role).where(Role.name.in_(data.roles))))
    audit(db, employee, 'employee.update', detail=f'employee:{staff.id}')
    return staff_info(staff)


@router.get('/admin/audit')
def audit_log(employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    return [{'id': a.id, 'actor_id': a.actor_id, 'hospital_id': a.hospital_id, 'patient_id': a.patient_id,
             'action': a.action, 'detail': a.detail, 'created_at': a.created_at}
            for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(500))]
