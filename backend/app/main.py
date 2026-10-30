import logging
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, InterfaceError
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.api.core import router as core_router
from backend.app.api.scheduling import router as scheduling_router
from backend.app.api.pharmacy import router as pharmacy_router
from backend.app.api.billing import router as billing_router
from backend.app.api.referrals import router as referrals_router

logger = logging.getLogger('medilink')


def create_app():
    app = FastAPI(title='MediLink NFC', version='1.0.0', description='Educational hospital system — synthetic data only')
    app.include_router(core_router)
    app.include_router(scheduling_router)
    app.include_router(pharmacy_router)
    app.include_router(billing_router)
    app.include_router(referrals_router)

    @app.get('/health')
    def health(db: Session = Depends(get_db, scope='function')):
        db.execute(text('SELECT 1'))
        return {'status': 'ok', 'database': 'postgresql'}

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, error):
        return JSONResponse(status_code=409, content={'detail': 'تعارض بيانات: سجل مكرر أو موعد متداخل أو قيمة غير مسموحة'})

    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def database_error(request, error):
        logger.error('Database unavailable (%s)', type(error).__name__)
        return JSONResponse(status_code=503, content={'detail': 'قاعدة البيانات غير متاحة؛ حاول مجدداً لاحقاً'})

    return app


app = create_app()
