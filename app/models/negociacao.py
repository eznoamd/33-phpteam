from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, Integer
from app.database import Base


class OfertaMercado(Base):
    __tablename__ = "ofertas_mercado"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo_demanda: Mapped[str] = mapped_column(String(20))  # QUERO_VENDER | QUERO_COMPRAR
    produto: Mapped[str] = mapped_column(String(100))
    quantidade_total: Mapped[float] = mapped_column(Float)  # sacas
    preco_saca_inicial: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_limite_envio: Mapped[datetime] = mapped_column(Date)
    cidade_origem: Mapped[str] = mapped_column(String(100))
    estado_origem: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ia_preco_minimo: Mapped[float | None] = mapped_column(Float, nullable=True)
    ia_preco_maximo: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ABERTA")  # ABERTA | EM_NEGOCIACAO | FECHADA
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NegociacaoLance(Base):
    __tablename__ = "negociacoes_lances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    oferta_id: Mapped[int] = mapped_column(ForeignKey("ofertas_mercado.id"))
    proponente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    valor_lance_saca: Mapped[float] = mapped_column(Float)
    modalidade_venda: Mapped[str] = mapped_column(String(30))
    # FOB_FAZENDA | FOB_ARMAZEM | CIF | POSTO_INDUSTRIA |
    # POSTO_COOPERATIVA | POSTO_PORTO | VENDA_A_RETIRAR | BARTER
    status_lance: Mapped[str] = mapped_column(String(20), default="PENDENTE")
    # PENDENTE | CONTRAPROPOSTA | ACEITO | RECUSADO
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ContratoTransporte(Base):
    __tablename__ = "contratos_transporte"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    negociacao_id: Mapped[int] = mapped_column(ForeignKey("negociacoes_lances.id"))
    oferta_id: Mapped[int] = mapped_column(ForeignKey("ofertas_mercado.id"))
    vendedor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    comprador_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    transportador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    responsavel_frete: Mapped[str] = mapped_column(String(10))  # COMPRADOR | VENDEDOR
    modalidade_venda: Mapped[str] = mapped_column(String(30))
    valor_saca_final: Mapped[float] = mapped_column(Float)
    status_logistica: Mapped[str] = mapped_column(String(30), default="AGUARDANDO_TRANSPORTADOR")
    # AGUARDANDO_TRANSPORTADOR | EM_TRANSITO | ENTREGUE
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
