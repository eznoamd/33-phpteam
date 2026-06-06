from pydantic import BaseModel
from typing import Optional
import datetime


class MensagemEnviar(BaseModel):
    destinatario_id: int
    texto: str
    viagem_id: Optional[int] = None


class MensagemResposta(BaseModel):
    id: int
    remetente_id: int
    destinatario_id: int
    viagem_id: Optional[int]
    texto: str
    lida: bool
    criado_em: datetime.datetime

    model_config = {"from_attributes": True}
