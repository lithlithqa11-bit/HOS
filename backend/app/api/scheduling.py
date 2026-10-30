from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.security import require, audit, role_names
from backend.app.db.session import get_db
from backend.app.db.models import Appointment, EmergencyCase, Employee, Patient, utcnow
from backend.app.schemas.requests import AppointmentInput, EmergencyInput, EmergencyUpdate
from backend.app.services.access import patient_access, get_or_404, local_record, permitted_patient_ids
from backend.app.services.scheduling import waiting_queue, emergency_heap, hospital_lock

router = APIRouter(prefix='/api')


def appointment_data(db, row):
    return {'id': row.id, 'patient_id': row.patient_id, 'patient_name': db.get(Patient, row.patient_id).full_name,
            'doctor_id': row.doctor_id, 'hospital_id': row.hospital_id, 'starts_at': row.starts_at,
            'ends_at': row.ends_at, 'status': row.status, 'checked_in_at': row.checked_in_at}


def validate_appointment(db, employee, data):
    patient_access(db, employee, data.patient_id)
    doctor = get_or_404(db, Employee, data.doctor_id)
    if doctor.hospital_id != employee.hospital_id or not doctor.active or 'doctor' not in role_names(doctor):
        raise HTTPException(422, 'اختر طبيباً فعالاً من مستشفاك')


@router.get('/appointments')
def appointments(employee=Depends(require('receptionist', 'doctor', 'nurse')), db: Session = Depends(get_db, scope='function')):
    rows = db.scalars(select(Appointment).where(Appointment.hospital_id == employee.hospital_id)
                      .where(Appointment.patient_id.in_(permitted_patient_ids(employee.hospital_id)))
                      .order_by(Appointment.starts_at.desc()).limit(300))
    audit(db, employee, 'appointments.read')
    return [appointment_data(db, row) for row in rows]


