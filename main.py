from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import criar_tabelas, migrar_banco
from app.routes import auth, usuarios, catalogo, web, negociacao

app = FastAPI(
    title="AgroHub API",
    description="Plataforma de conexão entre produtores rurais, transportadores e compradores.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Web (HTML)
app.include_router(web.router)

# API
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(catalogo.router)
app.include_router(negociacao.router)

# Static
app.mount("/static", StaticFiles(directory="templates/static"), name="static")


@app.on_event("startup")
def startup():
    criar_tabelas()
    migrar_banco()


@app.get("/health", tags=["Status"])
def health():
    return {"status": "ok", "app": "AgroHub", "versao": "1.0.0"}
