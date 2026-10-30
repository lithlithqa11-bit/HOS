from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from backend.app.core.security import current_employee, require, audit
from backend.app.db.session import get_db
from backend.app.db.models import Referral, Hospital, HospitalConnection, PatientHospitalAccess
from backend.app.schemas.requests import ReferralInput, ReferralUpdate, ConnectionInput
from backend.app.services.access import patient_access, get_or_404
from backend.app.services.scheduling import hospital_graph, hospital_lock

router = APIRouter(prefix='/api')


@router.get('/hospital-path/{destination_id}')
def path(destination_id: int, employee=Depends(current_employee), db: Session = Depends(get_db, scope='function')):
    route = hospital_graph(db).bfs(employee.hospital_id, destination_id)
    if not route:
        raise HTTPException(404, 'لا يوجد مسار إحالة متاح')
    return {'path': route, 'hospitals': [db.get(Hospital, id).name for id in route]}


@router.get('/connections')
def connections(employee=Depends(current_employee), db: Session = Depends(get_db, scope='function')):
    return [{'source_id': e.source_id, 'destination_id': e.destination_id}
            for e in db.scalars(select(HospitalConnection))]


@router.post('/admin/connections', status_code=201)
def connect(data: ConnectionInput, employee=Depends(require('admin')), db: Session = Depends(get_db, scope='function')):
    for id in (data.source_id, data.destination_id):
        get_or_404(db, Hospital, id)
    if data.source_id == data.destination_id:
        raise HTTPException(422, 'المصدر والوجهة يجب أن يختلفا')
    db.add(HospitalConnection(**data.model_dump()))
    audit(db, employee, 'connection.create', detail=f'{data.source_id}->{data.destination_id}')
    return {'ok': True}


@router.get('/referrals')
def referrals(employee=Depends(require('doctor', 'nurse', 'receptionist')),
              db: Session = Depends(get_db, scope='function')):
    graph = hospital_graph(db)
    rows = db.scalars(select(Referral).where(or_(Referral.source_id == employee.hospital_id,
                                               Referral.destination_id == employee.hospital_id))
                      .order_by(Referral.id.desc()).limit(300))
    audit(db, employee, 'referral.list')
    return [{'id': r.id, 'patient_id': r.patient_id, 'source_id': r.source_id, 'destination_id': r.destination_id,
             'source_name': db.get(Hospital, r.source_id).name,
             'destination_name': db.get(Hospital, r.destination_id).name, 'status': r.status,
             'path': graph.bfs(r.source_id, r.destination_id),
             # Clinical reason is not part of the receptionist view.
             **({'reason': r.reason} if any(role.name in ('doctor', 'nurse') for role in employee.roles) else {})}
            for r in rows]


@router.post('/referrals', status_code=201)
def refer(data: ReferralInput, employee=Depends(require('doctor')), db: Session = Depends(get_db, scope='function')):
    patient_access(db, employee, data.patient_id)
    if data.destination_id == employee.hospital_id:
        raise HTTPException(422, 'اختر مستشفى آخر')
    route = hospital_graph(db).bfs(employee.hospital_id, data.destination_id)
    if not route:
        raise HTTPException(409, 'لا يوجد مسار إحالة بين المستشفيين')
    referral = Referral(**data.model_dump(), source_id=employee.hospital_id, created_by=employee.id)
    db.add(referral)
    db.flush()
    audit(db, employee, 'referral.create', data.patient_id, f'referral:{referral.id};path:{route}')
    return {'id': referral.id, 'path': route, 'status': referral.status}


@router.put('/referrals/{id}')
def update_referral(id: int, data: ReferralUpdate, employee=Depends(require('doctor')),
                    db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 3)
    referral = get_or_404(db, Referral, id, lock=True)
    expected = referral.source_id if data.status == 'cancelled' else referral.destination_id
    if employee.hospital_id != expected:
        raise HTTPException(403, 'تحديث الإحالة يتطلب المستشفى المختص')
    if referral.status != 'pending':
        raise HTTPException(409, 'الإحالة ليست قيد الانتظار')
    referral.status = data.status
    if data.status == 'accepted':
        access = db.get(PatientHospitalAccess, (referral.patient_id, employee.hospital_id))
        if access:
            access.active = True
            access.granted_by = employee.id
        else:
            db.add(PatientHospitalAccess(patient_id=referral.patient_id, hospital_id=employee.hospital_id,
                                         granted_by=employee.id))
    audit(db, employee, 'referral.' + data.status, referral.patient_id, f'referral:{id}')
    return {'id': id, 'status': referral.status}
