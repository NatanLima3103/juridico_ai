from sqlalchemy import text

from app.core.config import settings
from app.database import SessionLocal, initialize_database
from app.models import AuditLog, Document, Generation, User, WritingProfile  # noqa: F401


def main() -> None:
    if not settings.is_production:
        raise SystemExit("Defina APP_ENV=production para preparar o banco de producao.")

    if not settings.is_postgres_database:
        raise SystemExit("DATABASE_URL deve apontar para PostgreSQL em producao.")

    initialize_database()

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))

    print("Banco de producao preparado e conexao validada.")


if __name__ == "__main__":
    main()
