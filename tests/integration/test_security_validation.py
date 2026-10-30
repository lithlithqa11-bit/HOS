from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
from uuid import uuid4
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.models import NFCCard, Payment
from backend.app.db.session import get_db, SessionLocal
from backend.app.main import create_app


@pytest.mark.parametrize('role,allowed,denied', [
    ('doctor', '/api/prescriptions', '/api/invoices'),
    ('nurse', '/api/emergencies', '/api/prescriptions'),
    ('pharmacist', '/api/prescriptions', '/api/emergencies'),
    ('receptionist', '/api/invoices', '/api/admin/audit'),
    ('admin', '/api/admin/audit', '/api/prescriptions'),
])
def test_role_matrix(client, auth, role, allowed, denied):
    headers = auth(role)
    assert client.get(allowed, headers=headers).status_code == 200
    assert client.get(denied, headers=headers).status_code == 403


def test_expired_and_tampered_token_and_deactivated_staff(client, auth):
    headers = auth('doctor')
    token = headers['Authorization'].split()[1]
    payload = jwt.decode(token, settings().jwt_secret, algorithms=['HS256'], audience='medilink-desktop')
    payload['exp'] = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired = jwt.encode(payload, settings().jwt_secret, algorithm='HS256')
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + expired}).status_code == 401
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token[:-8] + 'tampered'}).status_code == 401
    assert client.put('/api/admin/employees/2', headers=auth('admin'),
                       json={'active': False, 'roles': ['doctor']}).status_code == 200
    assert client.get('/api/auth/me', headers=headers).status_code == 401


def test_validation_transactions_and_injection(client, auth):
    receptionist, doctor, nurse = auth(), auth('doctor'), auth('nurse')
    bad_patients = [
        {'full_name': '', 'birth_date': '2000-01-01', 'sex': 'male'},
        {'full_name': 'test', 'birth_date': '2999-01-01', 'sex': 'male'},
        {'full_name': 'test', 'birth_date': '2000-01-01', 'sex': 'male', 'hospital_id': 2},
    ]
    for payload in bad_patients:
        assert client.post('/api/patients', headers=receptionist, json=payload).status_code == 422
    assert client.get("/api/patients?q=' OR 1=1 --", headers=receptionist).json() == []
    for priority in (0, 6):
        assert client.post('/api/emergencies', headers=nurse, json={'patient_id': 1, 'priority': priority}).status_code == 422
    assert client.post('/api/nfc/scan', headers=receptionist, json={'token': 'UID1234'}).status_code == 422
    visit = client.post('/api/visits', headers=doctor, json={'patient_id': 1}).json()['id']
    # A failed FK must not leave a partial prescription behind.
    assert client.post('/api/prescriptions', headers=doctor, json={'visit_id': visit, 'items': [
        {'medication_id': 999999, 'dose': 'demo', 'instructions': 'demo'}]}).status_code == 404
    assert client.get('/api/prescriptions', headers=doctor).json() == []
    assert client.post('/api/invoices', headers=receptionist, json={'patient_id': 1, 'discount': '100',
        'items': [{'description': 'x', 'quantity': 1, 'unit_price': '1.00'}]}).status_code == 422
    assert client.post('/api/invoices', headers=receptionist, json={'patient_id': 1,
        'items': [{'description': 'x', 'quantity': 1, 'unit_price': '1.001'}]}).status_code == 422


def test_nfc_cache_rechecks_database_and_permissions(client, auth):
    receptionist = auth()
    token = client.post('/api/patients/1/cards', headers=receptionist).json()['token']
    assert client.post('/api/nfc/scan', headers=receptionist, json={'token': token}).status_code == 200
    assert client.post('/api/nfc/scan', headers=auth('doctor', 'b'), json={'token': token}).status_code == 403
    # Simulate revocation by a different API process (no local cache invalidation).
    with SessionLocal.begin() as db:
        card = db.scalar(select(NFCCard).where(NFCCard.patient_id == 1))
        card.active = False
    assert client.post('/api/nfc/scan', headers=receptionist, json={'token': token}).status_code == 404


