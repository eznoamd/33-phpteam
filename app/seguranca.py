from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, hash: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), hash.encode("utf-8"))


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

COOKIE_NAME = "agrohub_session"


def criar_token(dados: dict) -> str:
    payload = dados.copy()
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expiracao})
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def obter_usuario_atual(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    from app.models.usuario import Usuario

    erro = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Tenta Bearer header; se ausente ou inválido, cai no cookie de sessão
    resolved = None
    if token:
        try:
            jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            resolved = token
        except JWTError:
            pass  # Bearer inválido (ex: "undefined") → tenta cookie

    if resolved is None:
        resolved = request.cookies.get(COOKIE_NAME)

    if not resolved:
        raise erro

    try:
        payload = jwt.decode(resolved, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        usuario_id: str = payload.get("sub")
        if usuario_id is None:
            raise erro
    except JWTError:
        raise erro

    usuario = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
    if usuario is None or not usuario.ativo:
        raise erro
    return usuario
