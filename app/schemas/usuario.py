from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UsuarioCriar(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    senha: str = Field(..., min_length=6)
    perfil: str = Field(..., examples=["produtor", "transportador", "comprador"])

    # Produtor
    cpf: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = Field(None, max_length=2)
    telefone: Optional[str] = None
    bio: Optional[str] = None

    # Comprador
    tipo_instituicao: Optional[str] = None
    cnpj: Optional[str] = None
    endereco_recebimento: Optional[str] = None
    capacidade_armazenagem: Optional[float] = None

    # Transportador
    tipo_veiculo: Optional[str] = None
    capacidade_carga: Optional[float] = None
    cidade_atual: Optional[str] = None


class UsuarioAtualizar(BaseModel):
    nome: Optional[str] = None
    foto_url: Optional[str] = None
    bio: Optional[str] = None
    telefone: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    tipo_veiculo: Optional[str] = None
    capacidade_carga: Optional[float] = None
    cidade_atual: Optional[str] = None
    tipo_instituicao: Optional[str] = None
    endereco_recebimento: Optional[str] = None
    capacidade_armazenagem: Optional[float] = None


class UsuarioResposta(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    ativo: bool
    foto_url: Optional[str]
    avaliacao_media: float
    total_avaliacoes: int
    cidade: Optional[str]
    estado: Optional[str]
    tipo_veiculo: Optional[str]
    capacidade_carga: Optional[float]
    cidade_atual: Optional[str]
    tipo_instituicao: Optional[str]
    endereco_recebimento: Optional[str]
    capacidade_armazenagem: Optional[float]

    model_config = {"from_attributes": True}


class UsuarioPublico(BaseModel):
    """Dados públicos visíveis no catálogo e perfis"""
    id: int
    nome: str
    perfil: str
    avaliacao_media: float
    total_avaliacoes: int
    foto_url: Optional[str]
    cidade: Optional[str]
    estado: Optional[str]
    bio: Optional[str]
    tipo_produto: Optional[str] = None  # para produtor no catálogo

    model_config = {"from_attributes": True}
