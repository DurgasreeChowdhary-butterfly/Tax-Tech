from fastapi import APIRouter

from app.api.v1.decision import router as decision_router
from app.api.v1.health import router as health_router
from app.api.v1.questionnaire import router as questionnaire_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(questionnaire_router)
api_router.include_router(decision_router)
