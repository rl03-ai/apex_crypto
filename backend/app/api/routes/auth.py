from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserOut, UserRegister
from app.api.deps import CurrentUser

router = APIRouter()


@router.post('/register', response_model=TokenResponse, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email já registado')
    user = User(email=payload.email, name=payload.name, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)


@router.post('/login', response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Credenciais inválidas')
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)


@router.get('/me', response_model=UserOut)
def me(current_user: CurrentUser) -> User:
    return current_user
