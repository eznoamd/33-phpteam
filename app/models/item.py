from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, ForeignKey
from app.database import Base


class Item(Base):
    __tablename__ = "itens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(100))
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preco: Mapped[float] = mapped_column(Float, default=0.0)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
