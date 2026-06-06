from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioPublico

router = APIRouter(prefix="/catalogo", tags=["Catálogo Público"])


@router.get("/produtores", response_model=list[UsuarioPublico])
def listar_produtores(
    estado: Optional[str] = None,
    tipo_produto: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Lista pública de produtores — acessível sem login."""
    q = db.query(Usuario).filter(Usuario.perfil == "produtor", Usuario.ativo == True)
    if estado:
        q = q.filter(Usuario.estado == estado.upper())
    return q.order_by(Usuario.avaliacao_media.desc()).all()


@router.get("/transportadores", response_model=list[UsuarioPublico])
def listar_transportadores(
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Lista pública de transportadores disponíveis."""
    q = db.query(Usuario).filter(Usuario.perfil == "transportador", Usuario.ativo == True)
    if estado:
        q = q.filter(Usuario.estado == estado.upper())
    return q.order_by(Usuario.avaliacao_media.desc()).all()
