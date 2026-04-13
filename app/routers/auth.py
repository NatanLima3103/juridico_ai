from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import SESSION_COOKIE_NAME
from app.database import get_db
from app.routers.common import templates
from app.schemas.user import UserCreate
from app.services.audit_service import registrar_acao_usuario
from app.services.user_service import (
    atualizar_senha_usuario,
    autenticar_usuario,
    buscar_usuario_por_email,
    criar_usuario,
    gerar_token_recuperacao_senha,
    validar_redefinicao_senha,
    validar_solicitacao_recuperacao_senha,
    validar_token_recuperacao_senha,
    validar_dados_cadastro,
    validar_dados_login,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalizar_destino_pos_login(destino: str | None) -> str:
    destino_limpo = (destino or "").strip()
    if not destino_limpo.startswith("/"):
        return "/"
    if destino_limpo.startswith("//"):
        return "/"
    return destino_limpo


def _redirect_if_authenticated(request: Request) -> RedirectResponse | None:
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return None


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "title": "Criar conta",
            "erro": request.query_params.get("erro"),
            "sucesso": request.query_params.get("sucesso"),
            "form_data": {},
            "next": _normalizar_destino_pos_login(request.query_params.get("next")),
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Entrar",
            "erro": request.query_params.get("erro"),
            "sucesso": request.query_params.get("sucesso"),
            "form_data": {},
            "next": _normalizar_destino_pos_login(request.query_params.get("next")),
        },
    )


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "title": "Recuperar senha",
            "erro": None,
            "sucesso": None,
            "form_data": {},
            "reset_link": None,
        },
    )


@router.post("/register", response_class=HTMLResponse)
def register_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    form_data = {
        "full_name": full_name,
        "email": email,
    }

    try:
        dados = validar_dados_cadastro(
            full_name=full_name,
            email=email,
            password=password,
            confirm_password=confirm_password,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "title": "Criar conta",
                "erro": str(exc),
                "sucesso": None,
                "form_data": form_data,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if buscar_usuario_por_email(db, dados["email"]):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "title": "Criar conta",
                "erro": "Já existe uma conta cadastrada com este e-mail.",
                "sucesso": None,
                "form_data": form_data,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    payload = UserCreate(**dados)
    usuario = criar_usuario(db, payload)
    registrar_acao_usuario(
        db,
        action="user_register",
        usuario=usuario,
        request=request,
        metadata={"email": usuario.email},
    )

    return RedirectResponse(
        url="/auth/login?sucesso=Conta criada com sucesso. Faça seu login.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/login", response_class=HTMLResponse)
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/", alias="next"),
    db: Session = Depends(get_db),
):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    form_data = {
        "email": email,
    }
    next_url = _normalizar_destino_pos_login(next_url)

    try:
        dados = validar_dados_login(email=email, password=password)
    except ValueError as exc:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "Entrar",
                "erro": str(exc),
                "sucesso": None,
                "form_data": form_data,
                "next": next_url,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    usuario = autenticar_usuario(db, email=dados["email"], password=dados["password"])
    if not usuario:
        usuario_existente = buscar_usuario_por_email(db, dados["email"])
        registrar_acao_usuario(
            db,
            action="login_failed",
            usuario=usuario_existente,
            request=request,
            metadata={
                "email": dados["email"],
                "reason": "invalid_credentials",
                "has_user": usuario_existente is not None,
            },
        )
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "Entrar",
                "erro": "E-mail ou senha inválidos.",
                "sucesso": None,
                "form_data": form_data,
                "next": next_url,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    request.session["user_id"] = usuario.id
    request.session["user_name"] = usuario.full_name
    request.session["is_admin"] = bool(usuario.is_admin)
    registrar_acao_usuario(
        db,
        action="login_success",
        usuario=usuario,
        request=request,
        metadata={"next": next_url},
    )

    return RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_user(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    form_data = {"email": email}

    try:
        dados = validar_solicitacao_recuperacao_senha(email=email)
    except ValueError as exc:
        return templates.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "title": "Recuperar senha",
                "erro": str(exc),
                "sucesso": None,
                "form_data": form_data,
                "reset_link": None,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    usuario = buscar_usuario_por_email(db, dados["email"])
    reset_link = None
    if usuario and bool(usuario.is_active):
        token = gerar_token_recuperacao_senha(usuario)
        reset_link = str(request.url_for("reset_password_form", token=token))

    registrar_acao_usuario(
        db,
        action="password_reset_requested",
        usuario=usuario if usuario and bool(usuario.is_active) else None,
        request=request,
        metadata={
            "email": dados["email"],
            "active_user_found": bool(usuario and usuario.is_active),
        },
    )

    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "title": "Recuperar senha",
            "erro": None,
            "sucesso": "Se o e-mail estiver cadastrado, um link de recuperação foi gerado.",
            "form_data": form_data,
            "reset_link": reset_link,
        },
    )


@router.get("/reset-password/{token}", response_class=HTMLResponse, name="reset_password_form")
def reset_password_form(request: Request, token: str, db: Session = Depends(get_db)):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    usuario = validar_token_recuperacao_senha(db, token)
    if not usuario:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "title": "Redefinir senha",
                "erro": "O link de recuperação é inválido ou expirou.",
                "sucesso": None,
                "token": token,
                "token_valido": False,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request,
            "title": "Redefinir senha",
            "erro": None,
            "sucesso": None,
            "token": token,
            "token_valido": True,
        },
    )


@router.post("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_user(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    redirect_response = _redirect_if_authenticated(request)
    if redirect_response:
        return redirect_response

    usuario = validar_token_recuperacao_senha(db, token)
    if not usuario:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "title": "Redefinir senha",
                "erro": "O link de recuperação é inválido ou expirou.",
                "sucesso": None,
                "token": token,
                "token_valido": False,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dados = validar_redefinicao_senha(password=password, confirm_password=confirm_password)
    except ValueError as exc:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "title": "Redefinir senha",
                "erro": str(exc),
                "sucesso": None,
                "token": token,
                "token_valido": True,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    atualizar_senha_usuario(db, usuario, dados["password"])
    registrar_acao_usuario(
        db,
        action="password_reset_completed",
        usuario=usuario,
        request=request,
    )

    return RedirectResponse(
        url=f"/auth/login?sucesso={quote('Senha redefinida com sucesso. Faça seu login.')}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/logout")
def logout_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    try:
        user_id_int = int(user_id) if user_id else None
    except (TypeError, ValueError):
        user_id_int = None

    if user_id_int is not None:
        registrar_acao_usuario(
            db,
            action="logout",
            user_id=user_id_int,
            request=request,
        )

    request.session.clear()
    response = RedirectResponse(
        url="/auth/login?sucesso=Sess%C3%A3o+encerrada+com+sucesso.",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
