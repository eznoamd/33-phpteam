import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey, Boolean
from app.database import Base


class Mensagem(Base):
    """
    Chat direto entre usuários.
    Regras de negócio (aplicadas na rota, não no banco):
    - Comprador <-> Produtor: OK
    - Produtor <-> Transportador: OK
    - Comprador <-> Transportador: NÃO PERMITIDO
    """
    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    remetente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    viagem_id: Mapped[int | None] = mapped_column(ForeignKey("viagens.id"), nullable=True)
    texto: Mapped[str] = mapped_column(Text)
    lida: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
