from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, field_validator, model_validator

Text150 = Annotated[str, Field(min_length=1, max_length=150)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(Input):
    username: Annotated[str, Field(min_length=1, max_length=80)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class PatientInput(Input):
    full_name: Text150
    birth_date: date
    sex: Literal['male', 'female', 'other']
    phone: Annotated[str, Field(max_length=30)] = ''

    @field_validator('birth_date')
    @classmethod
    def not_future(cls, value):
        if value > date.today() or value.year < 1900:
            raise ValueError('تاريخ الولادة غير صالح')
        return value


class TokenInput(Input):
    token: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class VisitInput(Input):
    patient_id: int = Field(gt=0)
    notes: str = Field(default='', max_length=5000)
    diagnosis: str = Field(default='', max_length=2000)
    shared: bool = False


class FactInput(Input):
    kind: Literal['allergy', 'chronic']
    description: Annotated[str, Field(min_length=1, max_length=500)]
    shared: bool = False


class ShareInput(Input):
    shared: bool


class AccessInput(Input):
    hospital_id: int = Field(gt=0)
    active: bool = True


class AppointmentInput(Input):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode='after')
    def valid_period(self):
        seconds = (self.ends_at - self.starts_at).total_seconds()
        if not 60 <= seconds <= 8 * 3600:
            raise ValueError('مدة الموعد من دقيقة إلى ثماني ساعات')
        return self


class EmergencyInput(Input):
    patient_id: int = Field(gt=0)
    priority: int = Field(ge=1, le=5)
    notes: str = Field(default='', max_length=2000)


class EmergencyUpdate(Input):
    priority: int = Field(ge=1, le=5)
    status: Literal['waiting', 'treating', 'discharged']


class PrescriptionItemInput(Input):
    medication_id: int = Field(gt=0)
    dose: Text150
    instructions: Annotated[str, Field(min_length=1, max_length=500)]


class PrescriptionInput(Input):
    visit_id: int = Field(gt=0)
    items: list[PrescriptionItemInput] = Field(min_length=1, max_length=30)


class CorrectionInput(Input):
    reason: Annotated[str, Field(min_length=5, max_length=300)]


class InvoiceItemInput(Input):
    description: Annotated[str, Field(min_length=1, max_length=200)]
    quantity: int = Field(ge=1, le=10000)
    unit_price: Money


class InvoiceInput(Input):
    patient_id: int = Field(gt=0)
    visit_id: int | None = Field(default=None, gt=0)
    discount: Money = Decimal('0')
    items: list[InvoiceItemInput] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def totals(self):
        total = sum(item.quantity * item.unit_price for item in self.items)
        if self.discount > total or total > Decimal('9999999999.99'):
            raise ValueError('الخصم أو مجموع الفاتورة غير صالح')
        return self


class PaymentInput(Input):
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    request_key: Annotated[str, Field(min_length=16, max_length=64)]


class ReferralInput(Input):
    patient_id: int = Field(gt=0)
    destination_id: int = Field(gt=0)
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class ReferralUpdate(Input):
    status: Literal['accepted', 'rejected', 'cancelled']


class HospitalInput(Input):
    name: Text150
    city: Annotated[str, Field(min_length=1, max_length=100)]


class EmployeeInput(Input):
    username: Annotated[str, Field(pattern=r'^[a-zA-Z0-9_.-]{3,80}$')]
    full_name: Text150
    hospital_id: int = Field(gt=0)
    password: Annotated[str, Field(min_length=12, max_length=256)]
    roles: list[Literal['admin', 'doctor', 'nurse', 'pharmacist', 'receptionist']] = Field(min_length=1)


class EmployeeUpdate(Input):
    active: bool
    roles: list[Literal['admin', 'doctor', 'nurse', 'pharmacist', 'receptionist']] = Field(min_length=1)


class ConnectionInput(Input):
    source_id: int = Field(gt=0)
    destination_id: int = Field(gt=0)
