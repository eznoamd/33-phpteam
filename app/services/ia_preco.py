import json
import logging
from datetime import date

import httpx

from app.config import config

log = logging.getLogger(__name__)

FALLBACK_PRECOS: dict[str, tuple[float, float]] = {
    "soja": (120.0, 165.0),
    "milho": (55.0, 78.0),
    "trigo": (85.0, 115.0),
    "feijao": (200.0, 280.0),
    "arroz": (80.0, 110.0),
    "cafe": (500.0, 700.0),
    "algodao": (150.0, 220.0),
    "cana": (25.0, 45.0),
    "sorgo": (45.0, 65.0),
    "girassol": (90.0, 130.0),
}


def calcular_guardrails(
    produto: str,
    quantidade_sacas: float,
    estado_origem: str = "SP",
) -> tuple[float, float]:
    if not config.GEMINI_API_KEY:
        return _fallback(produto)
    try:
        return _chamar_gemini(produto, quantidade_sacas, estado_origem)
    except Exception as exc:
        log.warning("Gemini falhou (%s); usando fallback para '%s'", exc, produto)
        return _fallback(produto)


def _chamar_gemini(produto: str, quantidade_sacas: float, estado_origem: str) -> tuple[float, float]:
    prompt = (
        f"Você é especialista em precificação de commodities agrícolas no Brasil.\n"
        f"Produto: {produto} | Quantidade: {quantidade_sacas:.0f} sacas de 60 kg | "
        f"Estado de origem: {estado_origem} | Data: {date.today().isoformat()}\n"
        f"Responda APENAS com JSON: {{\"preco_minimo\": <numero>, \"preco_maximo\": <numero>}}\n"
        f"Considere cotações CBOT/B3 recentes, base regional e margem ±15%. Valores em R$/saca de 60 kg.\n"
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
        timeout=10.0,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text.strip())
    preco_min = float(data["preco_minimo"])
    preco_max = float(data["preco_maximo"])
    log.info("Gemini guardrails '%s': R$ %.2f–%.2f", produto, preco_min, preco_max)
    return preco_min, preco_max


def _fallback(produto: str) -> tuple[float, float]:
    chave = produto.lower().strip()
    result = FALLBACK_PRECOS.get(chave, (80.0, 200.0))
    log.info("Fallback guardrails '%s': R$ %.2f–%.2f", produto, result[0], result[1])
    return result
