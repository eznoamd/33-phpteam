import httpx
from fastapi import HTTPException

from app.config import config

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class ServicoGemini:
    def _url(self) -> str:
        return f"{_BASE_URL}/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"

    def _montar_corpo(
        self,
        mensagens: list[dict],
        sistema: str | None = None,
    ) -> dict:
        corpo: dict = {"contents": mensagens}

        if sistema:
            corpo["systemInstruction"] = {
                "parts": [{"text": sistema}]
            }

        corpo["generationConfig"] = {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }

        return corpo

    async def perguntar(
        self,
        pergunta: str,
        sistema: str | None = None,
    ) -> str:
        if not config.GEMINI_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Chave da API do Gemini não configurada. Adicione GEMINI_API_KEY no arquivo .env",
            )

        mensagens = [
            {"role": "user", "parts": [{"text": pergunta}]}
        ]

        return await self._chamar_api(mensagens, sistema)

    async def conversar(
        self,
        historico: list[dict],
        nova_mensagem: str,
        sistema: str | None = None,
    ) -> str:
        if not config.GEMINI_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Chave da API do Gemini não configurada. Adicione GEMINI_API_KEY no arquivo .env",
            )

        mensagens = historico + [
            {"role": "user", "parts": [{"text": nova_mensagem}]}
        ]

        return await self._chamar_api(mensagens, sistema)

    async def _chamar_api(
        self,
        mensagens: list[dict],
        sistema: str | None = None,
    ) -> str:
        corpo = self._montar_corpo(mensagens, sistema)

        async with httpx.AsyncClient(timeout=30.0) as cliente:
            try:
                resposta = await cliente.post(self._url(), json=corpo)
                resposta.raise_for_status()
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=504,
                    detail="A API do Gemini demorou demais para responder. Tente novamente.",
                )
            except httpx.HTTPStatusError as e:
                detalhe = "Erro na API do Gemini."
                try:
                    erro_json = e.response.json()
                    detalhe = erro_json.get("error", {}).get("message", detalhe)
                except Exception:
                    pass
                raise HTTPException(status_code=502, detail=detalhe)

        dados = resposta.json()

        try:
            return dados["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise HTTPException(
                status_code=502,
                detail="Resposta inesperada da API do Gemini. Verifique os logs.",
            )


gemini = ServicoGemini()
