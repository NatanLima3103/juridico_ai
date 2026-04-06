from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if not DATABASE_URL.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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


def _sqlite_table_exists(connection, table_name: str) -> bool:
    resultado = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name = :table_name"),
        {"table_name": table_name},
    )
    return resultado.first() is not None


def _migrar_relacao_generation_documents(connection) -> None:
    if not _sqlite_table_exists(connection, "generation_documents"):
        return

    registros = connection.execute(
        text("SELECT id, source_document_ids FROM generations WHERE source_document_ids IS NOT NULL")
    ).fetchall()

    for generation_id, source_document_ids in registros:
        if not source_document_ids:
            continue

        ids_validos: list[int] = []
        for parte in str(source_document_ids).split(","):
            valor = parte.strip()
            if not valor:
                continue
            try:
                document_id = int(valor)
            except ValueError:
                continue
            if document_id not in ids_validos:
                ids_validos.append(document_id)

        for document_id in ids_validos:
            documento_existe = connection.execute(
                text("SELECT 1 FROM documents WHERE id = :document_id LIMIT 1"),
                {"document_id": document_id},
            ).first()

            if not documento_existe:
                continue

            connection.execute(
                text(
                    """
                    INSERT OR IGNORE INTO generation_documents (generation_id, document_id)
                    VALUES (:generation_id, :document_id)
                    """
                ),
                {"generation_id": generation_id, "document_id": document_id},
            )


def _sincronizar_source_document_ids(connection) -> None:
    if not _sqlite_table_exists(connection, "generation_documents"):
        return

    generation_ids = connection.execute(text("SELECT id FROM generations")).fetchall()

    for (generation_id,) in generation_ids:
        vinculados = connection.execute(
            text(
                """
                SELECT document_id
                FROM generation_documents
                WHERE generation_id = :generation_id
                ORDER BY document_id
                """
            ),
            {"generation_id": generation_id},
        ).fetchall()

        serializado = ",".join(str(document_id) for (document_id,) in vinculados)
        connection.execute(
            text(
                "UPDATE generations SET source_document_ids = :source_document_ids WHERE id = :generation_id"
            ),
            {
                "generation_id": generation_id,
                "source_document_ids": serializado or None,
            },
        )


def ensure_database_schema() -> None:
    """
    Ajustes incrementais de schema para SQLite sem quebrar bancos já existentes.
    Mantém compatibilidade com o estágio atual do projeto.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    ajustes = {
        "generations": {
            "is_pinned": "ALTER TABLE generations ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0",
        },
        "writing_profiles": {
            "is_pinned": "ALTER TABLE writing_profiles ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0",
        },
    }

    with engine.begin() as connection:
        inspector = inspect(connection)
        tabelas_existentes = set(inspector.get_table_names())

        for tabela, colunas in ajustes.items():
            if tabela not in tabelas_existentes:
                continue

            for coluna, sql in colunas.items():
                if not _sqlite_column_exists(connection, tabela, coluna):
                    connection.execute(text(sql))

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS generation_documents (
                    generation_id INTEGER NOT NULL,
                    document_id INTEGER NOT NULL,
                    PRIMARY KEY (generation_id, document_id),
                    FOREIGN KEY(generation_id) REFERENCES generations (id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
                )
                """
            )
        )

        _migrar_relacao_generation_documents(connection)
        _sincronizar_source_document_ids(connection)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()