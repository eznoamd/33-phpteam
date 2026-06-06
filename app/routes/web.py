import json
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models.usuario import Usuario
from app.models.negociacao import OfertaMercado, ContratoTransporte
from app.seguranca import criar_token, hash_senha, verificar_senha

router = APIRouter(tags=["Frontend"])
templates = Jinja2Templates(directory="templates")

COOKIE_NAME = "agrohub_session"


def primeiro_nome(nome: str) -> str:
    nome_limpo = (nome or "").strip()
    return nome_limpo.split()[0] if nome_limpo else "usuário"


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
def catalogo(request: Request, tipo: str = "produtor", db: Session = Depends(get_db)):
    if tipo not in {"produtor", "comprador", "transportador"}:
        tipo = "produtor"
    usuarios = db.query(Usuario).filter(
        Usuario.perfil == tipo, Usuario.ativo == True
    ).order_by(Usuario.avaliacao_media.desc()).all()
    return render("catalogo.html", request, db, usuarios=usuarios, tipo=tipo)


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
    resp = redirect_flash("/dashboard", "success", f"Bem-vindo, {primeiro_nome(usuario.nome)}!")
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=request.url.scheme == "https",
    )
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
    db.refresh(novo)
    token = criar_token({"sub": str(novo.id)})
    resp = redirect_flash("/dashboard", "success", f"Conta criada! Bem-vindo, {primeiro_nome(novo.nome)}!")
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=request.url.scheme == "https",
    )
    return resp


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
        minhas_ofertas = db.query(OfertaMercado).filter(
            OfertaMercado.autor_id == usuario.id
        ).order_by(OfertaMercado.id.desc()).limit(10).all()
        
        meus_contratos = db.query(ContratoTransporte).filter(
            ContratoTransporte.vendedor_id == usuario.id
        ).order_by(ContratoTransporte.id.desc()).limit(5).all()
        
        ofertas_disponiveis = db.query(OfertaMercado).filter(
            OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO", "AGUARDANDO_ACEITE"]),
            OfertaMercado.autor_id != usuario.id,
            OfertaMercado.tipo_demanda == "QUERO_COMPRAR",
        ).order_by(OfertaMercado.id.desc()).limit(5).all()
        
        ctx = {
            "minhas_ofertas": minhas_ofertas,
            "meus_contratos": meus_contratos,
            "ofertas_disponiveis": ofertas_disponiveis,
        }

    elif usuario.perfil == "comprador":
        minhas_ofertas = db.query(OfertaMercado).filter(
            OfertaMercado.autor_id == usuario.id
        ).order_by(OfertaMercado.id.desc()).limit(10).all()
        
        meus_contratos = db.query(ContratoTransporte).filter(
            ContratoTransporte.comprador_id == usuario.id
        ).order_by(ContratoTransporte.id.desc()).limit(5).all()
        
        ofertas_disponiveis = db.query(OfertaMercado).filter(
            OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO"]),
            OfertaMercado.autor_id != usuario.id,
            OfertaMercado.tipo_demanda == "QUERO_VENDER",
        ).order_by(OfertaMercado.id.desc()).limit(5).all()
        
        ctx = {
            "minhas_ofertas": minhas_ofertas,
            "meus_contratos": meus_contratos,
            "ofertas_disponiveis": ofertas_disponiveis,
        }

    # Mantendo o transportador mapeado para evitar quebras no render
    elif usuario.perfil == "transportador":
        fretes_disponiveis = db.query(ContratoTransporte).filter(
            ContratoTransporte.status_logistica.in_([
                "AGUARDANDO_TRANSPORTADOR", "EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE"
            ])
        ).order_by(ContratoTransporte.id.desc()).limit(10).all()
        meus_fretes = db.query(ContratoTransporte).filter(
            ContratoTransporte.transportador_id == usuario.id
        ).order_by(ContratoTransporte.id.desc()).limit(10).all()
        ctx = {"fretes_disponiveis": fretes_disponiveis, "meus_fretes": meus_fretes}

    return render("dashboard.html", request, db, **ctx)


