import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import QuestionType


class QuestionOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: str
    label: str
    order_index: int


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    order_index: int
    question_type: QuestionType
    prompt: str
    is_required: bool
    options: list[QuestionOptionRead] = []


class CurrentQuestionResponse(BaseModel):
    question: QuestionRead | None
    is_complete: bool


class AnswerSubmitRequest(BaseModel):
    question_id: uuid.UUID
    value: Any = None


class AnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filing_session_id: uuid.UUID
    question_id: uuid.UUID
    value: Any
    is_current: bool
    created_at: datetime


class SubmitAnswerResponse(BaseModel):
    answer: AnswerRead
    next_question: QuestionRead | None
    is_complete: bool


class QuestionnaireProgressRead(BaseModel):
    total_questions: int
    answered_questions: int
    is_complete: bool
