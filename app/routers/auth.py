from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import SESSION_COOKIE_NAME
from app.database import get_db
from app.routers.common import templates
from app.schemas.user import UserCreate
from app.services.user_service import (
    autenticar_usuario,
    buscar_usuario_por_email,
    criar_usuario,
    validar_dados_cadastro,
    validar_dados_login,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "title": "Criar conta",
            "erro": None,
            "sucesso": request.query_params.get("sucesso"),
            "form_data": {},
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Entrar",
            "erro": None,
            "sucesso": request.query_params.get("sucesso"),
            "form_data": {},
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
    criar_usuario(db, payload)

    return RedirectResponse(
        url="/auth/login?sucesso=Conta criada com sucesso. Faça seu login.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/login", response_class=HTMLResponse)
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    form_data = {
        "email": email,
    }

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
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    usuario = autenticar_usuario(db, email=dados["email"], password=dados["password"])
    if not usuario:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "Entrar",
                "erro": "E-mail ou senha inválidos.",
                "sucesso": None,
                "form_data": form_data,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    request.session["user_id"] = usuario.id
    request.session["user_name"] = usuario.full_name

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout_user(request: Request):
    request.session.clear()
    response = RedirectResponse(
        url="/auth/login?sucesso=Sess%C3%A3o+encerrada+com+sucesso.",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
