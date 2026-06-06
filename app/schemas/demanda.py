from pydantic import BaseModel, Field
from typing import Optional
import datetime


class DemandaCriar(BaseModel):
    tipo_produto: str = Field(..., min_length=2)
    quantidade_kg: float = Field(..., gt=0)
    preco_max_por_kg: float = Field(..., gt=0)
    data_limite_entrega: datetime.date
    local_entrega: str = Field(..., min_length=5)
    descricao: Optional[str] = None


class DemandaResposta(BaseModel):
    id: int
    tipo_produto: str
    quantidade_kg: float
    preco_max_por_kg: float
    data_limite_entrega: datetime.date
    local_entrega: str
    descricao: Optional[str]
    status: str
    comprador_id: int
    produtor_id: Optional[int]
    criado_em: datetime.datetime

    model_config = {"from_attributes": True}
