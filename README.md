# 🚜 AgroHub - CodeRace 2026
Conectando quem produz, transporta e movimenta o agro.

> Assista ao Pitch de 3 minutos aqui: https://youtu.be/eFlkO_FAPpw

## Identificação

Nome da Equipe: PHPteam

Integrantes:

- Artur Camera Segat - Dev (Fullstack)
- Enzo Augusto Mucha Domingues - Dev (Fullstack)
- Gabriel Mazui Azevedo - Dev (Fullstack)
- Lucas Lima Mendes - Negócios/Pitch
- Izabely Brum Rodrigues - Negócios/Pitch

## Escopo do Projeto

🎯 O Problema
A comercialização de safra e a logística no Brasil sofrem com ineficiências graves: negociações via WhatsApp (sem registro/segurança), falta de transparência sobre o histórico de motoristas e prejuízos bilionários causados por caminhões que retornam vazios após a entrega de insumos.

🚀 A Solução
O AgroHub é uma plataforma que atua como uma "Bolsa de Negócios" do campo. Unificamos a comercialização de safras (venda/compra) com um sistema de logística inteligente. Através de Inteligência Artificial, a plataforma protege o produtor, sugerindo faixas de preço de mercado (guardrails), e otimiza o frete, conectando cargas a caminhoneiros disponíveis na região.

## Stack Tecnológica
Linguagem: Python

Bibliotecas: [fastapi, uvicorn, sqlalchemy, pydantic, bcrypt, jinja2]


Integração de IA: Gemini API para análise de preços.

## Arquitetura

```
33-phpteam/
├── main.py
├── requirements.txt
├── .env.exemplo
├── app/
│   ├── config.py            # Pega as variaveis de ambiente
│   ├── database.py          # SQLite (trocar PostgreSQL em prod)
│   ├── seguranca.py         # Cuida de encriptações e segurança
│   ├── models/              # Tabelas do banco da aplicação
│   │   ├── [...]
│   ├── schemas/             # Validação Pydantic
│   └── routes/              # Rotas da aplicação
│       ├── [...]
└── templates/               # Todo o front-end da aplicação
    ├── [...]
```

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

Desenvolvido em 10 horas durante a CodeRace 2026.
