from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class OfertaCriar(BaseModel):
    tipo_demanda: str  # QUERO_VENDER | QUERO_COMPRAR
    produto: str
    quantidade_total: float
    preco_saca_inicial: Optional[float] = None
    data_limite_envio: date
    cidade_origem: str
    estado_origem: Optional[str] = None  # fallback: usuario.estado


class OfertaResposta(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    autor_id: int
    tipo_demanda: str
    produto: str
    quantidade_total: float
    preco_saca_inicial: Optional[float]
    data_limite_envio: date
    cidade_origem: str
    estado_origem: Optional[str]
    ia_preco_minimo: Optional[float]
    ia_preco_maximo: Optional[float]
    status: str
    criado_em: datetime


class LanceCriar(BaseModel):
    valor_lance_saca: float
    modalidade_venda: str  # FOB_FAZENDA | FOB_ARMAZEM | CIF | etc.


class LanceResposta(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    oferta_id: int
    proponente_id: int
    valor_lance_saca: float
    modalidade_venda: str
    status_lance: str
    criado_em: datetime
    atualizado_em: datetime


class LanceResponder(BaseModel):
    acao: str  # ACEITAR | RECUSAR


class ContratoResposta(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    negociacao_id: int
    oferta_id: int
    vendedor_id: int
    comprador_id: int
    transportador_id: Optional[int]
    responsavel_frete: str
    modalidade_venda: str
    valor_saca_final: float
    status_logistica: str
    criado_em: datetime


class ContratoStatusUpdate(BaseModel):
    status: str  # EM_TRANSITO | ENTREGUE
