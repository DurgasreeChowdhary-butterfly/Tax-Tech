from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPairResponse
from app.schemas.user import UserRead
from app.services import auth as auth_service
from app.services.auth_errors import EmailAlreadyRegisteredError, InvalidCredentialsError, InvalidRefreshTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = auth_service.register_user(db, email=body.email, password=body.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPairResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenPairResponse:
    try:
        pair = auth_service.login(db, email=body.email, password=body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="Incorrect email or password") from exc
    return TokenPairResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPairResponse:
    try:
        pair = auth_service.refresh_tokens(db, body.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    return TokenPairResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=204)
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> Response:
    auth_service.logout(db, body.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
