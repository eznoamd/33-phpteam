import asyncio
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.negociacao import ContratoTransporte, NegociacaoLance, OfertaMercado
from app.models.usuario import Usuario
from app.schemas.negociacao import (
    ContratoResposta,
    ContratoStatusUpdate,
    LanceCriar,
    LanceResponder,
    LanceResposta,
    OfertaCriar,
    OfertaResposta,
)
from app.seguranca import obter_usuario_atual
from app.services import ia_preco

router = APIRouter(tags=["Marketplace"])

MODALIDADES_VALIDAS = {
    "FOB_FAZENDA", "FOB_ARMAZEM", "CIF",
    "POSTO_INDUSTRIA", "POSTO_COOPERATIVA", "POSTO_PORTO",
    "VENDA_A_RETIRAR", "BARTER",
}

RESPONSAVEL_FRETE: dict[str, str] = {
    "FOB_FAZENDA": "COMPRADOR",
    "FOB_ARMAZEM": "COMPRADOR",
    "VENDA_A_RETIRAR": "COMPRADOR",
    "BARTER": "COMPRADOR",
    "CIF": "VENDEDOR",
    "POSTO_INDUSTRIA": "VENDEDOR",
    "POSTO_COOPERATIVA": "VENDEDOR",
    "POSTO_PORTO": "VENDEDOR",
}


# ── Ofertas ──────────────────────────────────────────────────────────────────

