from datetime import date, datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, Numeric, Text, Enum as SQLEnum
from app.database import Base
from app.enums.produtos import *


class OfertaMercado(Base):
    __tablename__ = "ofertas_mercado"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo_demanda: Mapped[str] = mapped_column(String(20))
    
    produto: Mapped[ProdutoEnum] = mapped_column(SQLEnum(ProdutoEnum), index=True)
    
    # NOVOS CAMPOS DE QUANTIDADE E UNIDADE
    quantidade_total: Mapped[float] = mapped_column(Float) 
    unidade_medida: Mapped[UnidadeMedidaEnum] = mapped_column(SQLEnum(UnidadeMedidaEnum), default=UnidadeMedidaEnum.SACAS)
    
    # Peso total em KG (cálculo que você fará no backend ao receber a requisição)
    peso_total_kg: Mapped[float | None] = mapped_column(Float, nullable=True) 
    
    preco_unidade_inicial: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    
    # NOVO CAMPO DE FRETE SUGERIDO
    tipo_frete_sugerido: Mapped[str | None] = mapped_column(String(30), nullable=True) 
    
    data_limite_envio: Mapped[date] = mapped_column(Date)
    
    # LOCALIZAÇÃO DE ORIGEM 
    cidade_origem: Mapped[str] = mapped_column(String(100), nullable=True)
    estado_origem: Mapped[str] = mapped_column(String(2), nullable=True) 
    
    # LOCALIZAÇÃO DE DESTINO (Opcionais - Usado no QUERO_COMPRAR)
    cidade_destino: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado_destino: Mapped[str | None] = mapped_column(String(2), nullable=True)
    
    # Frete sugerido padronizado com as modalidades do negócio (Pode virar um Enum no futuro também)
    tipo_frete_sugerido: Mapped[str | None] = mapped_column(String(30), nullable=True) 
    # FOB_FAZENDA | CIF | A_COMBINAR
    
    # Detalhes cruciais do Agro (Umidade, Tipo do Grão, Tipo de descarga)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Guardrails de preço por unidade calculados automaticamente pela IA
    ia_preco_minimo: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    ia_preco_maximo: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    
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