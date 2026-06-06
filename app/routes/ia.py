from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ia import gemini
from app.models.usuario import Usuario
from app.seguranca import obter_usuario_atual

router = APIRouter(prefix="/ia", tags=["🤖 IA (Gemini)"])


class PerguntaSimples(BaseModel):
    pergunta: str = Field(..., min_length=1, examples=["Qual é a capital da França?"])
    sistema: str | None = Field(
        None,
        examples=["Você é um assistente especialista em geografia. Responda de forma concisa."],
        description="Instrução de sistema: define a personalidade ou contexto do modelo.",
    )


class MensagemChat(BaseModel):
    role: str = Field(..., examples=["user"], description="'user' ou 'model'")
    texto: str = Field(..., examples=["Olá, tudo bem?"])


class PedidoConversa(BaseModel):
    historico: list[MensagemChat] = Field(
        default=[],
        description="Mensagens anteriores da conversa.",
    )
    nova_mensagem: str = Field(..., min_length=1, examples=["Me fale mais sobre isso."])
    sistema: str | None = Field(None, description="Instrução de sistema opcional.")


class RespostaIA(BaseModel):
    resposta: str
    modelo: str

@router.post(
    "/perguntar",
    response_model=RespostaIA,
    summary="Fazer uma pergunta direta ao Gemini",
    description="""
Envia uma **pergunta simples** para o Gemini e recebe uma resposta.

Opcionalmente, você pode definir um `sistema` para dar contexto ao modelo:
- `"Você é um assistente de culinária. Responda em português."`
- `"Responda sempre de forma curta, em no máximo 2 frases."`

**Requer login.**
""",
)
async def perguntar(
    dados: PerguntaSimples,
    usuario: Usuario = Depends(obter_usuario_atual),  # 🔒 Exige login
):
    from app.config import config
    resposta = await gemini.perguntar(dados.pergunta, sistema=dados.sistema)
    return RespostaIA(resposta=resposta, modelo=config.GEMINI_MODEL)


@router.post(
    "/conversar",
    response_model=RespostaIA,
    summary="Conversa com histórico (chat)",
)
async def conversar(
    dados: PedidoConversa,
    usuario: Usuario = Depends(obter_usuario_atual),
):
    from app.config import config

    historico_gemini = [
        {"role": msg.role, "parts": [{"text": msg.texto}]}
        for msg in dados.historico
    ]

    resposta = await gemini.conversar(
        historico=historico_gemini,
        nova_mensagem=dados.nova_mensagem,
        sistema=dados.sistema,
    )
    return RespostaIA(resposta=resposta, modelo=config.GEMINI_MODEL)


@router.get(
    "/status",
    summary="Verifica se a IA está configurada",
)
async def status_ia(usuario: Usuario = Depends(obter_usuario_atual)):
    from app.config import config

    configurada = bool(config.GEMINI_API_KEY and config.GEMINI_API_KEY != "sua-chave-aqui")

    return {
        "configurada": configurada,
        "modelo": config.GEMINI_MODEL,
        "mensagem": (
            "IA pronta para uso! ✅"
            if configurada
            else "Configure GEMINI_API_KEY no arquivo .env ⚠️"
        ),
    }
