from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.app.core.security import require, audit
from backend.app.db.session import get_db
from backend.app.db.models import Invoice, InvoiceItem, Payment, Visit
from backend.app.schemas.requests import InvoiceInput, InvoiceItemInput, PaymentInput
from backend.app.services.access import get_or_404, patient_access, local_record, permitted_patient_ids

router = APIRouter(prefix='/api')


def invoice_data(db, row):
    items = list(db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == row.id).order_by(InvoiceItem.id)))
    payments = list(db.scalars(select(Payment).where(Payment.invoice_id == row.id).order_by(Payment.id)))
    subtotal = sum((i.quantity * i.unit_price for i in items), Decimal('0.00'))
    paid = sum((p.amount for p in payments), Decimal('0.00'))
    return {'id': row.id, 'patient_id': row.patient_id, 'hospital_id': row.hospital_id,
            'visit_id': row.visit_id, 'created_at': row.created_at, 'currency': 'IQD',
            'subtotal': str(subtotal), 'discount': str(row.discount), 'total': str(subtotal - row.discount),
            'paid': str(paid), 'remaining': str(subtotal - row.discount - paid),
            'items': [{'id': i.id, 'description': i.description, 'quantity': i.quantity,
                       'unit_price': str(i.unit_price)} for i in items],
            'payments': [{'id': p.id, 'amount': str(p.amount), 'received_by': p.received_by,
                          'paid_at': p.paid_at} for p in payments]}


@router.post('/invoices', status_code=201)
def create_invoice(data: InvoiceInput, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    patient_access(db, employee, data.patient_id)
    if data.visit_id is not None:
        visit = local_record(get_or_404(db, Visit, data.visit_id), employee)
        if visit.patient_id != data.patient_id:
            raise HTTPException(422, 'الزيارة تخص مريضاً آخر')
    row = Invoice(patient_id=data.patient_id, hospital_id=employee.hospital_id, visit_id=data.visit_id,
                  discount=data.discount, items=[InvoiceItem(**item.model_dump()) for item in data.items])
    db.add(row)
    db.flush()
    audit(db, employee, 'invoice.create', row.patient_id, f'invoice:{row.id}')
    return invoice_data(db, row)


@router.get('/invoices')
def list_invoices(patient_id: int | None = None, employee=Depends(require('receptionist')),
                  db: Session = Depends(get_db, scope='function')):
    statement = select(Invoice).where(Invoice.hospital_id == employee.hospital_id,
                                     Invoice.patient_id.in_(permitted_patient_ids(employee.hospital_id)))
    if patient_id is not None:
        patient_access(db, employee, patient_id)
        statement = statement.where(Invoice.patient_id == patient_id)
    audit(db, employee, 'invoice.list')
    return [invoice_data(db, row) for row in db.scalars(statement.order_by(Invoice.id.desc()).limit(300))]


@router.get('/invoices/{id}')
def get_invoice(id: int, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    row = local_record(get_or_404(db, Invoice, id), employee)
    patient_access(db, employee, row.patient_id)
    audit(db, employee, 'invoice.read', row.patient_id, f'invoice:{id}')
    return invoice_data(db, row)


@router.post('/invoices/{id}/items', status_code=201)
def add_item(id: int, data: InvoiceItemInput, employee=Depends(require('receptionist')),
             db: Session = Depends(get_db, scope='function')):
    row = local_record(get_or_404(db, Invoice, id, lock=True), employee)
    patient_access(db, employee, row.patient_id)
    if db.scalar(select(Payment.id).where(Payment.invoice_id == id).limit(1)) is not None:
        raise HTTPException(409, 'لا تُعدل بنود فاتورة بدأ سدادها؛ أنشئ فاتورة خدمة جديدة')
    existing = Decimal(invoice_data(db, row)['subtotal'])
    if existing + data.quantity * data.unit_price > Decimal('9999999999.99'):
        raise HTTPException(422, 'المجموع يتجاوز الحد المسموح')
    db.add(InvoiceItem(invoice_id=id, **data.model_dump()))
    db.flush()
    audit(db, employee, 'invoice.item_add', row.patient_id, f'invoice:{id}')
    return invoice_data(db, row)


@router.post('/invoices/{id}/payments', status_code=201)
def pay(id: int, data: PaymentInput, employee=Depends(require('receptionist')), db: Session = Depends(get_db, scope='function')):
    row = local_record(get_or_404(db, Invoice, id, lock=True), employee)
    patient_access(db, employee, row.patient_id)
    prior = db.scalar(select(Payment).where(Payment.request_key == data.request_key))
    if prior:
        if prior.invoice_id != id or prior.amount != data.amount:
            raise HTTPException(409, 'مفتاح الطلب مستخدم لدفعة أخرى')
        return invoice_data(db, row)
    subtotal = db.scalar(select(func.sum(InvoiceItem.quantity * InvoiceItem.unit_price)).where(
                           InvoiceItem.invoice_id == id)) or Decimal('0')
    paid = db.scalar(select(func.sum(Payment.amount)).where(Payment.invoice_id == id)) or Decimal('0')
    if data.amount > subtotal - row.discount - paid:
        raise HTTPException(409, 'الدفعة تتجاوز المبلغ المتبقي')
    db.add(Payment(invoice_id=id, amount=data.amount, request_key=data.request_key, received_by=employee.id))
    db.flush()
    audit(db, employee, 'payment.create', row.patient_id, f'invoice:{id};amount:{data.amount}')
    return invoice_data(db, row)
