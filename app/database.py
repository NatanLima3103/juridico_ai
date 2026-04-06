from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def _sqlite_column_exists(connection, table_name: str, column_name: str) -> bool:
    resultado = connection.execute(text(f"PRAGMA table_info({table_name})"))
    colunas = {linha[1] for linha in resultado.fetchall()}
    return column_name in colunas


def ensure_database_schema() -> None:
    """
    Ajustes incrementais de schema para SQLite sem quebrar bancos já existentes.
    Mantém compatibilidade com o estágio atual do projeto.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)

    ajustes = {
        "generations": {
            "is_pinned": "ALTER TABLE generations ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0",
        },
        "writing_profiles": {
            "is_pinned": "ALTER TABLE writing_profiles ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0",
        },
    }

    with engine.begin() as connection:
        tabelas_existentes = set(inspector.get_table_names())

        for tabela, colunas in ajustes.items():
            if tabela not in tabelas_existentes:
                continue

            for coluna, sql in colunas.items():
                if not _sqlite_column_exists(connection, tabela, coluna):
                    connection.execute(text(sql))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()