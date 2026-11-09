"""Canonical PostgreSQL model registry. All timestamps are timezone aware UTC."""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ExcludeConstraint


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[int] = mapped_column(primary_key=True)


class Hospital(Identity, Base):
    __tablename__ = 'hospitals'
    name: Mapped[str] = mapped_column(String(150), unique=True)
    city: Mapped[str] = mapped_column(String(100))
    departments: Mapped[list['Department']] = relationship(back_populates='hospital')


class Department(Identity, Base):
    __tablename__ = 'departments'
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    hospital: Mapped[Hospital] = relationship(back_populates='departments')
    __table_args__ = (UniqueConstraint('hospital_id', 'name'),)


class EmployeeRole(Base):
    __tablename__ = 'employee_roles'
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'), primary_key=True)


class Role(Identity, Base):
    __tablename__ = 'roles'
    name: Mapped[str] = mapped_column(String(30), unique=True)


class Employee(Identity, Base):
    __tablename__ = 'employees'
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    roles: Mapped[list[Role]] = relationship(secondary='employee_roles', lazy='selectin')


class Patient(Identity, Base):
    __tablename__ = 'patients'
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    birth_date: Mapped[date]
    sex: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str] = mapped_column(String(30), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    visits: Mapped[list['Visit']] = relationship(back_populates='patient')
    __table_args__ = (CheckConstraint("sex IN ('male','female','other')", name='patient_sex'),)


class NFCCard(Identity, Base):
    __tablename__ = 'nfc_cards'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index('one_active_card', 'patient_id', unique=True, postgresql_where=text('active')),)


class PatientHospitalAccess(Base):
    __tablename__ = 'patient_hospital_access'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), primary_key=True)
    active: Mapped[bool] = mapped_column(default=True)
    granted_by: Mapped[int] = mapped_column(ForeignKey('employees.id'))


class Visit(Identity, Base):
    __tablename__ = 'visits'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey('employees.id'))
    notes: Mapped[str] = mapped_column(Text, default='')
    shared: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    patient: Mapped[Patient] = relationship(back_populates='visits')
    diagnoses: Mapped[list['Diagnosis']] = relationship(back_populates='visit')


class Diagnosis(Identity, Base):
    __tablename__ = 'diagnoses'
    visit_id: Mapped[int] = mapped_column(ForeignKey('visits.id'), index=True)
    description: Mapped[str] = mapped_column(Text)
    visit: Mapped[Visit] = relationship(back_populates='diagnoses')


class ClinicalFact:
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'))
    description: Mapped[str] = mapped_column(String(500))
    shared: Mapped[bool] = mapped_column(default=True)


class Allergy(Identity, ClinicalFact, Base):
    __tablename__ = 'allergies'


class ChronicCondition(Identity, ClinicalFact, Base):
    __tablename__ = 'chronic_conditions'


class Medication(Identity, Base):
    __tablename__ = 'medications'
    name: Mapped[str] = mapped_column(String(150), unique=True)


class Prescription(Identity, Base):
    __tablename__ = 'prescriptions'
    visit_id: Mapped[int] = mapped_column(ForeignKey('visits.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='Pending')
    dispensed_by: Mapped[int | None] = mapped_column(ForeignKey('employees.id'))
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list['PrescriptionItem']] = relationship(lazy='selectin')
    __table_args__ = (
        CheckConstraint("status IN ('Pending','Dispensed')", name='prescription_status'),
        CheckConstraint("(status='Pending' AND dispensed_at IS NULL AND dispensed_by IS NULL) OR "
                        "(status='Dispensed' AND dispensed_at IS NOT NULL AND dispensed_by IS NOT NULL)",
                        name='dispensing_consistent'),)


class PrescriptionItem(Identity, Base):
    __tablename__ = 'prescription_items'
    prescription_id: Mapped[int] = mapped_column(ForeignKey('prescriptions.id'), index=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey('medications.id'))
    dose: Mapped[str] = mapped_column(String(150))
    instructions: Mapped[str] = mapped_column(String(500))


class Appointment(Identity, Base):
    __tablename__ = 'appointments'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='booked')
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint('ends_at > starts_at', name='appointment_duration'),
        CheckConstraint("status IN ('booked','waiting','completed','cancelled')", name='appointment_status'),
        ExcludeConstraint(('doctor_id', '='), (text("tstzrange(starts_at, ends_at, '[)')"), '&&'),
                          where=text("status <> 'cancelled'"), name='doctor_no_overlap', using='gist'),
        ExcludeConstraint(('patient_id', '='), (text("tstzrange(starts_at, ends_at, '[)')"), '&&'),
                          where=text("status <> 'cancelled'"), name='patient_no_overlap', using='gist'),
        Index('waiting_order', 'hospital_id', 'checked_in_at', 'id'),)


class EmergencyCase(Identity, Base):
    __tablename__ = 'emergency_cases'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    priority: Mapped[int] = mapped_column(Integer)
    triaged_by: Mapped[int] = mapped_column(ForeignKey('employees.id'))
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default='waiting')
    notes: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (
        CheckConstraint('priority BETWEEN 1 AND 5', name='triage_priority'),
        CheckConstraint("status IN ('waiting','treating','discharged')", name='emergency_status'),
        Index('emergency_order', 'hospital_id', 'status', 'priority', 'arrived_at'),)


class HospitalConnection(Base):
    __tablename__ = 'hospital_connections'
    source_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), primary_key=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), primary_key=True)
    __table_args__ = (CheckConstraint('source_id <> destination_id', name='no_self_connection'),)


class Referral(Identity, Base):
    __tablename__ = 'referrals'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('employees.id'))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        CheckConstraint('source_id <> destination_id', name='referral_different_hospitals'),
        CheckConstraint("status IN ('pending','accepted','rejected','cancelled')", name='referral_status'),)


class Invoice(Identity, Base):
    __tablename__ = 'invoices'
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id'), index=True)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey('visits.id'))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal('0'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list['InvoiceItem']] = relationship(lazy='selectin')
    payments: Mapped[list['Payment']] = relationship(lazy='selectin')
    __table_args__ = (CheckConstraint('discount >= 0', name='nonnegative_discount'),)


class InvoiceItem(Identity, Base):
    __tablename__ = 'invoice_items'
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'), index=True)
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    __table_args__ = (CheckConstraint('quantity > 0 AND unit_price >= 0', name='valid_invoice_item'),)


class Payment(Identity, Base):
    __tablename__ = 'payments'
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    received_by: Mapped[int] = mapped_column(ForeignKey('employees.id'))
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (CheckConstraint('amount > 0', name='positive_payment'),)


class AuditLog(Identity, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id'), index=True)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey('hospitals.id'), index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey('patients.id'), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    detail: Mapped[str] = mapped_column(String(500), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
