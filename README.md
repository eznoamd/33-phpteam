# 🏁 CodeRace AMF — Template Base Python

## 📁 Estrutura do projeto

```
coderace/
│
├── main.py                  # Ponto de entrada da aplicação
├── .env.exemplo             # Modelo de arquivo de configuração
│
├── app/
│   ├── config.py            # Configurações globais (variáveis de ambiente)
│   ├── database.py          # Configuração do banco de dados
│   ├── seguranca.py         # Funções de segurança (hash, JWT)
│   ├── ia.py                # Cliente da API do Gemini
│   │
│   ├── models/              # Modelos (tabelas do banco de dados)
│   │   ├── usuario.py
│   │   └── item.py
│   │
│   ├── schemas/             # Schemas (validação de dados da API)
│   │   ├── usuario.py
│   │   ├── item.py
│   │   └── auth.py
│   │
│   └── routes/              # Rotas (endpoints da API)
│       ├── auth.py
│       ├── usuarios.py
│       ├── itens.py
│       ├── ia.py
│       └── web.py
│
├── tests/
│   └── test_api.py
│
├── requirements.txt
└── .gitignore
```

## 🧠 Conceitos Principais

### Config (`app/config.py`)
Gerencia configurações através de variáveis de ambiente. Centraliza chaves de API e segredos, permitindo diferentes configurações por ambiente.

### Model (`app/models/`)
Define a estrutura das tabelas do banco de dados usando SQLAlchemy ORM. Cada classe Python representa uma tabela.

### Schema (`app/schemas/`)
Define a estrutura dos dados que entram e saem da API usando Pydantic. Valida automaticamente tipos e formatos.

**Diferença entre Model e Schema:**
- **Model:** Tabela no banco de dados (inclui `senha_hash`, `id`, etc.)
- **Schema:** Contrato da API (o que o cliente envia/recebe, sem dados sensíveis)

### Routes (`app/routes/`)
Contém os endpoints da API. Cada função decorada com `@router` corresponde a uma URL HTTP.

---

## ⚡ Como rodar

### 1. Pré-requisito: Python 3.11+

```bash
python --version
```

### 2. Ambiente virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar .env

```bash
cp .env.exemplo .env
```

Edite o `.env`:

```env
SECRET_KEY=cole-aqui-uma-chave-longa-e-aleatoria
GEMINI_API_KEY=sua-chave-do-gemini
```

### 5. Subir o servidor

```bash
uvicorn main:app --reload
```

Acesse: **http://127.0.0.1:8000/docs**

---

## 🤖 IA (Gemini)

Configure a API Key em `.env` e use os endpoints `/ia/perguntar` e `/ia/conversar`.

```python
from app.ia import gemini

resposta = await gemini.perguntar("Qual é a capital do Brasil?")
```

---

## 🧩 Adicionar nova entidade

Exemplo: criar **Tarefas**.

### 1. Model (`app/models/tarefa.py`)

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, ForeignKey
from app.database import Base

class Tarefa(Base):
    __tablename__ = "tarefas"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    concluida: Mapped[bool] = mapped_column(Boolean, default=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
```

### 2. Schema (`app/schemas/tarefa.py`)

```python
from pydantic import BaseModel, Field

class TarefaCriar(BaseModel):
    titulo: str = Field(..., min_length=1)
    usuario_id: int

class TarefaResposta(BaseModel):
    id: int
    titulo: str
    concluida: bool
    usuario_id: int
    model_config = {"from_attributes": True}
```

### 3. Rotas (`app/routes/tarefas.py`)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tarefa import Tarefa
from app.schemas.tarefa import TarefaCriar, TarefaResposta

router = APIRouter(prefix="/tarefas", tags=["Tarefas"])

@router.post("/", response_model=TarefaResposta, status_code=201)
def criar_tarefa(dados: TarefaCriar, db: Session = Depends(get_db)):
    tarefa = Tarefa(**dados.model_dump())
    db.add(tarefa)
    db.commit()
    db.refresh(tarefa)
    return tarefa
```

### 4. Registrar em `main.py`

```python
from app.routes import tarefas
app.include_router(tarefas.router)
```

---


## 📚 Links úteis

- [FastAPI](https://fastapi.tiangolo.com/pt/)
- [Gemini API](https://ai.google.dev/gemini-api/docs/quickstart)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)