def test_access_revocation_removes_list_results(client, auth):
    receptionist, nurse, admin = auth(), auth('nurse'), auth('admin')
    appointment = client.post('/api/appointments', headers=receptionist, json={'patient_id': 1, 'doctor_id': 2,
        'starts_at': '2026-11-01T12:00:00Z', 'ends_at': '2026-11-01T12:30:00Z'}).json()['id']
    client.post(f'/api/appointments/{appointment}/check-in', headers=receptionist)
    client.post('/api/emergencies', headers=nurse, json={'patient_id': 1, 'priority': 2})
    client.post('/api/invoices', headers=receptionist, json={'patient_id': 1,
        'items': [{'description': 'demo', 'quantity': 1, 'unit_price': '10'}]})
    assert client.put('/api/admin/patients/1/access', headers=admin, json={'hospital_id': 1, 'active': False}).status_code == 200
    for path in ('/api/appointments', '/api/waiting-queue', '/api/invoices'):
        assert client.get(path, headers=receptionist).json() == []
    assert client.get('/api/emergencies', headers=nurse).json() == []


def test_private_prescription_and_cross_hospital_mutation(client, auth):
    a, b, admin = auth('doctor'), auth('doctor', 'b'), auth('admin')
    visit = client.post('/api/visits', headers=a, json={'patient_id': 1, 'shared': False}).json()['id']
    prescription = client.post('/api/prescriptions', headers=a, json={'visit_id': visit, 'items': [
        {'medication_id': 1, 'dose': 'demo', 'instructions': 'demo'}]}).json()['id']
    client.put('/api/admin/patients/1/access', headers=admin, json={'hospital_id': 2, 'active': True})
    pharmacist = auth('pharmacist', 'b')
    assert client.get('/api/prescriptions', headers=pharmacist).json() == []
    assert client.post(f'/api/prescriptions/{prescription}/dispense', headers=pharmacist).status_code == 403
    assert client.patch(f'/api/visits/{visit}/sharing', headers=b, json={'shared': True}).status_code == 403
    assert client.patch(f'/api/visits/{visit}/sharing', headers=a, json={'shared': True}).status_code == 200
    assert len(client.get('/api/prescriptions', headers=pharmacist).json()) == 1
    assert client.post(f'/api/prescriptions/{prescription}/dispense', headers=pharmacist).status_code == 200


def test_database_connection_failure_returns_503():
    app = create_app()
    unavailable = create_engine('postgresql+psycopg://invalid:invalid@127.0.0.1:1/unavailable',
                                connect_args={'connect_timeout': 1})
    def broken_db():
        with Session(unavailable) as session:
            yield session
    app.dependency_overrides[get_db] = broken_db
    try:
        with TestClient(app) as api:
            response = api.get('/health')
            assert response.status_code == 503
            assert 'قاعدة البيانات' in response.json()['detail']
            assert 'invalid' not in response.text
    finally:
        unavailable.dispose()


def test_fresh_python_process_recovers_queue_heap_and_graph(client, auth):
    receptionist, nurse = auth(), auth('nurse')
    appointment = client.post('/api/appointments', headers=receptionist, json={'patient_id': 1, 'doctor_id': 2,
        'starts_at': '2026-11-01T12:00:00Z', 'ends_at': '2026-11-01T12:30:00Z'}).json()['id']
    client.post(f'/api/appointments/{appointment}/check-in', headers=receptionist)
    case = client.post('/api/emergencies', headers=nurse, json={'patient_id': 1, 'priority': 2}).json()['id']
    code = '''
import json
from backend.app.db.session import SessionLocal
from backend.app.services.scheduling import waiting_queue, emergency_heap, hospital_graph
with SessionLocal() as db:
    print(json.dumps({'queue': [r.id for r in waiting_queue(db, 1)],
                      'heap': emergency_heap(db, 1).peek().id,
                      'path': hospital_graph(db).bfs(1, 2)}))
'''
    result = subprocess.run([sys.executable, '-c', code], env=os.environ.copy(), text=True,
                             capture_output=True, timeout=15,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'queue': [appointment], 'heap': case, 'path': [1, 2]}


def test_concurrent_idempotent_payment_returns_same_balance(client, auth):
    headers = auth()
    id = client.post('/api/invoices', headers=headers, json={'patient_id': 1,
        'items': [{'description': 'demo', 'quantity': 1, 'unit_price': '100'}]}).json()['id']
    data = {'amount': '10', 'request_key': str(uuid4())}
    def pay(_):
        with TestClient(create_app()) as concurrent:
            response = concurrent.post(f'/api/invoices/{id}/payments', headers=headers, json=data)
            assert response.status_code == 201, response.text
            return response.json()['remaining']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(pay, range(2))) == ['90.00', '90.00']
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Payment)))) == 1
