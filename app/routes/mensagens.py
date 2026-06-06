from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mensagem import Mensagem
from app.models.usuario import Usuario
from app.schemas.mensagem import MensagemEnviar, MensagemResposta
from app.seguranca import obter_usuario_atual

router = APIRouter(prefix="/mensagens", tags=["Mensagens"])

# Regras de comunicação:
# comprador <-> produtor: OK
# produtor <-> transportador: OK
# comprador <-> transportador: NÃO PERMITIDO

PERMITIDO = {
    ("comprador", "produtor"),
    ("produtor", "comprador"),
    ("produtor", "transportador"),
    ("transportador", "produtor"),
}


@router.post("/", response_model=MensagemResposta, status_code=201)
def enviar_mensagem(
    dados: MensagemEnviar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    destinatario = db.query(Usuario).filter(Usuario.id == dados.destinatario_id).first()
    if not destinatario:
        raise HTTPException(status_code=404, detail="Destinatário não encontrado.")

    par = (usuario.perfil, destinatario.perfil)
    if par not in PERMITIDO:
        raise HTTPException(
            status_code=403,
            detail=f"Comunicação entre {usuario.perfil} e {destinatario.perfil} não é permitida."
        )

    msg = Mensagem(
        remetente_id=usuario.id,
        destinatario_id=dados.destinatario_id,
        viagem_id=dados.viagem_id,
        texto=dados.texto,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/conversa/{outro_id}", response_model=list[MensagemResposta])
def ver_conversa(
    outro_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    msgs = (
        db.query(Mensagem)
        .filter(
            (
                (Mensagem.remetente_id == usuario.id) & (Mensagem.destinatario_id == outro_id)
            ) | (
                (Mensagem.remetente_id == outro_id) & (Mensagem.destinatario_id == usuario.id)
            )
        )
        .order_by(Mensagem.criado_em.asc())
        .all()
    )
    # marcar como lidas
    for m in msgs:
        if m.destinatario_id == usuario.id and not m.lida:
            m.lida = True
    db.commit()
    return msgs


@router.get("/nao-lidas/count")
def contar_nao_lidas(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    count = db.query(Mensagem).filter(
        Mensagem.destinatario_id == usuario.id,
        Mensagem.lida == False
    ).count()
    return {"nao_lidas": count}