@router.get("/perfil", response_class=HTMLResponse)
def perfil_page(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")
    return render("perfil.html", request, db)


# ── Marketplace ───────────────────────────────────────────────────────────────

@router.get("/mercado", response_class=HTMLResponse)
def mercado_page(
    request: Request,
    produto: str = "",
    tipo: str = "",
    db: Session = Depends(get_db),
):
    q = db.query(OfertaMercado).filter(
        OfertaMercado.status.in_(["ABERTA", "EM_NEGOCIACAO", "AGUARDANDO_ACEITE"])
    )
    if produto:
        q = q.filter(OfertaMercado.produto.ilike(f"%{produto}%"))
    if tipo:
        q = q.filter(OfertaMercado.tipo_demanda == tipo.upper())
    ofertas = q.order_by(OfertaMercado.id.desc()).limit(50).all()
    return render("mercado.html", request, db, ofertas=ofertas, filtro_produto=produto, filtro_tipo=tipo)


@router.get("/negociacao/{oferta_id}", response_class=HTMLResponse)
def negociacao_page(oferta_id: int, request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para negociar.")

    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == oferta_id).first()
    if not oferta:
        return redirect_flash("/mercado", "error", "Oferta não encontrada.")

    lances = (
        db.query(NegociacaoLance)
        .filter(NegociacaoLance.oferta_id == oferta_id)
        .order_by(NegociacaoLance.id)
        .all()
    )

    ultimo_pendente = (
        db.query(NegociacaoLance)
        .filter(
            NegociacaoLance.oferta_id == oferta_id,
            NegociacaoLance.status_lance == "PENDENTE",
        )
        .order_by(NegociacaoLance.id.desc())
        .first()
    )

    autor = db.query(Usuario).filter(Usuario.id == oferta.autor_id).first()
    since_id = lances[-1].id if lances else 0

    contrato = None
    if oferta.status == "FECHADA":
        contrato = db.query(ContratoTransporte).filter(
            ContratoTransporte.oferta_id == oferta_id
        ).first()

    lances_pendentes = [l for l in lances if l.status_lance == "PENDENTE"]
    ids_proponentes = {l.proponente_id for l in lances_pendentes}
    proponentes_negociacao = db.query(Usuario).filter(Usuario.id.in_(ids_proponentes)).all() if ids_proponentes else []
    proponentes_map = {u.id: u for u in proponentes_negociacao}

    pode_aceitar_contra_oferta = (
        oferta.status == "AGUARDANDO_ACEITE"
        and usuario.perfil != "transportador"
        and oferta.autor_id != usuario.id
        and not any(l.proponente_id == usuario.id for l in lances_pendentes)
    )
    pode_publicar_contra_proposta = (
        oferta.status in ("EM_NEGOCIACAO", "AGUARDANDO_ACEITE")
        and oferta.autor_id == usuario.id
    )

    return render(
        "negociacao.html",
        request,
        db,
        oferta=oferta,
        lances=lances,
        lances_pendentes=lances_pendentes,
        proponentes_map=proponentes_map,
        ultimo_pendente=ultimo_pendente,
        autor=autor,
        since_id=since_id,
        contrato=contrato,
        pode_aceitar_contra_oferta=pode_aceitar_contra_oferta,
        pode_publicar_contra_proposta=pode_publicar_contra_proposta,
    )


@router.get("/meus-contratos", response_class=HTMLResponse)
def meus_contratos_page(request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")

    if usuario.perfil == "transportador":
        disponiveis = (
            db.query(ContratoTransporte)
            .filter(ContratoTransporte.status_logistica.in_([
                "AGUARDANDO_TRANSPORTADOR", "EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE"
            ]))
            .order_by(ContratoTransporte.id.desc())
            .all()
        )
        meus = (
            db.query(ContratoTransporte)
            .filter(ContratoTransporte.transportador_id == usuario.id)
            .order_by(ContratoTransporte.id.desc())
            .all()
        )
        contratos = meus
        fretes_disponiveis = disponiveis
    elif usuario.perfil == "produtor":
        contratos = (
            db.query(ContratoTransporte)
            .filter(ContratoTransporte.vendedor_id == usuario.id)
            .order_by(ContratoTransporte.id.desc())
            .all()
        )
        fretes_disponiveis = []
    else:
        contratos = (
            db.query(ContratoTransporte)
            .filter(ContratoTransporte.comprador_id == usuario.id)
            .order_by(ContratoTransporte.id.desc())
            .all()
        )
        fretes_disponiveis = []

    # Carrega oferta para cada contrato (para mostrar produto)
    oferta_map = {}
    for c in contratos + fretes_disponiveis:
        if c.oferta_id not in oferta_map:
            oferta_map[c.oferta_id] = db.query(OfertaMercado).filter(
                OfertaMercado.id == c.oferta_id
            ).first()

    return render(
        "meus_contratos.html",
        request,
        db,
        contratos=contratos,
        fretes_disponiveis=fretes_disponiveis,
        oferta_map=oferta_map,
    )


@router.get("/contratos/{contrato_id}", response_class=HTMLResponse)
def contrato_page(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    usuario = get_session_usuario(request, db)
    if not usuario:
        return redirect_flash("/login", "info", "Faça login para acessar.")

    contrato = db.query(ContratoTransporte).filter(ContratoTransporte.id == contrato_id).first()
    if not contrato:
        return redirect_flash("/mercado", "error", "Contrato não encontrado.")

    partes = {contrato.vendedor_id, contrato.comprador_id, contrato.transportador_id}
    if usuario.id not in partes and usuario.perfil != "transportador":
        return redirect_flash("/dashboard", "error", "Acesso não autorizado.")

    vendedor = db.query(Usuario).filter(Usuario.id == contrato.vendedor_id).first()
    comprador = db.query(Usuario).filter(Usuario.id == contrato.comprador_id).first()
    transportador = (
        db.query(Usuario).filter(Usuario.id == contrato.transportador_id).first()
        if contrato.transportador_id else None
    )
    oferta = db.query(OfertaMercado).filter(OfertaMercado.id == contrato.oferta_id).first()

    lances_frete = (
        db.query(LanceFrete)
        .filter(LanceFrete.contrato_id == contrato_id)
        .order_by(LanceFrete.id)
        .all()
    )
    lances_pendentes = [l for l in lances_frete if l.status == "PENDENTE"]
    responsavel_frete_id = (
        contrato.vendedor_id if contrato.responsavel_frete == "VENDEDOR" else contrato.comprador_id
    )
    meu_lance_pendente = next(
        (l for l in lances_pendentes if l.proponente_id == usuario.id), None
    )

    # Monta mapa proponente_id → nome (para a view do responsável)
    ids_proponentes = {l.proponente_id for l in lances_frete}
    proponentes = db.query(Usuario).filter(Usuario.id.in_(ids_proponentes)).all()
    proponentes_map = {u.id: u for u in proponentes}

    status = contrato.status_logistica
    pode_propor_frete = (
        usuario.perfil == "transportador"
        and status in ("AGUARDANDO_TRANSPORTADOR", "EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE")
        and meu_lance_pendente is None
    )
    pode_contra_propor = (
        usuario.id == responsavel_frete_id
        and status in ("EM_NEGOCIACAO_FRETE", "AGUARDANDO_ACEITE_FRETE")
    )
    pode_aceitar_contra_oferta = (
        usuario.perfil == "transportador" and status == "AGUARDANDO_ACEITE_FRETE"
    )
    since_id_frete = lances_frete[-1].id if lances_frete else 0

    return render(
        "contrato.html",
        request,
        db,
        contrato=contrato,
        vendedor=vendedor,
        comprador=comprador,
        transportador=transportador,
        oferta=oferta,
        lances_frete=lances_frete,
        lances_pendentes=lances_pendentes,
        meu_lance_pendente=meu_lance_pendente,
        responsavel_frete_id=responsavel_frete_id,
        proponentes_map=proponentes_map,
        pode_propor_frete=pode_propor_frete,
        pode_contra_propor=pode_contra_propor,
        pode_aceitar_contra_oferta=pode_aceitar_contra_oferta,
        since_id_frete=since_id_frete,
    )
