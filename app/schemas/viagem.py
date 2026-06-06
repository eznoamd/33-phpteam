from pydantic import BaseModel, Field
from typing import Optional
import datetime


class ViagemCriar(BaseModel):
    demanda_id: Optional[int] = None
    comprador_id: int
    origem: str = Field(..., min_length=3)
    destino: str = Field(..., min_length=3)
    tipo_produto: str
    peso_kg: float = Field(..., gt=0)
    data_coleta: datetime.date


class ViagemAceitarTransportador(BaseModel):
    tipo_veiculo_viagem: str
    capacidade_veiculo: float


class AvaliacaoProdutor(BaseModel):
    """Produtor avalia transportador e comprador"""
    avaliacao_transportador: Optional[float] = Field(None, ge=1, le=5)
    comentario_transportador: Optional[str] = None
    avaliacao_comprador: Optional[float] = Field(None, ge=1, le=5)
    comentario_comprador: Optional[str] = None


class AvaliacaoTransportador(BaseModel):
    """Transportador avalia produtor e comprador"""
    avaliacao_produtor_pelo_transp: Optional[float] = Field(None, ge=1, le=5)
    comentario_produtor_pelo_transp: Optional[str] = None
    avaliacao_comprador_pelo_transp: Optional[float] = Field(None, ge=1, le=5)
    comentario_comprador_pelo_transp: Optional[str] = None


class AvaliacaoComprador(BaseModel):
    """Comprador avalia produtor e transportador"""
    avaliacao_produtor_pelo_comp: Optional[float] = Field(None, ge=1, le=5)
    comentario_produtor_pelo_comp: Optional[str] = None
    avaliacao_transportador_pelo_comp: Optional[float] = Field(None, ge=1, le=5)
    comentario_transportador_pelo_comp: Optional[str] = None


class ViagemResposta(BaseModel):
    id: int
    demanda_id: Optional[int]
    produtor_id: int
    transportador_id: Optional[int]
    comprador_id: int
    origem: str
    destino: str
    tipo_produto: str
    peso_kg: float
    data_coleta: datetime.date
    status: str
    tipo_veiculo_viagem: Optional[str]
    capacidade_veiculo: Optional[float]
    preco_final: Optional[float]
    rota_descricao: Optional[str]
    criado_em: datetime.datetime

    model_config = {"from_attributes": True}