@router.post("/ofertas/", response_model=OfertaResposta, status_code=201)
def criar_oferta(
    dados: OfertaCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil == "transportador":
        raise HTTPException(403, "Transportadores não podem criar ofertas.")
    if usuario.perfil == "produtor" and dados.tipo_demanda != "QUERO_VENDER":
        raise HTTPException(400, "Produtores só podem criar ofertas QUERO_VENDER.")
    if usuario.perfil == "comprador" and dados.tipo_demanda != "QUERO_COMPRAR":
        raise HTTPException(400, "Compradores só podem criar ofertas QUERO_COMPRAR.")

    estado = dados.estado_origem or getattr(usuario, "estado", None) or "SP"
    preco_min, preco_max = ia_preco.calcular_guardrails(
        dados.produto, dados.quantidade_total, estado
    )

    oferta = OfertaMercado(
        autor_id=usuario.id,
        tipo_demanda=dados.tipo_demanda,
        produto=dados.produto,
        quantidade_total=dados.quantidade_total,
        preco_saca_inicial=dados.preco_saca_inicial,
        data_limite_envio=dados.data_limite_envio,
        cidade_origem=dados.cidade_origem,
        estado_origem=estado,
        ia_preco_minimo=preco_min,
        ia_preco_maximo=preco_max,
        status="ABERTA",
    )
    db.add(oferta)
    db.commit()
    db.refresh(oferta)
    return oferta


@router.get("/ofertas/", response_model=list[OfertaResposta])
def listar_ofertas(
    produto: str | None = None,
    tipo_demanda: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(OfertaMercado).filter(
        OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO"])
    )
    if produto:
        q = q.filter(OfertaMercado.produto.ilike(f"%{produto}%"))
    if tipo_demanda:
        q = q.filter(OfertaMercado.tipo_demanda == tipo_demanda.upper())
    return q.order_by(OfertaMercado.id.desc()).limit(50).all()


@router.get("/ofertas/{oferta_id}", response_model=OfertaResposta)
def detalhe_oferta(oferta_id: int, db: Session = Depends(get_db)):
    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        raise HTTPException(404, "Oferta não encontrada.")
    return oferta


# ── Lances ───────────────────────────────────────────────────────────────────

@router.post("/ofertas/{oferta_id}/lances", response_model=LanceResposta, status_code=201)
def criar_lance(
    oferta_id: int,
    dados: LanceCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil == "transportador":
        raise HTTPException(403, "Transportadores não podem dar lances.")

    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        raise HTTPException(404, "Oferta não encontrada.")
    if oferta.status == "FECHADA":
        raise HTTPException(400, "Esta oferta já foi fechada.")

    if dados.modalidade_venda not in MODALIDADES_VALIDAS:
        raise HTTPException(
            400,
            f"Modalidade inválida. Opções: {', '.join(sorted(MODALIDADES_VALIDAS))}.",
        )

    total_lances = (
        db.query(NegociacaoLance)
        .filter(NegociacaoLance.oferta_id == oferta_id)
        .count()
    )
    if oferta.autor_id == usuario.id and total_lances == 0:
        raise HTTPException(400, "Aguarde outro usuário dar o primeiro lance na sua oferta.")

    ultimo_pendente = (
        db.query(NegociacaoLance)
        .filter(
            NegociacaoLance.oferta_id == oferta_id,
            NegociacaoLance.status_lance == "PENDENTE",
        )
        .order_by(NegociacaoLance.id.desc())
        .first()
    )
    if ultimo_pendente and ultimo_pendente.proponente_id == usuario.id:
        raise HTTPException(400, "Aguarde a resposta da outra parte antes de enviar um novo lance.")

    if oferta.ia_preco_minimo and dados.valor_lance_saca < oferta.ia_preco_minimo:
        raise HTTPException(
            422,
            f"Lance abaixo do mínimo da IA: R$ {oferta.ia_preco_minimo:.2f}/saca.",
        )
    if oferta.ia_preco_maximo and dados.valor_lance_saca > oferta.ia_preco_maximo:
        raise HTTPException(
            422,
            f"Lance acima do máximo da IA: R$ {oferta.ia_preco_maximo:.2f}/saca.",
        )

    if ultimo_pendente:
        ultimo_pendente.status_lance = "CONTRAPROPOSTA"
        ultimo_pendente.atualizado_em = datetime.utcnow()

    lance = NegociacaoLance(
        oferta_id=oferta_id,
        proponente_id=usuario.id,
        valor_lance_saca=dados.valor_lance_saca,
        modalidade_venda=dados.modalidade_venda,
        status_lance="PENDENTE",
    )
    db.add(lance)
    oferta.status = "EM_NEGOCIACAO"
    db.commit()
    db.refresh(lance)
    return lance


@router.post("/ofertas/{oferta_id}/lances/{lance_id}/responder")
def responder_lance(
    oferta_id: int,
    lance_id: int,
    dados: LanceResponder,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    lance = db.query(NegociacaoLance).filter(
        NegociacaoLance.id == lance_id,
        NegociacaoLance.oferta_id == oferta_id,
    ).first()
    if not lance:
        raise HTTPException(404, "Lance não encontrado.")
    if lance.status_lance != "PENDENTE":
        raise HTTPException(400, "Este lance não está mais pendente.")
    if lance.proponente_id == usuario.id:
        raise HTTPException(400, "Você não pode responder ao seu próprio lance.")

    acao = dados.acao.upper()
    if acao not in ("ACEITAR", "RECUSAR"):
        raise HTTPException(400, "Ação deve ser ACEITAR ou RECUSAR.")

    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()

    if acao == "RECUSAR":
        lance.status_lance = "RECUSADO"
        lance.atualizado_em = datetime.utcnow()
        oferta.status = "ABERTA"
        db.commit()
        return {"resultado": "RECUSADO"}

    lance.status_lance = "ACEITO"
    lance.atualizado_em = datetime.utcnow()
    oferta.status = "FECHADA"

    contrato = _criar_contrato(lance, oferta, db)
    db.commit()
    db.refresh(contrato)

    return {
        "resultado": "ACEITO",
        "contrato_id": contrato.id,
        "responsavel_frete": contrato.responsavel_frete,
        "modalidade": contrato.modalidade_venda,
        "valor_saca_final": contrato.valor_saca_final,
    }


def _criar_contrato(
    lance: NegociacaoLance,
    oferta: OfertaMercado,
    db: Session,
) -> ContratoTransporte:
    responsavel = RESPONSAVEL_FRETE.get(lance.modalidade_venda, "VENDEDOR")

    if oferta.tipo_demanda == "QUERO_VENDER":
        vendedor_id = oferta.autor_id
        comprador_id = lance.proponente_id
    else:
        comprador_id = oferta.autor_id
        vendedor_id = lance.proponente_id

    contrato = ContratoTransporte(
        negociacao_id=lance.id,
        oferta_id=oferta.id,
        vendedor_id=vendedor_id,
        comprador_id=comprador_id,
        responsavel_frete=responsavel,
        modalidade_venda=lance.modalidade_venda,
        valor_saca_final=lance.valor_lance_saca,
        status_logistica="AGUARDANDO_TRANSPORTADOR",
    )
    db.add(contrato)
    return contrato


# ── SSE ──────────────────────────────────────────────────────────────────────

@router.get("/ofertas/{oferta_id}/eventos")
async def sse_eventos(oferta_id: int, request: Request, since_id: int = 0):
    async def generate():
        ultimo_id = since_id
        ultimo_check = datetime(2000, 1, 1)
        start = time.time()
        contrato_emitido = False

        while time.time() - start < 300:
            if await request.is_disconnected():
                break

            agora = datetime.utcnow()
            db = SessionLocal()
            try:
                # Novos lances inseridos após o último visto
                novos = (
                    db.query(NegociacaoLance)
                    .filter(
                        NegociacaoLance.oferta_id == oferta_id,
                        NegociacaoLance.id > ultimo_id,
                    )
                    .order_by(NegociacaoLance.id)
                    .all()
                )
                for lance in novos:
                    payload = _lance_payload(lance)
                    yield f"event: novo_lance\ndata: {json.dumps(payload)}\n\n"
                    ultimo_id = lance.id

                # Lances já vistos cujo status mudou
                atualizados = (
                    db.query(NegociacaoLance)
                    .filter(
                        NegociacaoLance.oferta_id == oferta_id,
                        NegociacaoLance.id <= ultimo_id,
                        NegociacaoLance.atualizado_em > ultimo_check,
                    )
                    .all()
                )
                for lance in atualizados:
                    payload = _lance_payload(lance)
                    yield f"event: lance_atualizado\ndata: {json.dumps(payload)}\n\n"

                # Verifica se o contrato foi criado
                if not contrato_emitido:
                    oferta_obj = db.query(OfertaMercado).filter(
                        OfertaMercado.id == oferta_id,
                        OfertaMercado.status == "FECHADA",
                    ).first()
                    if oferta_obj:
                        contrato = db.query(ContratoTransporte).filter(
                            ContratoTransporte.oferta_id == oferta_id
                        ).first()
                        if contrato:
                            c_data = {
                                "contrato_id": contrato.id,
                                "responsavel_frete": contrato.responsavel_frete,
                                "modalidade": contrato.modalidade_venda,
                                "valor_saca_final": contrato.valor_saca_final,
                            }
                            yield f"event: contrato_criado\ndata: {json.dumps(c_data)}\n\n"
                            contrato_emitido = True
                            return
            finally:
                db.close()

            ultimo_check = agora
            await asyncio.sleep(1.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _lance_payload(lance: NegociacaoLance) -> dict:
    return {
        "id": lance.id,
        "proponente_id": lance.proponente_id,
        "valor_lance_saca": lance.valor_lance_saca,
        "modalidade_venda": lance.modalidade_venda,
        "status_lance": lance.status_lance,
        "criado_em": lance.criado_em.isoformat(),
    }


# ── Contratos ────────────────────────────────────────────────────────────────

@router.get("/contratos/", response_model=list[ContratoResposta])
def listar_contratos(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil == "transportador":
        contratos = (
            db.query(ContratoTransporte)
            .filter(ContratoTransporte.status_logistica == "AGUARDANDO_TRANSPORTADOR")
            .order_by(ContratoTransporte.id.desc())
            .all()
        )
    else:
        contratos = (
            db.query(ContratoTransporte)
            .filter(
                (ContratoTransporte.vendedor_id == usuario.id)
                | (ContratoTransporte.comprador_id == usuario.id)
                | (ContratoTransporte.transportador_id == usuario.id)
            )
            .order_by(ContratoTransporte.id.desc())
            .all()
        )
    return contratos


@router.get("/contratos/{contrato_id}", response_model=ContratoResposta)
def detalhe_contrato(
    contrato_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    partes = {contrato.vendedor_id, contrato.comprador_id, contrato.transportador_id}
    if usuario.id not in partes and usuario.perfil != "transportador":
        raise HTTPException(403, "Acesso não autorizado.")
    return contrato


@router.post("/contratos/{contrato_id}/aceitar-frete")
def aceitar_frete(
    contrato_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "transportador":
        raise HTTPException(403, "Apenas transportadores podem aceitar fretes.")
    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    if contrato.status_logistica != "AGUARDANDO_TRANSPORTADOR":
        raise HTTPException(400, "Este contrato não está aguardando transportador.")
    contrato.transportador_id = usuario.id
    contrato.status_logistica = "EM_TRANSITO"
    db.commit()
    return {"resultado": "Frete aceito.", "status_logistica": contrato.status_logistica}


@router.post("/contratos/{contrato_id}/status")
def atualizar_status_logistica(
    contrato_id: int,
    dados: ContratoStatusUpdate,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    if contrato.transportador_id != usuario.id:
        raise HTTPException(403, "Apenas o transportador responsável pode atualizar o status.")
    if dados.status not in {"EM_TRANSITO", "ENTREGUE"}:
        raise HTTPException(400, "Status deve ser EM_TRANSITO ou ENTREGUE.")
    contrato.status_logistica = dados.status
    db.commit()
    return {"resultado": "Status atualizado.", "status_logistica": contrato.status_logistica}
