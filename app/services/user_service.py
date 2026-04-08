from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def _normalizar_texto(valor: str | None) -> str:
    return (valor or "").strip()


def _normalizar_email(email: str | None) -> str:
    return _normalizar_texto(email).lower()


def buscar_usuario_por_email(db: Session, email: str) -> User | None:
    email_normalizado = _normalizar_email(email)
    if not email_normalizado:
        return None
    return db.query(User).filter(User.email == email_normalizado).first()


def buscar_usuario_por_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def validar_dados_cadastro(
    *,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
) -> dict[str, str]:
    full_name = _normalizar_texto(full_name)
    email = _normalizar_email(email)
    password = (password or "").strip()
    confirm_password = (confirm_password or "").strip()

    if not full_name:
        raise ValueError("Informe seu nome completo.")
    if len(full_name) < 3:
        raise ValueError("O nome completo deve ter pelo menos 3 caracteres.")

    if not email:
        raise ValueError("Informe seu e-mail.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Informe um e-mail válido.")

    if not password:
        raise ValueError("Informe uma senha.")
    if len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    if password != confirm_password:
        raise ValueError("A confirmação de senha não confere.")

    return {
        "full_name": full_name,
        "email": email,
        "password": password,
    }


def criar_usuario(db: Session, payload: UserCreate) -> User:
    usuario = User(
        full_name=_normalizar_texto(payload.full_name),
        email=_normalizar_email(payload.email),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def validar_dados_login(*, email: str, password: str) -> dict[str, str]:
    email = _normalizar_email(email)
    password = (password or "").strip()

    if not email:
        raise ValueError("Informe seu e-mail.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Informe um e-mail válido.")
    if not password:
        raise ValueError("Informe sua senha.")

    return {
        "email": email,
        "password": password,
    }


def autenticar_usuario(db: Session, *, email: str, password: str) -> User | None:
    usuario = buscar_usuario_por_email(db, email)
    if not usuario:
        return None
    if not bool(usuario.is_active):
        return None
    if not verify_password(password, usuario.password_hash):
        return None
    return usuario
