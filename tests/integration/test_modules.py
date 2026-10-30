from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.app.main import create_app
from backend.app.db.models import EmergencyCase, Payment, Appointment
from backend.app.db.session import SessionLocal
from backend.app.services.scheduling import waiting_queue, emergency_heap


def book_payload(patient=1, doctor=2, start='2026-11-01T09:00:00+03:00', end='2026-11-01T09:30:00+03:00'):
    return {'patient_id': patient, 'doctor_id': doctor, 'starts_at': start, 'ends_at': end}


def new_invoice(client, headers):
    result = client.post('/api/invoices', headers=headers, json={'patient_id': 1, 'discount': '10.00',
        'items': [{'description': 'خدمة تدريبية', 'quantity': 2, 'unit_price': '50.00'}]})
    assert result.status_code == 201, result.text
    return result.json()


def new_prescription(client, doctor):
    visit = client.post('/api/visits', headers=doctor, json={'patient_id': 1, 'shared': True}).json()['id']
    response = client.post('/api/prescriptions', headers=doctor, json={'visit_id': visit, 'items': [
        {'medication_id': 1, 'dose': 'جرعة تدريبية', 'instructions': 'تعليمات وهمية فقط'}]})
    assert response.status_code == 201, response.text
    return response.json()


def test_appointments_conflicts_update_cancel_and_queue(client, auth):
    receptionist = auth()
    first = client.post('/api/appointments', headers=receptionist, json=book_payload())
    assert first.status_code == 201, first.text
    id = first.json()['id']
    assert client.post('/api/appointments', headers=receptionist, json=book_payload(2)).status_code == 409
    assert client.post('/api/appointments', headers=receptionist, json=book_payload(2, 3)).status_code == 422
    adjacent = book_payload(2, start='2026-11-01T09:30:00+03:00', end='2026-11-01T10:00:00+03:00')
    second = client.post('/api/appointments', headers=receptionist, json=adjacent)
    assert second.status_code == 201
    assert client.put(f'/api/appointments/{id}', headers=receptionist,
                      json=book_payload(start=adjacent['starts_at'], end=adjacent['ends_at'])).status_code == 409
    for row_id in (second.json()['id'], id):
        assert client.post(f'/api/appointments/{row_id}/check-in', headers=receptionist).status_code == 200
    assert client.post(f'/api/appointments/{id}/check-in', headers=receptionist).status_code == 409
    queue = client.get('/api/waiting-queue', headers=receptionist).json()
    assert [row['id'] for row in queue] == [second.json()['id'], id]
    with SessionLocal() as db:
        assert [row.id for row in waiting_queue(db, 1)] == [second.json()['id'], id]
    assert client.post('/api/waiting-queue/next', headers=auth('nurse')).json()['id'] == second.json()['id']
    assert client.post(f'/api/appointments/{id}/cancel', headers=receptionist).status_code == 200
    assert client.get('/api/waiting-queue', headers=receptionist).json() == []
    assert client.post('/api/appointments', headers=receptionist, json=book_payload()).status_code == 201


def test_appointment_concurrent_overlap(client, auth):
    headers = auth()
    def create(patient):
        with TestClient(create_app()) as concurrent:
            return concurrent.post('/api/appointments', headers=headers, json=book_payload(patient)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, [1, 2]))
    assert sorted(results) == [201, 409]


def test_emergency_ties_update_restart_and_next(client, auth):
    nurse = auth('nurse')
    ids = []
    for patient, priority in [(1, 3), (2, 3), (3, 1)]:
        response = client.post('/api/emergencies', headers=nurse, json={'patient_id': patient, 'priority': priority})
        assert response.status_code == 201, response.text
        ids.append(response.json()['id'])
    with SessionLocal.begin() as db:
        for id in ids:
            db.get(EmergencyCase, id).arrived_at = datetime(2026, 10, 30, tzinfo=timezone.utc)
    assert [r['id'] for r in client.get('/api/emergencies', headers=nurse).json()] == [ids[2], ids[0], ids[1]]
    assert client.put(f'/api/emergencies/{ids[1]}', headers=nurse,
                      json={'priority': 1, 'status': 'waiting'}).status_code == 200
    with SessionLocal() as db:
        heap = emergency_heap(db, 1)
        assert [heap.extract_min().id for _ in range(len(heap))] == [ids[1], ids[2], ids[0]]
    with TestClient(create_app()) as restarted:
        assert restarted.post('/api/emergencies/next', headers=nurse).json()['id'] == ids[1]
    assert client.put(f'/api/emergencies/{ids[1]}', headers=nurse,
                      json={'priority': 2, 'status': 'discharged'}).status_code == 200
    assert client.put(f'/api/emergencies/{ids[1]}', headers=nurse,
                      json={'priority': 2, 'status': 'waiting'}).status_code == 409
    assert client.post('/api/emergencies', headers=auth(), json={'patient_id': 1, 'priority': 1}).status_code == 403
    assert client.get('/api/emergencies', headers=auth('nurse', 'b')).json() == []


