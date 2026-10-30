from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.models import Employee, AuditLog
from backend.app.db.session import get_db

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
ROLES = ('admin', 'doctor', 'nurse', 'pharmacist', 'receptionist')


def hash_password(password):
    return hasher.hash(password)


def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_token(employee):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(employee.id), 'iat': now, 'exp': now + timedelta(minutes=settings().token_minutes),
                       'iss': 'medilink', 'aud': 'medilink-desktop'}, settings().jwt_secret, algorithm='HS256')


def current_employee(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db, scope='function')):
    try:
        if credentials is None:
            raise ValueError()
        payload = jwt.decode(credentials.credentials, settings().jwt_secret, algorithms=['HS256'],
                             issuer='medilink', audience='medilink-desktop',
                             options={'require': ['sub', 'iat', 'exp']})
        employee = db.get(Employee, int(payload['sub']))
        if employee is None or not employee.active:
            raise ValueError()
        return employee
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(401, 'جلسة غير صالحة أو منتهية؛ سجّل الدخول مجدداً') from None


def role_names(employee):
    return {role.name for role in employee.roles}


def require(*allowed):
    def dependency(employee: Employee = Depends(current_employee)):
        if not role_names(employee).intersection(allowed):
            raise HTTPException(403, 'لا تملك صلاحية تنفيذ هذه العملية')
        return employee
    return dependency


def audit(db, employee, action, patient_id=None, detail=''):
    db.add(AuditLog(actor_id=employee.id if employee else None,
                    hospital_id=employee.hospital_id if employee else None,
                    patient_id=patient_id, action=action, detail=detail[:500]))
