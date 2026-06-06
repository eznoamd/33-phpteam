from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import criar_tabelas, migrar_banco
from app.routes import auth, usuarios, catalogo, web, negociacao, ia

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
app.include_router(ia.router)

# Static
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

# Templates for error pages
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup():
    criar_tabelas()
    migrar_banco()


@app.get("/health", tags=["Status"])
def health():
    return {"status": "ok", "app": "AgroHub", "versao": "1.0.0"}


# Exception handlers for error pages
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("404.html", {"request": request})


@app.exception_handler(403)
async def forbidden_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("403.html", {"request": request})


@app.exception_handler(500)
async def internal_exception_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("500.html", {"request": request})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request})
    elif exc.status_code == 403:
        return templates.TemplateResponse("403.html", {"request": request})
    elif exc.status_code == 500:
        return templates.TemplateResponse("500.html", {"request": request})
    return templates.TemplateResponse("500.html", {"request": request})
