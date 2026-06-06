from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.demanda import Demanda
from app.models.usuario import Usuario
from app.schemas.demanda import DemandaCriar, DemandaResposta
from app.seguranca import obter_usuario_atual

router = APIRouter(prefix="/demandas", tags=["Demandas"])


@router.post("/", response_model=DemandaResposta, status_code=201)
def criar_demanda(
    dados: DemandaCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "comprador":
        raise HTTPException(status_code=403, detail="Apenas compradores podem criar demandas.")
    demanda = Demanda(**dados.model_dump(), comprador_id=usuario.id)
    db.add(demanda)
    db.commit()
    db.refresh(demanda)
    return demanda


@router.get("/", response_model=list[DemandaResposta])
def listar_demandas(
    status: Optional[str] = None,
    tipo_produto: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Demandas públicas — visíveis para produtores aceitarem."""
    q = db.query(Demanda)
    if status:
        q = q.filter(Demanda.status == status)
    else:
        q = q.filter(Demanda.status == "aberta")
    if tipo_produto:
        q = q.filter(Demanda.tipo_produto.ilike(f"%{tipo_produto}%"))
    return q.order_by(Demanda.criado_em.desc()).all()


@router.get("/{demanda_id}", response_model=DemandaResposta)
def ver_demanda(demanda_id: int, db: Session = Depends(get_db)):
    d = db.query(Demanda).filter(Demanda.id == demanda_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    return d


@router.post("/{demanda_id}/aceitar", response_model=DemandaResposta)
def aceitar_demanda(
    demanda_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Produtor aceita uma demanda de um comprador."""
    if usuario.perfil != "produtor":
        raise HTTPException(status_code=403, detail="Apenas produtores podem aceitar demandas.")
    demanda = db.query(Demanda).filter(Demanda.id == demanda_id, Demanda.status == "aberta").first()
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada ou já aceita.")
    demanda.status = "aceita"
    demanda.produtor_id = usuario.id
    db.commit()
    db.refresh(demanda)
    return demanda


@router.post("/{demanda_id}/cancelar", response_model=DemandaResposta)
def cancelar_demanda(
    demanda_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    demanda = db.query(Demanda).filter(Demanda.id == demanda_id).first()
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if demanda.comprador_id != usuario.id:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    demanda.status = "cancelada"
    db.commit()
    db.refresh(demanda)
    return demanda


@router.get("/minhas/lista", response_model=list[DemandaResposta])
def minhas_demandas(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil == "comprador":
        return db.query(Demanda).filter(Demanda.comprador_id == usuario.id).order_by(Demanda.criado_em.desc()).all()
    elif usuario.perfil == "produtor":
        return db.query(Demanda).filter(Demanda.produtor_id == usuario.id).order_by(Demanda.criado_em.desc()).all()
    raise HTTPException(status_code=403, detail="Sem acesso a demandas.")
