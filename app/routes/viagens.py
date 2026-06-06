from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.viagem import Viagem
from app.models.usuario import Usuario
from app.schemas.viagem import (
    ViagemCriar, ViagemResposta, ViagemAceitarTransportador,
    AvaliacaoProdutor, AvaliacaoTransportador, AvaliacaoComprador
)
from app.seguranca import obter_usuario_atual

router = APIRouter(prefix="/viagens", tags=["Viagens"])


def _calcular_preco(peso_kg: float) -> float:
    """Estimativa simples: R$ 0,25/kg com mínimo de R$ 150"""
    return max(150.0, peso_kg * 0.25)


@router.post("/", response_model=ViagemResposta, status_code=201)
def criar_viagem(
    dados: ViagemCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Produtor cria viagem após aceitar demanda."""
    if usuario.perfil != "produtor":
        raise HTTPException(status_code=403, detail="Apenas produtores criam viagens.")

    preco = _calcular_preco(dados.peso_kg)
    rota = f"{dados.origem} → {dados.destino}"

    viagem = Viagem(
        **dados.model_dump(),
        produtor_id=usuario.id,
        preco_final=preco,
        rota_descricao=rota,
    )
    db.add(viagem)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.get("/", response_model=list[ViagemResposta])
def listar_viagens_abertas(db: Session = Depends(get_db)):
    """Viagens aguardando transportador — públicas para transportadores verem."""
    return (
        db.query(Viagem)
        .filter(Viagem.status == "aguardando_transportador")
        .order_by(Viagem.criado_em.desc())
        .all()
    )


@router.get("/minhas", response_model=list[ViagemResposta])
def minhas_viagens(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil == "produtor":
        return db.query(Viagem).filter(Viagem.produtor_id == usuario.id).order_by(Viagem.criado_em.desc()).all()
    elif usuario.perfil == "transportador":
        return db.query(Viagem).filter(Viagem.transportador_id == usuario.id).order_by(Viagem.criado_em.desc()).all()
    elif usuario.perfil == "comprador":
        return db.query(Viagem).filter(Viagem.comprador_id == usuario.id).order_by(Viagem.criado_em.desc()).all()
    return []


@router.get("/{viagem_id}", response_model=ViagemResposta)
def ver_viagem(viagem_id: int, db: Session = Depends(get_db)):
    v = db.query(Viagem).filter(Viagem.id == viagem_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Viagem não encontrada.")
    return v


@router.post("/{viagem_id}/aceitar", response_model=ViagemResposta)
def aceitar_viagem(
    viagem_id: int,
    dados: ViagemAceitarTransportador,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Transportador aceita uma viagem."""
    if usuario.perfil != "transportador":
        raise HTTPException(status_code=403, detail="Apenas transportadores aceitam viagens.")
    viagem = db.query(Viagem).filter(
        Viagem.id == viagem_id,
        Viagem.status == "aguardando_transportador"
    ).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não disponível.")
    viagem.transportador_id = usuario.id
    viagem.tipo_veiculo_viagem = dados.tipo_veiculo_viagem
    viagem.capacidade_veiculo = dados.capacidade_veiculo
    viagem.status = "confirmada"
    db.commit()
    db.refresh(viagem)
    return viagem


@router.post("/{viagem_id}/status/{novo_status}", response_model=ViagemResposta)
def atualizar_status(
    viagem_id: int,
    novo_status: str,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Transportador atualiza o status da viagem (coleta, em_transito, entregue)."""
    if usuario.perfil != "transportador":
        raise HTTPException(status_code=403, detail="Apenas o transportador altera o status.")
    status_validos = {"coleta", "em_transito", "entregue"}
    if novo_status not in status_validos:
        raise HTTPException(status_code=400, detail=f"Status inválido. Use: {status_validos}")
    viagem = db.query(Viagem).filter(Viagem.id == viagem_id, Viagem.transportador_id == usuario.id).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não encontrada.")
    viagem.status = novo_status
    db.commit()
    db.refresh(viagem)
    return viagem


@router.post("/{viagem_id}/avaliar/produtor", response_model=ViagemResposta)
def avaliar_como_produtor(
    viagem_id: int,
    dados: AvaliacaoProdutor,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "produtor":
        raise HTTPException(status_code=403, detail="Apenas produtor usa este endpoint.")
    viagem = db.query(Viagem).filter(Viagem.id == viagem_id, Viagem.produtor_id == usuario.id).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não encontrada.")
    if viagem.status != "entregue":
        raise HTTPException(status_code=400, detail="Só é possível avaliar após entrega.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(viagem, campo, valor)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.post("/{viagem_id}/avaliar/transportador", response_model=ViagemResposta)
def avaliar_como_transportador(
    viagem_id: int,
    dados: AvaliacaoTransportador,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "transportador":
        raise HTTPException(status_code=403, detail="Apenas transportador usa este endpoint.")
    viagem = db.query(Viagem).filter(Viagem.id == viagem_id, Viagem.transportador_id == usuario.id).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não encontrada.")
    if viagem.status != "entregue":
        raise HTTPException(status_code=400, detail="Só é possível avaliar após entrega.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(viagem, campo, valor)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.post("/{viagem_id}/avaliar/comprador", response_model=ViagemResposta)
def avaliar_como_comprador(
    viagem_id: int,
    dados: AvaliacaoComprador,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "comprador":
        raise HTTPException(status_code=403, detail="Apenas comprador usa este endpoint.")
    viagem = db.query(Viagem).filter(Viagem.id == viagem_id, Viagem.comprador_id == usuario.id).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não encontrada.")
    if viagem.status != "entregue":
        raise HTTPException(status_code=400, detail="Só é possível avaliar após entrega.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(viagem, campo, valor)
    db.commit()
    db.refresh(viagem)
    return viagem
