import enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Text, ForeignKey, Date
from app.database import Base
import datetime


class StatusDemanda(str, enum.Enum):
    aberta = "aberta"
    aceita = "aceita"
    em_andamento = "em_andamento"
    concluida = "concluida"
    cancelada = "cancelada"


class Demanda(Base):
    __tablename__ = "demandas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tipo_produto: Mapped[str] = mapped_column(String(100))
    quantidade_kg: Mapped[float] = mapped_column(Float)
    preco_max_por_kg: Mapped[float] = mapped_column(Float)
    data_limite_entrega: Mapped[datetime.date] = mapped_column(Date)
    local_entrega: Mapped[str] = mapped_column(String(300))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="aberta")

    comprador_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    produtor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
