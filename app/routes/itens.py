from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.item import Item
from app.models.usuario import Usuario
from app.schemas.item import ItemCriar, ItemAtualizar, ItemResposta

router = APIRouter(prefix="/itens", tags=["Itens"])


@router.post("/", response_model=ItemResposta, status_code=201, summary="Criar item")
def criar_item(dados: ItemCriar, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    item = Item(**dados.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/", response_model=list[ItemResposta], summary="Listar todos os itens")
def listar_itens(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Item).offset(skip).limit(limit).all()


@router.get("/{item_id}", response_model=ItemResposta, summary="Buscar item por ID")
def buscar_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return item


@router.get(
    "/usuario/{usuario_id}",
    response_model=list[ItemResposta],
    summary="Listar itens de um usuário",
)
def itens_do_usuario(usuario_id: int, db: Session = Depends(get_db)):
    return db.query(Item).filter(Item.usuario_id == usuario_id).all()


@router.patch("/{item_id}", response_model=ItemResposta, summary="Atualizar item")
def atualizar_item(item_id: int, dados: ItemAtualizar, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(item, campo, valor)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204, summary="Deletar item")
def deletar_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    db.delete(item)
    db.commit()
