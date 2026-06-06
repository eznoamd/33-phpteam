import asyncio
import json
import time
from datetime import date, timedelta, datetime

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

    # --- VALIDAÇÃO DE DATA ---
    hoje = date.today()
    daqui_um_ano = hoje + timedelta(days=365)

    if dados.data_limite_envio < hoje:
        raise HTTPException(400, "A data limite não pode ser no passado.")
    
    if dados.data_limite_envio > daqui_um_ano:
        raise HTTPException(400, "A data limite não pode ultrapassar 1 ano a partir de hoje.")
    # -------------------------

    estado = (dados.estado_origem or dados.estado_destino) or getattr(usuario, "estado", None) or "SP"
    
    preco_min, preco_max = ia_preco.calcular_guardrails(
        dados.produto.value, dados.quantidade_total, estado
    )

    oferta = OfertaMercado(
        autor_id=usuario.id,
        tipo_demanda=dados.tipo_demanda,
        produto=dados.produto.value,
        quantidade_total=dados.quantidade_total,
        unidade_medida=dados.unidade_medida.value,
        tipo_frete_sugerido=dados.tipo_frete_sugerido.value,
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
        OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO"])
    )
    if produto:
        # Ajuste dependendo de como você busca por Enum no DB. 
        # Pode exigir conversão dependendo do driver do banco.
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

@router.post("/ofertas/", response_model=OfertaResposta, status_code=201)
def criar_oferta(
    dados: OfertaCriar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    # 1. Validação de campos obrigatórios (garante que não sejam None ou strings vazias)
    campos_obrigatorios = {
        "produto": dados.produto,
        "quantidade_total": dados.quantidade_total,
        "unidade_medida": dados.unidade_medida,
        "tipo_frete_sugerido": dados.tipo_frete_sugerido,
        "data_limite_envio": dados.data_limite_envio,
        "estado": (dados.estado_origem or dados.estado_destino),
        "cidade": (dados.cidade_origem or dados.cidade_destino)
    }

    for nome, valor in campos_obrigatorios.items():
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            raise HTTPException(400, f"O campo {nome} é obrigatório e não pode estar vazio.")

    # 2. Regras de perfil
    if usuario.perfil == "transportador":
        raise HTTPException(403, "Transportadores não podem criar ofertas.")
    if usuario.perfil == "produtor" and dados.tipo_demanda != "QUERO_VENDER":
        raise HTTPException(400, "Produtores só podem criar ofertas QUERO_VENDER.")
    if usuario.perfil == "comprador" and dados.tipo_demanda != "QUERO_COMPRAR":
        raise HTTPException(400, "Compradores só podem criar ofertas QUERO_COMPRAR.")

    # 3. Validação de Data (Trava de 1 ano)
    hoje = date.today()
    daqui_um_ano = hoje + timedelta(days=365)

    if dados.data_limite_envio < hoje:
        raise HTTPException(400, "A data limite não pode ser no passado.")
    if dados.data_limite_envio > daqui_um_ano:
        raise HTTPException(400, "A data limite não pode ultrapassar 1 ano a partir de hoje.")

    # 4. Cálculo de Preço e Criação da Oferta
    estado = (dados.estado_origem or dados.estado_destino) or getattr(usuario, "estado", None) or "SP"
    
    preco_min, preco_max = ia_preco.calcular_guardrails(
        dados.produto.value, dados.quantidade_total, estado
    )

    oferta = OfertaMercado(
        autor_id=usuario.id,
        tipo_demanda=dados.tipo_demanda,
        produto=dados.produto.value,
        quantidade_total=dados.quantidade_total,
        unidade_medida=dados.unidade_medida.value,
        tipo_frete_sugerido=dados.tipo_frete_sugerido.value,
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
        "valor_unidade_final": contrato.valor_unidade_final, # Atualizado
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
        valor_unidade_final=lance.valor_lance_unidade, # Atualizado
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
                                "valor_unidade_final": contrato.valor_unidade_final, # Atualizado
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
        "valor_lance_unidade": float(lance.valor_lance_unidade), # Atualizado e cast para float seguro no JSON
        "modalidade_venda": lance.modalidade_venda,
        "status_lance": lance.status_lance,
        "criado_em": lance.criado_em.isoformat(),
    }


# ── Contratos ────────────────────────────────────────────────────────────────
# (O restante das rotas de contrato permanecem as mesmas estruturalmente)

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

# ... rotas detalhe_contrato, aceitar_frete e atualizar_status_logistica mantidas
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
