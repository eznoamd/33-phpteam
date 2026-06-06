from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import criar_tabelas
from app.routes import usuarios, itens, auth, ia, web

app = FastAPI(
    title="Meu Projeto CodeRace",
    description="Template base.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(web.router)
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(itens.router)
app.include_router(ia.router)

app.mount("/static", StaticFiles(directory="templates/static"), name="static")

@app.on_event("startup")
def startup():
    criar_tabelas()

@app.get("/", tags=["Status"])
def raiz():
    return {
        "status": "ok",
        "mensagem": "API rodando! Acesse /docs para ver os endpoints.",
        "docs": "http://localhost:8000/docs",
    }

