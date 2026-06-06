from pydantic import BaseModel, Field


class ItemCriar(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100, examples=["Notebook"])
    descricao: str | None = Field(None, examples=["Notebook gamer 16GB RAM"])
    preco: float = Field(..., ge=0, examples=[2999.90])
    usuario_id: int = Field(..., examples=[1])


class ItemAtualizar(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=100)
    descricao: str | None = None
    preco: float | None = Field(None, ge=0)


class ItemResposta(BaseModel):
    id: int
    nome: str
    descricao: str | None
    preco: float
    usuario_id: int

    model_config = {"from_attributes": True}
