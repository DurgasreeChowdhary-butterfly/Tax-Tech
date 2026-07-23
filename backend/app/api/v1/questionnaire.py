import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.engines.questionnaire.errors import (
    AmbiguousRoutingError,
    CrossQuestionnaireAnswerError,
    InvalidAnswerError,
    NoPublishedVersionError,
)
from app.models.filing_session import FilingSession
from app.schemas.questionnaire import (
    AnswerRead,
    AnswerSubmitRequest,
    CurrentQuestionResponse,
    QuestionnaireProgressRead,
    QuestionRead,
    SubmitAnswerResponse,
)
from app.services import questionnaire as questionnaire_service

router = APIRouter(prefix="/filing-sessions/{filing_session_id}/questionnaire", tags=["questionnaire"])


@router.get("/current", response_model=CurrentQuestionResponse)
def get_current_question(
    filing_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> CurrentQuestionResponse:
    try:
        question = questionnaire_service.get_current_question(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoPublishedVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AmbiguousRoutingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return CurrentQuestionResponse(
        question=QuestionRead.model_validate(question) if question else None,
        is_complete=question is None,
    )


@router.post("/answers", response_model=SubmitAnswerResponse)
def submit_answer(
    filing_session_id: uuid.UUID,
    body: AnswerSubmitRequest,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> SubmitAnswerResponse:
    try:
        answer = questionnaire_service.submit_answer(db, filing_session_id, body.question_id, body.value)
        next_question = questionnaire_service.get_current_question(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoPublishedVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (CrossQuestionnaireAnswerError, InvalidAnswerError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AmbiguousRoutingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SubmitAnswerResponse(
        answer=AnswerRead.model_validate(answer),
        next_question=QuestionRead.model_validate(next_question) if next_question else None,
        is_complete=next_question is None,
    )


@router.get("/progress", response_model=QuestionnaireProgressRead)
def get_progress(
    filing_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> QuestionnaireProgressRead:
    try:
        progress = questionnaire_service.get_progress(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoPublishedVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AmbiguousRoutingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QuestionnaireProgressRead(**progress)
