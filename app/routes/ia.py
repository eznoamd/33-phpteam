import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models.negociacao import ContratoTransporte, LanceFrete, NegociacaoLance, OfertaMercado
from app.models.usuario import Usuario
from app.routes.web import get_session_usuario

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ia", tags=["IA"])


def _oferta_resumo(o: OfertaMercado) -> dict:
    return {
        "id": o.id,
        "tipo": o.tipo_demanda,
        "produto": str(o.produto).split(".")[-1],
        "quantidade": o.quantidade_total,
        "valor": float(o.preco_unidade_inicial) if o.preco_unidade_inicial else None,
        "estado_origem": o.estado_origem,
        "status": o.status,
        "prazo": o.data_limite_envio.isoformat() if o.data_limite_envio else None,
    }


def _contrato_resumo(c: ContratoTransporte) -> dict:
    return {
        "id": c.id,
        "modalidade": c.modalidade_venda,
        "valor_saca": c.valor_saca_final,
        "status_logistica": c.status_logistica,
        "responsavel_frete": c.responsavel_frete,
    }


def _lance_resumo(l: NegociacaoLance, oferta: OfertaMercado | None) -> dict:
    return {
        "oferta_id": l.oferta_id,
        "produto": str(oferta.produto).split(".")[-1] if oferta else "?",
        "meu_lance": l.valor_lance_saca,
        "status": l.status_lance,
    }


@router.post("/recomendacao")
def recomendar(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        raise HTTPException(401, "Não autenticado.")

    dados: dict = {}

    if usuario.perfil in ("produtor", "comprador"):
        tipo_alvo = "QUERO_COMPRAR" if usuario.perfil == "produtor" else "QUERO_VENDER"
        todos_meus_lances = db.query(NegociacaoLance).filter(
            NegociacaoLance.proponente_id == usuario.id
        ).all()
        excluir_oferta_ids = {l.oferta_id for l in todos_meus_lances}

        oportunidades = (
            db.query(OfertaMercado)
            .filter(
                OfertaMercado.autor_id != usuario.id,
                OfertaMercado.tipo_demanda == tipo_alvo,
                OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO", "AGUARDANDO_ACEITE"]),
                ~OfertaMercado.id.in_(excluir_oferta_ids),
            )
            .order_by(OfertaMercado.id.desc())
            .limit(20)
            .all()
        )

        lances_ativos = [l for l in todos_meus_lances if l.status_lance in ("PENDENTE", "CONTRAPROPOSTA")]
        oferta_map = {
            o.id: o for o in db.query(OfertaMercado)
            .filter(OfertaMercado.id.in_({l.oferta_id for l in lances_ativos})).all()
        } if lances_ativos else {}

        dados["oportunidades"] = [_oferta_resumo(o) for o in oportunidades]
        dados["lances_ativos"] = [_lance_resumo(l, oferta_map.get(l.oferta_id)) for l in lances_ativos]

    else:  # transportador
        todos_meus_lances_frete = db.query(LanceFrete).filter(
            LanceFrete.proponente_id == usuario.id
        ).all()
        excluir_contrato_ids = {l.contrato_id for l in todos_meus_lances_frete}

        fretes = (
            db.query(ContratoTransporte)
            .filter(
                ContratoTransporte.status_logistica.in_([
                    "AGUARDANDO_TRANSPORTADOR", "EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE"
                ]),
                ~ContratoTransporte.id.in_(excluir_contrato_ids),
            )
            .order_by(ContratoTransporte.id.desc())
            .limit(20)
            .all()
        )
        dados["fretes_disponiveis"] = [_contrato_resumo(c) for c in fretes]

    contratos = (
        db.query(ContratoTransporte)
        .filter(
            or_(
                ContratoTransporte.vendedor_id == usuario.id,
                ContratoTransporte.comprador_id == usuario.id,
                ContratoTransporte.transportador_id == usuario.id,
            )
        )
        .order_by(ContratoTransporte.id.desc())
        .limit(10)
        .all()
    )
    dados["contratos_ativos"] = [_contrato_resumo(c) for c in contratos]

    total = sum(len(v) for v in dados.values())
    if total == 0:
        return {
            "tipo": None, "id": None, "link": "/dashboard",
            "justificativa": "Sem dados suficientes para recomendação. Explore as oportunidades disponíveis!",
        }

    rec = _chamar_gemini(usuario, dados)
    if rec.get("tipo") == "oferta":
        rec["link"] = f"/negociacao/{rec['id']}"
    elif rec.get("tipo") == "contrato":
        rec["link"] = f"/contratos/{rec['id']}"
    else:
        rec["link"] = "/dashboard"
    return rec


def _chamar_gemini(usuario: Usuario, dados: dict) -> dict:
    if not config.GEMINI_API_KEY:
        return _fallback(dados)
    try:
        prompt = (
            f"Você é assistente de um marketplace agrícola brasileiro.\n"
            f"Perfil: {usuario.perfil} | Nome: {usuario.nome}\n"
            f"Dados de sessão:\n{json.dumps(dados, ensure_ascii=False, indent=2)}\n\n"
            f"Responda APENAS com JSON válido:\n"
            f'{{\"tipo\": \"oferta\", \"id\": <int>, \"justificativa\": \"<1-2 frases>\"}}\n'
            f"Campo 'tipo': use 'oferta' para oportunidades/lances, 'contrato' para contratos ativos.\n"
            f"Escolha a ação mais lucrativa ou urgente para este usuário agora. "
            f"Não inclua texto fora do JSON."
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"/{config.GEMINI_MODEL}:generateContent"
        )
        resp = httpx.post(
            url,
            params={"key": config.GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15.0,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as exc:
        log.warning("Gemini recomendação falhou: %s", exc)
        return _fallback(dados)


def _fallback(dados: dict) -> dict:
    if dados.get("oportunidades"):
        o = dados["oportunidades"][0]
        return {"tipo": "oferta", "id": o["id"],
                "justificativa": f"Oportunidade recente de {o['produto']} disponível — seja o primeiro a negociar."}
    if dados.get("fretes_disponiveis"):
        c = dados["fretes_disponiveis"][0]
        return {"tipo": "contrato", "id": c["id"],
                "justificativa": "Frete disponível aguardando transportador — proponha um valor agora."}
    if dados.get("lances_ativos"):
        l = dados["lances_ativos"][0]
        return {"tipo": "oferta", "id": l["oferta_id"],
                "justificativa": f"Seu lance em {l['produto']} ainda está pendente — acompanhe a resposta."}
    if dados.get("contratos_ativos"):
        c = dados["contratos_ativos"][0]
        return {"tipo": "contrato", "id": c["id"],
                "justificativa": "Contrato ativo requer acompanhamento logístico."}
    return {"tipo": None, "id": None, "justificativa": "Sem dados suficientes."}
