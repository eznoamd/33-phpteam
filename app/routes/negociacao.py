import asyncio
import json
import time
from datetime import date, timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.negociacao import ContratoTransporte, LanceFrete, NegociacaoLance, OfertaMercado
from app.models.usuario import Usuario
from app.schemas.negociacao import (
    ContratoResposta,
    ContratoStatusUpdate,
    LanceCriar,
    LanceFreteCriar,
    LanceFreteResponder,
    LanceFreteResposta,
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

    hoje = date.today()
    daqui_um_ano = hoje + timedelta(days=365)
    if dados.data_limite_envio < hoje:
        raise HTTPException(400, "A data limite não pode ser no passado.")
    if dados.data_limite_envio > daqui_um_ano:
        raise HTTPException(400, "A data limite não pode ultrapassar 1 ano a partir de hoje.")

    estado = (dados.estado_origem or dados.estado_destino) or getattr(usuario, "estado", None) or "SP"
    preco_min, preco_max = ia_preco.calcular_guardrails(
        dados.produto.value, dados.quantidade_total, estado
    )

    oferta = OfertaMercado(
        autor_id=usuario.id,
        tipo_demanda=dados.tipo_demanda,
        produto=dados.produto.value,
        quantidade_total=dados.quantidade_total,
        unidade_medida=dados.unidade_medida.value if dados.unidade_medida else "SACAS",
        tipo_frete_sugerido=dados.tipo_frete_sugerido.value if dados.tipo_frete_sugerido else None,
        preco_unidade_inicial=dados.preco_unidade_inicial,
        data_limite_envio=dados.data_limite_envio,
        cidade_origem=dados.cidade_origem,
        estado_origem=dados.estado_origem,
        cidade_destino=dados.cidade_destino,
        estado_destino=dados.estado_destino,
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
        OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO", "AGUARDANDO_ACEITE"])
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
        raise HTTPException(403, "Transportadores não podem dar lances em ofertas de mercadoria.")

    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        raise HTTPException(404, "Oferta não encontrada.")
    if oferta.status not in ("ABERTA", "EM_NEGOCIACAO", "AGUARDANDO_ACEITE"):
        raise HTTPException(400, "Esta oferta já foi fechada.")

    if oferta.autor_id == usuario.id:
        raise HTTPException(400, "Use 'Publicar preço' para propor um valor aberto que qualquer par pode aceitar.")
    if dados.modalidade_venda not in MODALIDADES_VALIDAS:
        raise HTTPException(400, f"Modalidade inválida. Opções: {', '.join(sorted(MODALIDADES_VALIDAS))}.")
    if dados.valor_lance_saca <= 0:
        raise HTTPException(400, "O valor deve ser maior que zero.")
    if oferta.ia_preco_minimo and dados.valor_lance_saca < float(oferta.ia_preco_minimo):
        raise HTTPException(422, f"Valor abaixo do mínimo sugerido (R$ {float(oferta.ia_preco_minimo):.2f}/saca).")
    if oferta.ia_preco_maximo and dados.valor_lance_saca > float(oferta.ia_preco_maximo):
        raise HTTPException(422, f"Valor acima do máximo sugerido (R$ {float(oferta.ia_preco_maximo):.2f}/saca).")

    lance = NegociacaoLance(
        oferta_id=oferta_id,
        proponente_id=usuario.id,
        valor_lance_saca=dados.valor_lance_saca,
        modalidade_venda=dados.modalidade_venda,
        status_lance="PENDENTE",
    )
    db.add(lance)
    if oferta.status == "ABERTA":
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

    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        raise HTTPException(404, "Oferta não encontrada.")
    if oferta.autor_id != usuario.id:
        raise HTTPException(403, "Apenas o criador da oferta pode aceitar ou recusar lances.")

    acao = dados.acao.upper()
    if acao not in ("ACEITAR", "RECUSAR"):
        raise HTTPException(400, "Ação deve ser ACEITAR ou RECUSAR.")

    if acao == "RECUSAR":
        lance.status_lance = "RECUSADO"
        lance.atualizado_em = datetime.utcnow()
        restantes = db.query(NegociacaoLance).filter(
            NegociacaoLance.oferta_id == oferta_id,
            NegociacaoLance.status_lance == "PENDENTE",
            NegociacaoLance.id != lance_id,
        ).count()
        if oferta.status not in ("AGUARDANDO_ACEITE",):
            oferta.status = "EM_NEGOCIACAO" if restantes > 0 else "ABERTA"
        db.commit()
        return {"resultado": "RECUSADO"}

    lance.status_lance = "ACEITO"
    lance.atualizado_em = datetime.utcnow()
    _rejeitar_pendentes_oferta(oferta_id, exceto_id=lance_id, novo_status="RECUSADO_AUTO", db=db)
    oferta.contra_valor_saca = None
    oferta.contra_modalidade_venda = None
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


def _rejeitar_pendentes_oferta(oferta_id: int, exceto_id: int | None, novo_status: str, db: Session):
    q = db.query(NegociacaoLance).filter(
        NegociacaoLance.oferta_id == oferta_id,
        NegociacaoLance.status_lance == "PENDENTE",
    )
    if exceto_id:
        q = q.filter(NegociacaoLance.id != exceto_id)
    for l in q.all():
        l.status_lance = novo_status
        l.atualizado_em = datetime.utcnow()


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


@router.post("/ofertas/{oferta_id}/contra-proposta")
def contra_proposta_oferta(
    oferta_id: int,
    dados: LanceCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        raise HTTPException(404, "Oferta não encontrada.")
    if oferta.autor_id != usuario.id:
        raise HTTPException(403, "Apenas o autor da oferta pode publicar contra-proposta.")
    if oferta.status not in ("EM_NEGOCIACAO", "AGUARDANDO_ACEITE"):
        raise HTTPException(400, "Contra-proposta só é possível durante negociação.")
    if dados.modalidade_venda not in MODALIDADES_VALIDAS:
        raise HTTPException(400, f"Modalidade inválida. Opções: {', '.join(sorted(MODALIDADES_VALIDAS))}.")
    if dados.valor_lance_saca <= 0:
        raise HTTPException(400, "O valor deve ser maior que zero.")

    _rejeitar_pendentes_oferta(oferta_id, exceto_id=None, novo_status="RECUSADO_AUTO", db=db)
    oferta.contra_valor_saca = dados.valor_lance_saca
    oferta.contra_modalidade_venda = dados.modalidade_venda
    oferta.status = "AGUARDANDO_ACEITE"
    db.commit()
    return {
        "resultado": "CONTRA_PROPOSTA_PUBLICADA",
        "contra_valor_saca": oferta.contra_valor_saca,
        "contra_modalidade_venda": oferta.contra_modalidade_venda,
    }


@router.post("/ofertas/{oferta_id}/aceitar-contra-oferta")
def aceitar_contra_oferta_oferta(
    oferta_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil == "transportador":
        raise HTTPException(403, "Transportadores não podem aceitar ofertas de mercadoria.")
    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        raise HTTPException(404, "Oferta não encontrada.")
    if oferta.status != "AGUARDANDO_ACEITE":
        raise HTTPException(400, "Esta oferta já foi aceita ou não está disponível.")
    if oferta.autor_id == usuario.id:
        raise HTTPException(400, "O autor não pode aceitar seu próprio preço publicado. Aguarde outro participante.")

    lance = NegociacaoLance(
        oferta_id=oferta_id,
        proponente_id=usuario.id,
        valor_lance_saca=oferta.contra_valor_saca,
        modalidade_venda=oferta.contra_modalidade_venda,
        status_lance="ACEITO",
    )
    db.add(lance)
    db.flush()  # garante lance.id antes de criar o contrato
    oferta.contra_valor_saca = None
    oferta.contra_modalidade_venda = None
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


# ── SSE ──────────────────────────────────────────────────────────────────────

@router.get("/ofertas/{oferta_id}/eventos")
async def sse_eventos(oferta_id: int, request: Request, since_id: int = 0):
    async def generate():
        ultimo_id = since_id
        ultimo_check = datetime.utcnow()
        start = time.time()
        contrato_emitido = False
        ultimo_status_oferta = None

        while time.time() - start < 300:
            if await request.is_disconnected():
                break

            agora = datetime.utcnow()
            db = SessionLocal()
            try:
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

                oferta_obj = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
                if oferta_obj:
                    status_atual = oferta_obj.status
                    if ultimo_status_oferta is None:
                        ultimo_status_oferta = status_atual
                    elif status_atual != ultimo_status_oferta:
                        if status_atual == "AGUARDANDO_ACEITE":
                            payload = {
                                "status": status_atual,
                                "contra_valor_saca": oferta_obj.contra_valor_saca,
                                "contra_modalidade_venda": oferta_obj.contra_modalidade_venda,
                            }
                            yield f"event: oferta_atualizada\ndata: {json.dumps(payload)}\n\n"
                        elif status_atual == "FECHADA" and not contrato_emitido:
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
                        ultimo_status_oferta = status_atual
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
        "valor_lance_saca": float(lance.valor_lance_saca),
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


def _responsavel_id(contrato: ContratoTransporte) -> int:
    return contrato.vendedor_id if contrato.responsavel_frete == "VENDEDOR" else contrato.comprador_id


def _rejeitar_pendentes(contrato_id: int, exceto_id: int | None, novo_status: str, db: Session):
    q = db.query(LanceFrete).filter(
        LanceFrete.contrato_id == contrato_id,
        LanceFrete.status == "PENDENTE",
    )
    if exceto_id:
        q = q.filter(LanceFrete.id != exceto_id)
    for l in q.all():
        l.status = novo_status
        l.atualizado_em = datetime.utcnow()


@router.post("/contratos/{contrato_id}/lances-frete", response_model=LanceFreteResposta, status_code=201)
def propor_frete(
    contrato_id: int,
    dados: LanceFreteCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "transportador":
        raise HTTPException(403, "Apenas transportadores podem propor frete.")

    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    if contrato.status_logistica not in ("AGUARDANDO_TRANSPORTADOR", "EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE"):
        raise HTTPException(400, "Este contrato não está aceitando propostas de frete.")

    ja_tem = db.query(LanceFrete).filter(
        LanceFrete.contrato_id == contrato_id,
        LanceFrete.proponente_id == usuario.id,
        LanceFrete.status == "PENDENTE",
    ).first()
    if ja_tem:
        raise HTTPException(400, "Você já tem uma proposta pendente. Aguarde a resposta.")

    if dados.valor_frete_saca <= 0:
        raise HTTPException(400, "O valor do frete deve ser maior que zero.")

    lance = LanceFrete(
        contrato_id=contrato_id,
        proponente_id=usuario.id,
        valor_frete_saca=dados.valor_frete_saca,
        status="PENDENTE",
    )
    db.add(lance)
    if contrato.status_logistica == "AGUARDANDO_TRANSPORTADOR":
        contrato.status_logistica = "EM_NEGOCIACAO_FRETE"
    db.commit()
    db.refresh(lance)
    return lance


@router.post("/contratos/{contrato_id}/lances-frete/{lance_id}/responder")
def responder_lance_frete(
    contrato_id: int,
    lance_id: int,
    dados: LanceFreteResponder,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    if usuario.id != _responsavel_id(contrato):
        raise HTTPException(403, "Apenas o responsável pelo frete pode aceitar ou recusar propostas.")

    lance = db.query(LanceFrete).filter(
        LanceFrete.id == lance_id, LanceFrete.contrato_id == contrato_id,
    ).first()
    if not lance:
        raise HTTPException(404, "Lance não encontrado.")
    if lance.status != "PENDENTE":
        raise HTTPException(400, "Esta proposta não está mais pendente.")

    acao = dados.acao.upper()
    if acao == "ACEITAR":
        lance.status = "ACEITO"
        lance.atualizado_em = datetime.utcnow()
        _rejeitar_pendentes(contrato_id, exceto_id=lance_id, novo_status="RECUSADO_AUTO", db=db)
        contrato.transportador_id = lance.proponente_id
        contrato.valor_frete_saca_final = lance.valor_frete_saca
        contrato.status_logistica = "A_ENVIAR"
        db.commit()
        return {"resultado": "ACEITO", "valor_frete_saca_final": contrato.valor_frete_saca_final}

    elif acao == "RECUSAR":
        lance.status = "RECUSADO"
        lance.atualizado_em = datetime.utcnow()
        restantes = db.query(LanceFrete).filter(
            LanceFrete.contrato_id == contrato_id, LanceFrete.status == "PENDENTE",
        ).count()
        if restantes == 0:
            contrato.status_logistica = "AGUARDANDO_TRANSPORTADOR"
        db.commit()
        return {"resultado": "RECUSADO"}

    raise HTTPException(400, "Ação deve ser ACEITAR ou RECUSAR.")


@router.post("/contratos/{contrato_id}/contra-proposta-frete")
def contra_proposta_frete(
    contrato_id: int,
    dados: LanceFreteCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    if usuario.id != _responsavel_id(contrato):
        raise HTTPException(403, "Apenas o responsável pelo frete pode fazer contra-proposta.")
    if contrato.status_logistica not in ("EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE"):
        raise HTTPException(400, "Contra-proposta só é possível durante negociação de frete.")
    if dados.valor_frete_saca <= 0:
        raise HTTPException(400, "O valor deve ser maior que zero.")

    _rejeitar_pendentes(contrato_id, exceto_id=None, novo_status="RECUSADO_AUTO", db=db)
    contrato.contra_valor_frete = dados.valor_frete_saca
    contrato.status_logistica = "AGUARDANDO_ACEITE_FRETE"
    db.commit()
    return {"resultado": "CONTRA_PROPOSTA_ENVIADA", "contra_valor_frete": contrato.contra_valor_frete}


@router.post("/contratos/{contrato_id}/aceitar-contra-oferta")
def aceitar_contra_oferta(
    contrato_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    if usuario.perfil != "transportador":
        raise HTTPException(403, "Apenas transportadores podem aceitar fretes.")
    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado.")
    if contrato.status_logistica != "AGUARDANDO_ACEITE_FRETE":
        raise HTTPException(400, "Este frete já foi aceito por outro transportador.")

    lance = LanceFrete(
        contrato_id=contrato_id,
        proponente_id=usuario.id,
        valor_frete_saca=contrato.contra_valor_frete,
        status="ACEITO",
    )
    db.add(lance)
    contrato.transportador_id = usuario.id
    contrato.valor_frete_saca_final = contrato.contra_valor_frete
    contrato.status_logistica = "A_ENVIAR"
    db.commit()
    return {"resultado": "ACEITO", "valor_frete_saca_final": contrato.valor_frete_saca_final}


@router.get("/contratos/{contrato_id}/eventos")
async def sse_contrato_eventos(contrato_id: int, request: Request, since_id_frete: int = 0):
    async def generate():
        ultimo_id_frete = since_id_frete
        ultimo_check = datetime.utcnow()
        start = time.time()
        ultimo_status_logistica = None

        while time.time() - start < 300:
            if await request.is_disconnected():
                break

            agora = datetime.utcnow()
            db = SessionLocal()
            try:
                novos = (
                    db.query(LanceFrete)
                    .filter(LanceFrete.contrato_id == contrato_id, LanceFrete.id > ultimo_id_frete)
                    .order_by(LanceFrete.id)
                    .all()
                )
                for lance in novos:
                    yield f"event: novo_lance_frete\ndata: {json.dumps(_lance_frete_payload(lance))}\n\n"
                    ultimo_id_frete = lance.id

                atualizados = (
                    db.query(LanceFrete)
                    .filter(
                        LanceFrete.contrato_id == contrato_id,
                        LanceFrete.id <= ultimo_id_frete,
                        LanceFrete.atualizado_em > ultimo_check,
                    )
                    .all()
                )
                for lance in atualizados:
                    yield f"event: lance_frete_atualizado\ndata: {json.dumps(_lance_frete_payload(lance))}\n\n"

                contrato_obj = (
                    db.query(ContratoTransporte)
                    .filter(ContratoTransporte.id == contrato_id)
                    .first()
                )
                if contrato_obj:
                    status_atual = contrato_obj.status_logistica
                    if ultimo_status_logistica is not None and status_atual != ultimo_status_logistica:
                        payload = {
                            "status_logistica": status_atual,
                            "valor_frete_saca_final": contrato_obj.valor_frete_saca_final,
                        }
                        yield f"event: contrato_atualizado\ndata: {json.dumps(payload)}\n\n"
                        if status_atual == "A_ENVIAR":
                            return
                    ultimo_status_logistica = status_atual
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


def _lance_frete_payload(lance: LanceFrete) -> dict:
    return {
        "id": lance.id,
        "proponente_id": lance.proponente_id,
        "valor_frete_saca": lance.valor_frete_saca,
        "status": lance.status,
        "criado_em": lance.criado_em.isoformat(),
    }


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
    transicoes = {"A_ENVIAR": "EM_TRANSITO", "EM_TRANSITO": "ENTREGUE"}
    proximo = transicoes.get(contrato.status_logistica)
    if dados.status not in transicoes.values() or dados.status != proximo:
        raise HTTPException(400, f"Transição inválida: {contrato.status_logistica} → {dados.status}.")
    contrato.status_logistica = dados.status
    db.commit()
    return {"resultado": "Status atualizado.", "status_logistica": contrato.status_logistica}
