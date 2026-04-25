from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

DBSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)
_settings = get_settings()


def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """Valida JWT e devolve o utilizador.

    Em modo DEBUG, se não houver token, devolve o primeiro user da DB —
    facilita testes locais via Swagger sem ter de copiar tokens.
    Em produção (DEBUG=false), exige sempre token válido.
    """
    if credentials is None:
        if _settings.debug:
            user = db.query(User).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='Sem utilizador. Regista-te em POST /auth/register',
                )
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Falta o header Authorization: Bearer <token>',
        )

    try:
        user_id = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token inválido ou expirado',
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Utilizador não encontrado')
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
