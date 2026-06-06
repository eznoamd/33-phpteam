from pydantic import BaseModel, EmailStr, Field


class UsuarioCriar(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100, examples=["João Silva"])
    email: EmailStr = Field(..., examples=["joao@email.com"])
    senha: str = Field(..., min_length=6, examples=["minhasenha123"])


class UsuarioAtualizar(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = None


class UsuarioResposta(BaseModel):
    id: int
    nome: str
    email: str
    ativo: bool

    model_config = {"from_attributes": True}
