from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import criar_tabelas
from app.routes import auth, usuarios, demandas, viagens, mensagens, catalogo, web

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
app.include_router(demandas.router)
app.include_router(viagens.router)
app.include_router(mensagens.router)
app.include_router(catalogo.router)

# Static
app.mount("/static", StaticFiles(directory="templates/static"), name="static")


@app.on_event("startup")
def startup():
    criar_tabelas()


@app.get("/health", tags=["Status"])
def health():
    return {"status": "ok", "app": "AgroHub", "versao": "1.0.0"}