@router.post('/appointments', status_code=201)
def book(data: AppointmentInput, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    validate_appointment(db, employee, data)
    row = Appointment(**data.model_dump(), hospital_id=employee.hospital_id)
    db.add(row)
    db.flush()  # PostgreSQL exclusion constraint is the concurrency authority.
    audit(db, employee, 'appointment.create', row.patient_id, f'appointment:{row.id}')
    return appointment_data(db, row)


@router.put('/appointments/{id}')
def reschedule(id: int, data: AppointmentInput, employee=Depends(require('receptionist')),
               db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 1)
    row = local_record(get_or_404(db, Appointment, id, lock=True), employee)
    patient_access(db, employee, row.patient_id)
    if row.status != 'booked' or row.patient_id != data.patient_id:
        raise HTTPException(409, 'يمكن تعديل موعد محجوز فقط، دون تغيير المريض')
    validate_appointment(db, employee, data)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.flush()
    audit(db, employee, 'appointment.update', row.patient_id, f'appointment:{id}')
    return appointment_data(db, row)


@router.post('/appointments/{id}/cancel')
def cancel(id: int, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 1)
    row = local_record(get_or_404(db, Appointment, id, lock=True), employee)
    patient_access(db, employee, row.patient_id)
    if row.status not in ('booked', 'waiting'):
        raise HTTPException(409, 'لا يمكن إلغاء هذا الموعد')
    row.status = 'cancelled'
    audit(db, employee, 'appointment.cancel', row.patient_id, f'appointment:{id}')
    return {'ok': True}


@router.post('/appointments/{id}/check-in')
def check_in(id: int, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 1)
    row = local_record(get_or_404(db, Appointment, id, lock=True), employee)
    patient_access(db, employee, row.patient_id)
    if row.status != 'booked':
        raise HTTPException(409, 'الموعد ليس في حالة الحجز')
    row.status, row.checked_in_at = 'waiting', utcnow()
    db.flush()
    queue = waiting_queue(db, employee.hospital_id)
    audit(db, employee, 'appointment.check_in', row.patient_id, f'appointment:{id}')
    return {'appointment_id': id, 'queue_length': len(queue)}


@router.get('/waiting-queue')
def queue_list(employee=Depends(require('receptionist', 'doctor', 'nurse')), db: Session = Depends(get_db, scope='function')):
    audit(db, employee, 'queue.read')
    return [appointment_data(db, row) for row in waiting_queue(db, employee.hospital_id)]


@router.post('/waiting-queue/next')
def queue_next(employee=Depends(require('receptionist', 'doctor', 'nurse')), db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 1)
    queue = waiting_queue(db, employee.hospital_id)
    if queue.is_empty():
        raise HTTPException(404, 'طابور المراجعين فارغ')
    row = queue.dequeue()
    patient_access(db, employee, row.patient_id)
    row.status = 'completed'
    audit(db, employee, 'queue.next', row.patient_id, f'appointment:{row.id}')
    return appointment_data(db, row)


def emergency_data(db, row):
    return {'id': row.id, 'patient_id': row.patient_id, 'patient_name': db.get(Patient, row.patient_id).full_name,
            'hospital_id': row.hospital_id, 'priority': row.priority, 'status': row.status,
            'arrived_at': row.arrived_at, 'notes': row.notes, 'triaged_by': row.triaged_by}


@router.get('/emergencies')
def emergencies(employee=Depends(require('doctor', 'nurse')), db: Session = Depends(get_db, scope='function')):
    heap = emergency_heap(db, employee.hospital_id)
    waiting = [emergency_data(db, heap.extract_min().value) for _ in range(len(heap))]
    others = db.scalars(select(EmergencyCase).where(EmergencyCase.hospital_id == employee.hospital_id,
                        EmergencyCase.patient_id.in_(permitted_patient_ids(employee.hospital_id)),
                        EmergencyCase.status != 'waiting').order_by(EmergencyCase.arrived_at.desc()).limit(100))
    audit(db, employee, 'emergency.read')
    return waiting + [emergency_data(db, row) for row in others]


@router.post('/emergencies', status_code=201)
def triage(data: EmergencyInput, employee=Depends(require('doctor', 'nurse')), db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 2)
    patient_access(db, employee, data.patient_id)
    row = EmergencyCase(**data.model_dump(), hospital_id=employee.hospital_id, triaged_by=employee.id)
    db.add(row)
    db.flush()
    heap = emergency_heap(db, employee.hospital_id)
    audit(db, employee, 'emergency.create', row.patient_id, f'case:{row.id};priority:{row.priority}')
    return {**emergency_data(db, row), 'next_case_id': heap.peek().id}


@router.put('/emergencies/{id}')
def update_triage(id: int, data: EmergencyUpdate, employee=Depends(require('doctor', 'nurse')),
                  db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 2)
    row = local_record(get_or_404(db, EmergencyCase, id, lock=True), employee)
    patient_access(db, employee, row.patient_id)
    if row.status == 'discharged':
        raise HTTPException(409, 'الحالة مغلقة؛ سجّل حالة جديدة عند الحاجة')
    if row.status == 'treating' and data.status == 'waiting':
        raise HTTPException(409, 'لا يمكن إعادة حالة قيد العلاج إلى الانتظار')
    if row.status == 'waiting':
        heap = emergency_heap(db, employee.hospital_id)
        row.priority = heap.update_priority(row.id, data.priority).priority
    else:
        row.priority = data.priority
    row.status, row.triaged_by = data.status, employee.id
    audit(db, employee, 'emergency.update', row.patient_id, f'case:{id};priority:{data.priority};status:{data.status}')
    return emergency_data(db, row)


@router.post('/emergencies/next')
def emergency_next(employee=Depends(require('doctor', 'nurse')), db: Session = Depends(get_db, scope='function')):
    hospital_lock(db, employee.hospital_id, 2)
    heap = emergency_heap(db, employee.hospital_id)
    if not len(heap):
        raise HTTPException(404, 'لا توجد حالات طوارئ منتظرة')
    row = heap.extract_min().value
    patient_access(db, employee, row.patient_id)
    row.status = 'treating'
    audit(db, employee, 'emergency.next', row.patient_id, f'case:{row.id}')
    return emergency_data(db, row)
