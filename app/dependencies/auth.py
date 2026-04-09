from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.user_service import buscar_usuario_por_id


def _build_login_redirect_url(request: Request, message: str = "Faça login para continuar.") -> str:
    next_path = request.url.path or "/"
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"

    return f"/auth/login?next={quote(next_path, safe='')}&erro={quote(message)}"


def get_authenticated_user(
    request: Request,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Autenticação necessária.",
            headers={"Location": _build_login_redirect_url(request)},
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Sessão inválida.",
            headers={"Location": _build_login_redirect_url(request, "Sua sessão é inválida. Faça login novamente.")},
        )

    usuario = buscar_usuario_por_id(db, user_id_int)
    if not usuario or not bool(usuario.is_active):
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Sessão expirada.",
            headers={"Location": _build_login_redirect_url(request, "Sua sessão expirou. Faça login novamente.")},
        )

    request.session["user_id"] = usuario.id
    request.session["user_name"] = usuario.full_name
    return usuario
