import os
from fastapi.testclient import TestClient
from backend.app.main import create_app


def patient_payload(name='مريض اختبار جديد'):
    return {'full_name': name, 'birth_date': '2002-03-04', 'sex': 'male', 'phone': '000000000'}


def test_health_and_login(client, auth):
    assert client.get('/health').json() == {'status': 'ok', 'database': 'postgresql'}
    assert client.get('/api/patients').status_code == 401
    for username, password in [('unknown', 'bad'), ('doctor.a', 'bad')]:
        assert client.post('/api/auth/login', json={'username': username, 'password': password}).status_code == 401
    assert client.get('/api/auth/me', headers=auth('doctor')).json()['roles'] == ['doctor']
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer forged'}).status_code == 401


def test_core_workflow_and_revocation(client, auth):
    headers = auth()
    created = client.post('/api/patients', headers=headers, json=patient_payload())
    assert created.status_code == 201, created.text
    patient_id = created.json()['id']
    card = client.post(f'/api/patients/{patient_id}/cards', headers=headers)
    assert card.status_code == 201, card.text
    token = card.json()['token']
    for _ in range(2):
        scan = client.post('/api/nfc/scan', headers=headers, json={'token': token})
        assert scan.status_code == 200 and scan.json()['id'] == patient_id
    assert client.post('/api/nfc/scan', headers=headers, json={'token': '0' * 64}).status_code == 404
    new = client.post(f'/api/patients/{patient_id}/cards', headers=headers).json()['token']
    assert new != token
    assert client.post('/api/nfc/scan', headers=headers, json={'token': token}).status_code == 404
    assert client.delete(f'/api/patients/{patient_id}/cards', headers=headers).status_code == 200
    assert client.post('/api/nfc/scan', headers=headers, json={'token': new}).status_code == 404
    update = client.put(f'/api/patients/{patient_id}', headers=headers, json=patient_payload('اسم معدل'))
    assert update.json()['full_name'] == 'اسم معدل'
    assert client.get('/api/patients?q=اسم', headers=headers).json()[0]['id'] == patient_id


def test_role_and_hospital_projections(client, auth):
    doctor, receptionist, nurse, pharmacist = auth('doctor'), auth(), auth('nurse'), auth('pharmacist')
    for role in ('doctor', 'nurse', 'pharmacist', 'admin'):
        assert client.post('/api/patients', headers=auth(role), json=patient_payload()).status_code == 403
    for headers in (receptionist, nurse, pharmacist):
        assert client.post('/api/visits', headers=headers, json={'patient_id': 1}).status_code == 403
    assert client.post('/api/visits', headers=doctor, json={'patient_id': 1, 'notes': 'private'}).status_code == 201
    assert 'visits' in client.get('/api/patients/1', headers=doctor).json()
    assert 'visits' not in client.get('/api/patients/1', headers=nurse).json()
    for headers in (receptionist, pharmacist):
        result = client.get('/api/patients/1', headers=headers).json()
        assert 'visits' not in result and 'allergies' not in result
    assert client.get('/api/patients/1', headers=auth('doctor', 'b')).status_code == 403
    assert client.get('/api/patients', headers=auth('receptionist', 'b')).json() == []


def test_cross_hospital_sharing_and_audit(client, auth):
    a, b, admin = auth('doctor'), auth('doctor', 'b'), auth('admin')
    for shared in (False, True):
        assert client.post('/api/visits', headers=a, json={'patient_id': 1, 'notes': str(shared),
                           'diagnosis': 'demo', 'shared': shared}).status_code == 201
    assert client.put('/api/admin/patients/1/access', headers=admin,
                       json={'hospital_id': 2, 'active': True}).status_code == 200
    profile = client.get('/api/patients/1', headers=b).json()
    assert len(profile['visits']) == 1 and profile['visits'][0]['notes'] == 'True'
    assert client.post('/api/visits', headers=b, json={'patient_id': 1, 'notes': 'B visit'}).status_code == 201
    logs = client.get('/api/admin/audit', headers=admin).json()
    assert any(log['action'] == 'cross_hospital.read' and log['hospital_id'] == 2 for log in logs)
    client.put('/api/admin/patients/1/access', headers=admin, json={'hospital_id': 2, 'active': False})
    assert client.get('/api/patients/1', headers=b).status_code == 403


def test_restart_persists_patient_and_nfc(client, auth):
    headers = auth()
    token = client.post('/api/patients/1/cards', headers=headers).json()['token']
    with TestClient(create_app()) as restarted:
        login = restarted.post('/api/auth/login', json={'username': 'receptionist.a',
                                                       'password': os.environ['DEMO_PASSWORD']}).json()
        result = restarted.post('/api/nfc/scan', headers={'Authorization': 'Bearer ' + login['access_token']},
                                json={'token': token})
        assert result.status_code == 200 and result.json()['id'] == 1
