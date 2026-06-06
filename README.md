# 🌾 AgroHub — Conexão no Campo

Plataforma que conecta **produtores rurais**, **transportadores** e **compradores** em um fluxo simples e transparente.

---

## Fluxo principal

```
Comprador posta demanda → Produtor aceita → Viagem criada → Transportador aceita
→ Coleta → Entrega → Avaliações mútuas
```

**Regras de comunicação:**
- Comprador ↔ Produtor ✅
- Produtor ↔ Transportador ✅  
- Comprador ↔ Transportador ❌ (não permitido)

---

## Perfis

### 🌾 Produtor
- Vê demandas abertas de compradores
- Aceita demandas e cria viagens
- Fala com comprador e transportador
- Avalia transportador e comprador

### 🚛 Transportador
- Vê viagens disponíveis
- Aceita viagens informando veículo
- Atualiza status (coleta / em_trânsito / entregue)
- Fala apenas com produtor
- Avalia produtor e comprador

### 🏢 Comprador
- Publica demandas (produto, qtd, preço máx, prazo)
- Acompanha status das entregas
- Fala apenas com produtor
- Avalia produtor e transportador

---

## Estrutura

```
agrohub/
├── main.py
├── requirements.txt
├── .env.exemplo
├── app/
│   ├── config.py
│   ├── database.py          # SQLite (trocar PostgreSQL em prod)
│   ├── seguranca.py         # JWT + bcrypt
│   ├── models/
│   │   ├── usuario.py       # Produtor / Transportador / Comprador
│   │   ├── demanda.py       # Demanda postada pelo comprador
│   │   ├── viagem.py        # Viagem (transporte de carga)
│   │   └── mensagem.py      # Chat entre usuários
│   ├── schemas/             # Validação Pydantic
│   └── routes/
│       ├── web.py           # Frontend HTML (Jinja2)
│       ├── auth.py          # Login / JWT
│       ├── usuarios.py      # Criação e atualização de perfil
│       ├── demandas.py      # CRUD demandas
│       ├── viagens.py       # CRUD viagens + avaliações
│       ├── mensagens.py     # Chat com regras de acesso
│       └── catalogo.py      # Lista pública de produtores
└── templates/
    ├── base.html
    ├── landing.html         # Landing page pública
    ├── catalogo.html        # Lista de produtores (pública)
    ├── login.html
    ├── cadastro.html
    ├── dashboard.html       # Painel adaptado por perfil
    ├── demandas.html
    ├── viagens.html
    ├── perfil.html
    └── static/css/main.css
```

---

## Como rodar

```bash
# 1. Ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Configurar .env
cp .env.exemplo .env
# Edite e coloque uma SECRET_KEY segura

# 4. Rodar
uvicorn main:app --reload
```

Acesse: **http://127.0.0.1:8000**  
API Docs: **http://127.0.0.1:8000/docs**

---

## Endpoints principais

| Método | Rota | Quem usa |
|--------|------|----------|
| POST | `/usuarios/` | Registro público |
| POST | `/auth/login` | Todos |
| GET | `/catalogo/produtores` | Público |
| GET | `/demandas/` | Produtor (ver abertas) |
| POST | `/demandas/` | Comprador |
| POST | `/demandas/{id}/aceitar` | Produtor |
| POST | `/viagens/` | Produtor |
| GET | `/viagens/` | Transportador (ver disponíveis) |
| POST | `/viagens/{id}/aceitar` | Transportador |
| POST | `/viagens/{id}/status/{status}` | Transportador |
| POST | `/viagens/{id}/avaliar/produtor` | Produtor |
| POST | `/viagens/{id}/avaliar/transportador` | Transportador |
| POST | `/viagens/{id}/avaliar/comprador` | Comprador |
| POST | `/mensagens/` | Produtor/Comprador/Transportador |
| GET | `/mensagens/conversa/{id}` | Todos |

---

## Próximos passos

- [ ] Migrar SQLite → PostgreSQL
- [ ] Upload de foto de perfil
- [ ] Notificações por e-mail
- [ ] WebSocket para chat em tempo real
- [ ] Mapa de rotas com API de mapas
- [ ] Sistema de pagamento integrado
- [ ] App mobile