def test_prescriptions_dispense_correction_and_cross_hospital(client, auth):
    doctor, pharmacist, admin = auth('doctor'), auth('pharmacist'), auth('admin')
    row = new_prescription(client, doctor)
    id = row['id']
    assert client.post(f'/api/prescriptions/{id}/dispense', headers=doctor).status_code == 403
    assert client.post(f'/api/prescriptions/{id}/dispense', headers=auth('pharmacist', 'b')).status_code == 403
    result = client.post(f'/api/prescriptions/{id}/dispense', headers=pharmacist)
    assert result.status_code == 200 and result.json()['dispensed_by'] == 4
    assert result.json()['dispensed_at'] is not None
    assert client.post(f'/api/prescriptions/{id}/dispense', headers=pharmacist).status_code == 409
    assert client.post(f'/api/prescriptions/{id}/correct', headers=admin,
                       json={'reason': 'تصحيح تدريبي مصرح'}).status_code == 200
    assert client.post(f'/api/prescriptions/{id}/dispense', headers=pharmacist).status_code == 200
    assert client.get('/api/prescriptions', headers=auth()).status_code == 403
    assert 'notes' not in client.get('/api/prescriptions', headers=pharmacist).json()[0]


def test_concurrent_dispense_once(client, auth):
    id = new_prescription(client, auth('doctor'))['id']
    headers = auth('pharmacist')
    def dispense(_):
        with TestClient(create_app()) as concurrent:
            return concurrent.post(f'/api/prescriptions/{id}/dispense', headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(dispense, range(2))) == [200, 409]


def test_invoice_decimal_multiple_payments_and_idempotency(client, auth):
    headers = auth()
    invoice = new_invoice(client, headers)
    id = invoice['id']
    assert Decimal(invoice['total']) == Decimal('90.00')
    payment = {'amount': '30.10', 'request_key': str(uuid4())}
    for _ in range(2):
        result = client.post(f'/api/invoices/{id}/payments', headers=headers, json=payment)
        assert result.status_code == 201, result.text
        assert Decimal(result.json()['remaining']) == Decimal('59.90')
    assert client.post(f'/api/invoices/{id}/payments', headers=headers,
                       json={'amount': '30.11', 'request_key': payment['request_key']}).status_code == 409
    assert client.post(f'/api/invoices/{id}/payments', headers=headers,
                       json={'amount': '60.00', 'request_key': str(uuid4())}).status_code == 409
    assert client.post(f'/api/invoices/{id}/payments', headers=headers,
                       json={'amount': '59.90', 'request_key': str(uuid4())}).json()['remaining'] == '0.00'
    assert client.post(f'/api/invoices/{id}/items', headers=headers,
                       json={'description': 'late', 'quantity': 1, 'unit_price': '1'}).status_code == 409
    assert client.get(f'/api/invoices/{id}', headers=auth('receptionist', 'b')).status_code == 403
    assert client.get('/api/invoices', headers=auth('doctor')).status_code == 403
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Payment).where(Payment.invoice_id == id)))) == 2


def test_concurrent_payments_cannot_overpay(client, auth):
    headers = auth()
    id = new_invoice(client, headers)['id']
    def pay(_):
        with TestClient(create_app()) as concurrent:
            return concurrent.post(f'/api/invoices/{id}/payments', headers=headers,
                                   json={'amount': '60.00', 'request_key': str(uuid4())}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(pay, range(2))) == [201, 409]
    assert client.get(f'/api/invoices/{id}', headers=headers).json()['remaining'] == '30.00'


def test_referral_graph_acceptance_and_shared_record(client, auth):
    doctor_a, doctor_b = auth('doctor'), auth('doctor', 'b')
    visit = client.post('/api/visits', headers=doctor_a, json={'patient_id': 1, 'shared': True,
                                                           'diagnosis': 'تشخيص تدريبي'}).json()
    response = client.post('/api/referrals', headers=doctor_a,
                           json={'patient_id': 1, 'destination_id': 2, 'reason': 'إحالة تعليمية'})
    assert response.status_code == 201 and response.json()['path'] == [1, 2]
    id = response.json()['id']
    assert client.get('/api/hospital-path/2', headers=doctor_a).json()['path'] == [1, 2]
    assert client.get('/api/patients/1', headers=doctor_b).status_code == 403
    assert client.put(f'/api/referrals/{id}', headers=doctor_a, json={'status': 'accepted'}).status_code == 403
    assert client.put(f'/api/referrals/{id}', headers=doctor_b, json={'status': 'accepted'}).status_code == 200
    assert client.get('/api/patients/1', headers=doctor_b).json()['visits'][0]['id'] == visit['id']
    assert client.post('/api/visits', headers=doctor_b, json={'patient_id': 1}).status_code == 201
    assert client.put(f'/api/referrals/{id}', headers=doctor_b, json={'status': 'accepted'}).status_code == 409
    assert client.get('/api/referrals', headers=doctor_b).json()[0]['source_id'] == 1
    assert 'reason' not in client.get('/api/referrals', headers=auth()).json()[0]


def test_concurrent_queue_and_emergency_next_are_distinct(client, auth):
    receptionist, nurse = auth(), auth('nurse')
    first = client.post('/api/appointments', headers=receptionist, json=book_payload()).json()['id']
    second = client.post('/api/appointments', headers=receptionist, json=book_payload(2,
        start='2026-11-01T10:00:00+03:00', end='2026-11-01T10:30:00+03:00')).json()['id']
    for id in (first, second):
        client.post(f'/api/appointments/{id}/check-in', headers=receptionist)
    for patient in (1, 2):
        client.post('/api/emergencies', headers=nurse, json={'patient_id': patient, 'priority': 2})
    for path, headers in [('/api/waiting-queue/next', receptionist), ('/api/emergencies/next', nurse)]:
        def take(_):
            with TestClient(create_app()) as concurrent:
                response = concurrent.post(path, headers=headers)
                assert response.status_code == 200, response.text
                return response.json()['id']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(take, range(2)))
        assert len(set(results)) == 2
    with SessionLocal() as db:
        assert all(a.status == 'completed' for a in db.scalars(select(Appointment)))
