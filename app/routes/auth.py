from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import TokenResposta
from app.seguranca import verificar_senha, criar_token, obter_usuario_atual

router = APIRouter(prefix="/auth", tags=["🔐 Autenticação"])


@router.post(
    "/login",
    response_model=TokenResposta,
    summary="Login — obtém token de acesso",
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == form.username).first()

    if not usuario or not verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Entre em contato com o suporte.",
        )

    token = criar_token({"sub": str(usuario.id)})

    return TokenResposta(
        access_token=token,
        usuario_id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
    )


@router.get(
    "/eu",
    summary="Retorna dados do usuário logado (rota protegida de exemplo)",
)
def quem_sou_eu(usuario: Usuario = Depends(obter_usuario_atual)):
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "ativo": usuario.ativo,
    }
