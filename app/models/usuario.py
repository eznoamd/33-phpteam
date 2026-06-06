import enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Float, Text, Enum as SAEnum
from app.database import Base


class TipoPerfil(str, enum.Enum):
    produtor = "produtor"
    transportador = "transportador"
    comprador = "comprador"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[str] = mapped_column(String(30))  # produtor | transportador | comprador
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    foto_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avaliacao_media: Mapped[float] = mapped_column(Float, default=0.0)
    total_avaliacoes: Mapped[int] = mapped_column(default=0)

    # Campos do Produtor
    cpf: Mapped[str | None] = mapped_column(String(14), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos do Comprador
    tipo_instituicao: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endereco_recebimento: Mapped[str | None] = mapped_column(String(300), nullable=True)
    capacidade_armazenagem: Mapped[float | None] = mapped_column(Float, nullable=True)  # toneladas

    # Campos do Transportador
    tipo_veiculo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacidade_carga: Mapped[float | None] = mapped_column(Float, nullable=True)  # toneladas
    cidade_atual: Mapped[str | None] = mapped_column(String(100), nullable=True)
