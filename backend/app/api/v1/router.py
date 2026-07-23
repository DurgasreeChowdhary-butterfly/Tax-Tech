from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.consent import router as consent_router
from app.api.v1.decision import router as decision_router
from app.api.v1.deduction import router as deduction_router
from app.api.v1.document import router as document_router
from app.api.v1.extraction import router as extraction_router
from app.api.v1.health import router as health_router
from app.api.v1.questionnaire import router as questionnaire_router
from app.api.v1.supported_case import router as supported_case_router
from app.api.v1.tax_calculation import router as tax_calculation_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(questionnaire_router)
api_router.include_router(decision_router)
api_router.include_router(document_router)
api_router.include_router(extraction_router)
api_router.include_router(supported_case_router)
api_router.include_router(deduction_router)
api_router.include_router(tax_calculation_router)
api_router.include_router(consent_router)
