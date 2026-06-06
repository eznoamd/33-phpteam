from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCriar
from app.seguranca import verificar_senha, criar_token, hash_senha
from app.config import config
from jose import JWTError, jwt

router = APIRouter(tags=["🖥️  Frontend"])
templates = Jinja2Templates(directory="templates")

COOKIE_NAME = "session_token"


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
    import json
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
        {
            "request": request,
            "session_usuario": usuario,
            "flash_messages": msgs,
            **ctx,
        },
    )
    if msgs:
        response.delete_cookie("flash")
    return response


def redirect_with_flash(url: str, tipo: str, texto: str) -> RedirectResponse:
    import json
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie("flash", json.dumps([{"tipo": tipo, "texto": texto}]), httponly=True)
    return resp


def require_login(request: Request, db: Session) -> Usuario | None:
    return get_session_usuario(request, db)


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if usuario:
        return RedirectResponse("/dashboard", status_code=302)
    return render("index.html", request, db)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_session_usuario(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return render("login.html", request, db)


@router.post("/auth/login-form")
def login_form(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        resp = redirect_with_flash("/login", "error", "E-mail ou senha incorretos.")
        resp.set_cookie("flash_email", email, httponly=True)
        return resp

    if not usuario.ativo:
        return redirect_with_flash("/login", "error", "Conta desativada.")

    token = criar_token({"sub": str(usuario.id)})
    resp = redirect_with_flash("/dashboard", "success", f"Bem-vindo(a), {usuario.nome}!")
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return resp


@router.get("/cadastro", response_class=HTMLResponse)
def cadastro_page(request: Request, db: Session = Depends(get_db)):
    if get_session_usuario(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return render("cadastro.html", request, db)


@router.post("/cadastro")
def cadastro_form(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
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

    novo = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha))
    db.add(novo)
    db.commit()
    return redirect_with_flash("/login", "success", "Conta criada! Faça login para continuar.")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_with_flash("/login", "info", "Faça login para acessar o dashboard.")

    usuarios = db.query(Usuario).all()
    return render("dashboard.html", request, db, usuarios=usuarios)


@router.get("/ia", response_class=HTMLResponse)
def ia_page(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_with_flash("/login", "info", "Faça login para usar a IA.")
    token = request.cookies.get(COOKIE_NAME, "")
    return render("ia.html", request, db, token=token)


@router.get("/auth/logout")
def logout():
    resp = redirect_with_flash("/login", "success", "Você saiu. Até logo!")
    resp.delete_cookie(COOKIE_NAME)
    return resp
