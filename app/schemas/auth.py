from pydantic import BaseModel


class TokenResposta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario_id: int
    nome: str
    email: str
