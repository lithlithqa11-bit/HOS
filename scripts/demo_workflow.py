"""Execute the 16-step university acceptance scenario through the running API.

Adds synthetic records without deleting anything. Secrets only in ignored .runtime.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
import httpx


def main():
    load_dotenv()
    base = os.getenv('API_URL', 'http://127.0.0.1:8000')
    clients = {}
    with httpx.Client(base_url=base, timeout=15, trust_env=False) as connection:
        def call(role, method, path, data=None):
            response = connection.request(method, path, json=data, headers=clients.get(role, {}))
            if response.is_error:
                raise RuntimeError(f'{method} {path}: {response.status_code} {response.text}')
            return response.json()
        call('', 'GET', '/health')
        for name in ('receptionist.a', 'doctor.a', 'nurse.a', 'pharmacist.a', 'admin.a', 'doctor.b'):
            login = call('', 'POST', '/api/auth/login', {'username': name, 'password': os.environ['DEMO_PASSWORD']})
            clients[name] = {'Authorization': 'Bearer ' + login['access_token']}
        receptionist, doctor, nurse = 'receptionist.a', 'doctor.a', 'nurse.a'
        patient = call(receptionist, 'POST', '/api/patients', {'full_name': 'مريض العرض الجامعي — بيانات وهمية',
                        'birth_date': '2003-05-15', 'sex': 'male', 'phone': '00000000000'})
        pid = patient['id']
        card = call(receptionist, 'POST', f'/api/patients/{pid}/cards')
        assert call(receptionist, 'POST', '/api/nfc/scan', {'token': card['token']})['id'] == pid
        doctors = call(receptionist, 'GET', '/api/doctors')
        start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
        existing = call(receptionist, 'GET', '/api/appointments')
        while any(row['doctor_id'] == doctors[0]['id'] and row['status'] != 'cancelled' and
                  datetime.fromisoformat(row['starts_at']) < start + timedelta(minutes=30) and
                  datetime.fromisoformat(row['ends_at']) > start for row in existing):
            start += timedelta(minutes=30)
        appointment = call(receptionist, 'POST', '/api/appointments', {'patient_id': pid,
                           'doctor_id': doctors[0]['id'], 'starts_at': start.isoformat(),
                           'ends_at': (start + timedelta(minutes=30)).isoformat()})
        call(receptionist, 'POST', f"/api/appointments/{appointment['id']}/check-in")
        emergency = call(nurse, 'POST', '/api/emergencies', {'patient_id': pid, 'priority': 3,
                         'notes': 'حالة عرض تعليمية؛ الأولوية أدخلها موظف مخول'})
        call(nurse, 'PUT', f"/api/emergencies/{emergency['id']}", {'priority': 2, 'status': 'waiting'})
        visit = call(doctor, 'POST', '/api/visits', {'patient_id': pid, 'notes': 'زيارة مشاركة للعرض الجامعي',
                     'diagnosis': 'تشخيص تعليمي وهمي', 'shared': True})
        private = call(doctor, 'POST', '/api/visits', {'patient_id': pid, 'notes': 'زيارة خاصة بالمستشفى A',
                       'diagnosis': 'بيانات وهمية غير مشاركة', 'shared': False})
        call(doctor, 'POST', f'/api/patients/{pid}/facts', {'kind': 'allergy', 'description': 'حساسية تجريبية', 'shared': True})
        call(doctor, 'POST', f'/api/patients/{pid}/facts', {'kind': 'chronic', 'description': 'حالة مزمنة تعليمية', 'shared': True})
        medications = call(doctor, 'GET', '/api/medications')
        prescription = call(doctor, 'POST', '/api/prescriptions', {'visit_id': visit['id'], 'items': [
            {'medication_id': medications[0]['id'], 'dose': 'جرعة وهمية للعرض فقط', 'instructions': 'لا يستخدم كإرشاد طبي'}]})
        call('pharmacist.a', 'POST', f"/api/prescriptions/{prescription['id']}/dispense")
        invoice = call(receptionist, 'POST', '/api/invoices', {'patient_id': pid, 'visit_id': visit['id'],
            'discount': '5000.00', 'items': [{'description': 'زيارة تعليمية', 'quantity': 1, 'unit_price': '25000.00'},
                                            {'description': 'خدمة تدريبية', 'quantity': 1, 'unit_price': '10000.00'}]})
        invoice = call(receptionist, 'POST', f"/api/invoices/{invoice['id']}/payments",
                       {'amount': '10000.00', 'request_key': str(uuid4())})
        destination = call('doctor.b', 'GET', '/api/auth/me')['hospital_id']
        referral = call(doctor, 'POST', '/api/referrals', {'patient_id': pid, 'destination_id': destination,
                        'reason': 'إحالة تعليمية لاستعراض الربط بين المستشفيات'})
        call('doctor.b', 'PUT', f"/api/referrals/{referral['id']}", {'status': 'accepted'})
        visit_b = call('doctor.b', 'POST', '/api/visits', {'patient_id': pid, 'notes': 'زيارة في المستشفى B',
                       'diagnosis': 'متابعة تعليمية وهمية', 'shared': True})
        b_profile = call('doctor.b', 'GET', f'/api/patients/{pid}')
        assert visit['id'] in [v['id'] for v in b_profile['visits']]
        assert private['id'] not in [v['id'] for v in b_profile['visits']]
        logs = call('admin.a', 'GET', '/api/admin/audit')
        assert any(log['action'] == 'cross_hospital.read' and log['patient_id'] == pid for log in logs)
        summary = {'patient_id': pid, 'appointment_id': appointment['id'], 'emergency_id': emergency['id'],
                   'shared_visit_a': visit['id'], 'private_visit_a': private['id'], 'visit_b': visit_b['id'],
                   'prescription_id': prescription['id'], 'invoice_id': invoice['id'],
                   'invoice_remaining': invoice['remaining'], 'referral_id': referral['id'], 'path': referral['path'],
                   'completed_at': datetime.now(timezone.utc).isoformat()}
        runtime = Path('.runtime')
        runtime.mkdir(exist_ok=True)
        (runtime / 'demo-run.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        (runtime / 'demo-card-token.txt').write_text(card['token'], encoding='ascii')
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        print('Acceptance workflow succeeded. Demo token saved only in ignored .runtime/demo-card-token.txt')


if __name__ == '__main__':
    main()
