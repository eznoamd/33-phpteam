import json
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models.usuario import Usuario
from app.models.demanda import Demanda
from app.models.viagem import Viagem
from app.seguranca import criar_token, hash_senha, verificar_senha

router = APIRouter(tags=["Frontend"])
templates = Jinja2Templates(directory="templates")

COOKIE_NAME = "agrohub_session"


def get_session_usuario(request: Request, db: Session) -> Usuario | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        uid = payload.get("sub")
        if uid is None:
            return None
        return db.query(Usuario).filter(Usuario.id == int(uid), Usuario.ativo == True).first()
    except JWTError:
        return None


def flash_messages(request: Request) -> list[dict]:
    raw = request.cookies.get("flash")
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def render(template: str, request: Request, db: Session, **ctx):
    msgs = flash_messages(request)
    usuario = get_session_usuario(request, db)
    response = templates.TemplateResponse(
        template,
        {"request": request, "session_usuario": usuario, "flash_messages": msgs, **ctx},
    )
    if msgs:
        response.delete_cookie("flash")
    return response


def redirect_flash(url: str, tipo: str, texto: str) -> RedirectResponse:
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie("flash", json.dumps([{"tipo": tipo, "texto": texto}]), httponly=True)
    return resp


# ── Páginas públicas ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)):
    if get_session_usuario(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return render("landing.html", request, db)


@router.get("/catalogo", response_class=HTMLResponse)
def catalogo(request: Request, db: Session = Depends(get_db)):
    produtores = db.query(Usuario).filter(
        Usuario.perfil == "produtor", Usuario.ativo == True
    ).order_by(Usuario.avaliacao_media.desc()).all()
    return render("catalogo.html", request, db, produtores=produtores)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_session_usuario(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return render("login.html", request, db)


@router.get("/cadastro", response_class=HTMLResponse)
def cadastro_page(request: Request, db: Session = Depends(get_db)):
    if get_session_usuario(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return render("cadastro.html", request, db)


# ── Auth forms ────────────────────────────────────────────────────────────────

@router.post("/auth/login-form")
def login_form(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        resp = redirect_flash("/login", "error", "E-mail ou senha incorretos.")
        resp.set_cookie("flash_email", email, httponly=True)
        return resp
    if not usuario.ativo:
        return redirect_flash("/login", "error", "Conta desativada.")
    token = criar_token({"sub": str(usuario.id)})
    resp = redirect_flash("/dashboard", "success", f"Bem-vindo, {usuario.nome.split()[0]}!")
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return resp


@router.post("/cadastro")
def cadastro_form(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(Usuario).filter(Usuario.email == email).first():
        return render("cadastro.html", request, db,
                      flash_messages=[{"tipo": "error", "texto": "E-mail já cadastrado."}],
                      nome_anterior=nome, email_anterior=email)
    if len(senha) < 6:
        return render("cadastro.html", request, db,
                      flash_messages=[{"tipo": "error", "texto": "Senha deve ter ao menos 6 caracteres."}],
                      nome_anterior=nome, email_anterior=email)
    if perfil not in {"produtor", "transportador", "comprador"}:
        return render("cadastro.html", request, db,
                      flash_messages=[{"tipo": "error", "texto": "Perfil inválido."}])
    novo = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), perfil=perfil)
    db.add(novo)
    db.commit()
    return redirect_flash("/login", "success", "Conta criada! Faça login para continuar.")


@router.get("/auth/logout")
def logout():
    resp = redirect_flash("/", "success", "Até logo!")
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ── Dashboard (área logada) ───────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")

    ctx = {}

    if usuario.perfil == "produtor":
        demandas_abertas = db.query(Demanda).filter(Demanda.status == "aberta").order_by(Demanda.criado_em.desc()).limit(10).all()
        minhas_viagens = db.query(Viagem).filter(Viagem.produtor_id == usuario.id).order_by(Viagem.criado_em.desc()).limit(10).all()
        ctx = {"demandas_abertas": demandas_abertas, "minhas_viagens": minhas_viagens}

    elif usuario.perfil == "transportador":
        viagens_disponiveis = db.query(Viagem).filter(Viagem.status == "aguardando_transportador").order_by(Viagem.criado_em.desc()).limit(10).all()
        minhas_viagens = db.query(Viagem).filter(Viagem.transportador_id == usuario.id).order_by(Viagem.criado_em.desc()).limit(10).all()
        ctx = {"viagens_disponiveis": viagens_disponiveis, "minhas_viagens": minhas_viagens}

    elif usuario.perfil == "comprador":
        minhas_demandas = db.query(Demanda).filter(Demanda.comprador_id == usuario.id).order_by(Demanda.criado_em.desc()).limit(10).all()
        minhas_viagens = db.query(Viagem).filter(Viagem.comprador_id == usuario.id).order_by(Viagem.criado_em.desc()).limit(10).all()
        ctx = {"minhas_demandas": minhas_demandas, "minhas_viagens": minhas_viagens}

    return render("dashboard.html", request, db, **ctx)


@router.get("/perfil", response_class=HTMLResponse)
def perfil_page(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")
    return render("perfil.html", request, db)


@router.get("/demandas", response_class=HTMLResponse)
def demandas_page(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")
    demandas = db.query(Demanda).filter(Demanda.status == "aberta").order_by(Demanda.criado_em.desc()).all()
    return render("demandas.html", request, db, demandas=demandas)


@router.get("/viagens", response_class=HTMLResponse)
def viagens_page(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")
    viagens = db.query(Viagem).filter(Viagem.status == "aguardando_transportador").order_by(Viagem.criado_em.desc()).all()
    return render("viagens.html", request, db, viagens=viagens)
