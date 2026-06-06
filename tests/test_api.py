"""
Testes básicos da API.

Para rodar: pytest tests/

Instale o pytest se ainda não tiver:
  pip install pytest httpx
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database import Base, get_db

# Banco de dados em memória exclusivo para testes (não polui o banco.db real)
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
engine_test = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Substitui o banco real pelo banco de testes
app.dependency_overrides[get_db] = override_get_db

# Cria as tabelas no banco de testes
Base.metadata.create_all(bind=engine_test)

client = TestClient(app)


# ── Testes ─────────────────────────────────────────────────────────────────────

def test_raiz():
    """Testa se a API está de pé."""
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_criar_usuario():
    """Testa a criação de um usuário."""
    resposta = client.post("/usuarios/", json={
        "nome": "Maria Teste",
        "email": "maria@teste.com",
        "senha": "senha123"
    })
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["email"] == "maria@teste.com"
    assert "senha" not in dados  # senha nunca deve aparecer na resposta!


def test_email_duplicado():
    """Testa que e-mails duplicados são rejeitados."""
    payload = {"nome": "João", "email": "joao@teste.com", "senha": "senha123"}
    client.post("/usuarios/", json=payload)
    resposta = client.post("/usuarios/", json=payload)
    assert resposta.status_code == 400


def test_usuario_nao_encontrado():
    """Testa a resposta quando um usuário não existe."""
    resposta = client.get("/usuarios/99999")
    assert resposta.status_code == 404
