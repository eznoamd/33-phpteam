from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCriar, UsuarioAtualizar, UsuarioResposta
from app.seguranca import hash_senha, obter_usuario_atual

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.post("/", response_model=UsuarioResposta, status_code=201)
def criar_usuario(dados: UsuarioCriar, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    perfis_validos = {"produtor", "transportador", "comprador"}
    if dados.perfil not in perfis_validos:
        raise HTTPException(status_code=400, detail=f"Perfil inválido. Use: {perfis_validos}")

    novo = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        perfil=dados.perfil,
        cpf=dados.cpf,
        cidade=dados.cidade,
        estado=dados.estado,
        telefone=dados.telefone,
        bio=dados.bio,
        tipo_instituicao=dados.tipo_instituicao,
        cnpj=dados.cnpj,
        endereco_recebimento=dados.endereco_recebimento,
        capacidade_armazenagem=dados.capacidade_armazenagem,
        tipo_veiculo=dados.tipo_veiculo,
        capacidade_carga=dados.capacidade_carga,
        cidade_atual=dados.cidade_atual,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/me", response_model=UsuarioResposta)
def meu_perfil(usuario: Usuario = Depends(obter_usuario_atual)):
    return usuario


@router.patch("/me", response_model=UsuarioResposta)
def atualizar_perfil(
    dados: UsuarioAtualizar,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/{usuario_id}", response_model=UsuarioResposta)
def ver_usuario(usuario_id: int, db: Session = Depends(get_db)):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return u
