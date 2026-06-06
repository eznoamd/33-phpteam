import enum
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Text, ForeignKey, Date, DateTime
from app.database import Base


class StatusViagem(str, enum.Enum):
    aguardando_transportador = "aguardando_transportador"
    confirmada = "confirmada"
    coleta = "coleta"          # transportador coletou
    em_transito = "em_transito"
    entregue = "entregue"
    cancelada = "cancelada"


class Viagem(Base):
    __tablename__ = "viagens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Referências
    demanda_id: Mapped[int | None] = mapped_column(ForeignKey("demandas.id"), nullable=True)
    produtor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    transportador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    comprador_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    # Preenchido pelo produtor
    origem: Mapped[str] = mapped_column(String(300))
    destino: Mapped[str] = mapped_column(String(300))
    tipo_produto: Mapped[str] = mapped_column(String(100))
    peso_kg: Mapped[float] = mapped_column(Float)
    data_coleta: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="aguardando_transportador")

    # Avaliações do produtor
    avaliacao_transportador: Mapped[float | None] = mapped_column(Float, nullable=True)
    avaliacao_comprador: Mapped[float | None] = mapped_column(Float, nullable=True)
    comentario_transportador: Mapped[str | None] = mapped_column(Text, nullable=True)
    comentario_comprador: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Preenchido pelo transportador
    tipo_veiculo_viagem: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacidade_veiculo: Mapped[float | None] = mapped_column(Float, nullable=True)
    avaliacao_produtor_pelo_transp: Mapped[float | None] = mapped_column(Float, nullable=True)
    avaliacao_comprador_pelo_transp: Mapped[float | None] = mapped_column(Float, nullable=True)
    comentario_produtor_pelo_transp: Mapped[str | None] = mapped_column(Text, nullable=True)
    comentario_comprador_pelo_transp: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Preenchido pelo comprador
    avaliacao_produtor_pelo_comp: Mapped[float | None] = mapped_column(Float, nullable=True)
    avaliacao_transportador_pelo_comp: Mapped[float | None] = mapped_column(Float, nullable=True)
    comentario_produtor_pelo_comp: Mapped[str | None] = mapped_column(Text, nullable=True)
    comentario_transportador_pelo_comp: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Preenchido pelo sistema
    rota_descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    preco_final: Mapped[float | None] = mapped_column(Float, nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )
