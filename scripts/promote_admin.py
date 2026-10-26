import argparse

from app.database import SessionLocal, initialize_database
from app.models import AuditLog, Document, Generation, User, WritingProfile  # noqa: F401
from app.services.audit_service import registrar_acao_usuario
from app.services.user_service import atualizar_status_usuario, buscar_usuario_por_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Concede ou revoga acesso administrativo de uma conta existente.")
    parser.add_argument("email", help="E-mail da conta ja cadastrada.")
    parser.add_argument("--revogar", action="store_true", help="Remove o acesso administrativo em vez de conceder.")
    args = parser.parse_args()

    is_admin = not args.revogar
    initialize_database()

    with SessionLocal() as session:
        usuario = buscar_usuario_por_email(session, args.email)
        if not usuario:
            raise SystemExit(f"Nenhuma conta encontrada com o e-mail {args.email}. Cadastre-a pelo site primeiro.")

        atualizar_status_usuario(session, usuario, is_admin=is_admin)
        registrar_acao_usuario(
            session,
            action="admin_granted_cli" if is_admin else "admin_revoked_cli",
            usuario=usuario,
            metadata={"source": "scripts/promote_admin.py"},
        )
        email = usuario.email

    situacao = "agora e administradora" if is_admin else "nao e mais administradora"
    print(f"A conta {email} {situacao}.")


if __name__ == "__main__":
    main()
