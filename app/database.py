from collections.abc import Callable

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

LATEST_SCHEMA_VERSION = 8


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


def _criar_tabela_schema_migrations(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _listar_migracoes_aplicadas(connection) -> set[int]:
    _criar_tabela_schema_migrations(connection)
    resultado = connection.execute(text("SELECT version FROM schema_migrations"))
    return {int(version) for (version,) in resultado.fetchall()}


def _registrar_migracao(connection, version: int, name: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO schema_migrations (version, name)
            VALUES (:version, :name)
            """
        ),
        {"version": version, "name": name},
    )


def _migration_001_add_metadata_columns(connection) -> None:
    ajustes = {
        "documents": {
            "tags": "ALTER TABLE documents ADD COLUMN tags TEXT",
            "is_favorite": "ALTER TABLE documents ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0",
            "status": "ALTER TABLE documents ADD COLUMN status TEXT",
        },
        "generations": {
            "is_pinned": "ALTER TABLE generations ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0",
            "tags": "ALTER TABLE generations ADD COLUMN tags TEXT",
            "is_favorite": "ALTER TABLE generations ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0",
            "status": "ALTER TABLE generations ADD COLUMN status TEXT",
        },
        "writing_profiles": {
            "is_pinned": "ALTER TABLE writing_profiles ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0",
            "tags": "ALTER TABLE writing_profiles ADD COLUMN tags TEXT",
            "is_favorite": "ALTER TABLE writing_profiles ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0",
            "status": "ALTER TABLE writing_profiles ADD COLUMN status TEXT",
        },
    }

    inspector = inspect(connection)
    tabelas_existentes = set(inspector.get_table_names())

    for tabela, colunas in ajustes.items():
        if tabela not in tabelas_existentes:
            continue

        for coluna, sql in colunas.items():
            if not _sqlite_column_exists(connection, tabela, coluna):
                connection.execute(text(sql))


def _migration_002_create_generation_documents(connection) -> None:
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


def _migration_003_sync_generation_documents(connection) -> None:
    _migrar_relacao_generation_documents(connection)
    _sincronizar_source_document_ids(connection)


def _migration_004_add_versioning_columns(connection) -> None:
    ajustes = {
        "documents": {
            "version": "ALTER TABLE documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
            "updated_at": "ALTER TABLE documents ADD COLUMN updated_at DATETIME",
        },
        "generations": {
            "version": "ALTER TABLE generations ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
        },
        "writing_profiles": {
            "version": "ALTER TABLE writing_profiles ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
            "updated_at": "ALTER TABLE writing_profiles ADD COLUMN updated_at DATETIME",
        },
    }

    inspector = inspect(connection)
    tabelas_existentes = set(inspector.get_table_names())

    for tabela, colunas in ajustes.items():
        if tabela not in tabelas_existentes:
            continue

        for coluna, sql in colunas.items():
            if not _sqlite_column_exists(connection, tabela, coluna):
                connection.execute(text(sql))

    connection.execute(
        text("UPDATE documents SET version = COALESCE(version, 1), updated_at = COALESCE(updated_at, created_at)")
    )
    connection.execute(
        text("UPDATE generations SET version = COALESCE(version, 1)")
    )
    connection.execute(
        text(
            "UPDATE writing_profiles SET version = COALESCE(version, 1), updated_at = COALESCE(updated_at, created_at)"
        )
    )


def _migration_005_create_audit_logs(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50) NOT NULL,
                entity_id INTEGER NOT NULL,
                action VARCHAR(50) NOT NULL,
                entity_version INTEGER NOT NULL DEFAULT 1,
                payload TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _migration_006_prepare_users_table(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    connection.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email)")
    )


def _migration_007_link_documents_to_users(connection) -> None:
    if not _sqlite_column_exists(connection, "documents", "user_id"):
        connection.execute(text("ALTER TABLE documents ADD COLUMN user_id INTEGER"))

    connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id)")
    )

    usuarios = connection.execute(text("SELECT id FROM users ORDER BY id ASC")).fetchall()
    if len(usuarios) == 1:
        unico_usuario_id = int(usuarios[0][0])
        connection.execute(
            text("UPDATE documents SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": unico_usuario_id},
        )


def _migration_008_link_writing_profiles_to_users(connection) -> None:
    if not _sqlite_column_exists(connection, "writing_profiles", "user_id"):
        connection.execute(text("ALTER TABLE writing_profiles ADD COLUMN user_id INTEGER"))

    connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_writing_profiles_user_id ON writing_profiles (user_id)")
    )

    usuarios = connection.execute(text("SELECT id FROM users ORDER BY id ASC")).fetchall()
    if len(usuarios) == 1:
        unico_usuario_id = int(usuarios[0][0])
        connection.execute(
            text("UPDATE writing_profiles SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": unico_usuario_id},
        )


SQLITE_MIGRATIONS: list[tuple[int, str, Callable]] = [
    (1, "add_metadata_columns", _migration_001_add_metadata_columns),
    (2, "create_generation_documents", _migration_002_create_generation_documents),
    (3, "sync_generation_documents", _migration_003_sync_generation_documents),
    (4, "add_versioning_columns", _migration_004_add_versioning_columns),
    (5, "create_audit_logs", _migration_005_create_audit_logs),
    (6, "prepare_users_table", _migration_006_prepare_users_table),
    (7, "link_documents_to_users", _migration_007_link_documents_to_users),
    (8, "link_writing_profiles_to_users", _migration_008_link_writing_profiles_to_users),
]


def ensure_database_schema() -> None:
    """
    Aplica migracoes incrementais e idempotentes para bancos SQLite existentes.
    Cada versao e registrada em schema_migrations para facilitar evolucao futura.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        migracoes_aplicadas = _listar_migracoes_aplicadas(connection)

        for version, name, migration_fn in SQLITE_MIGRATIONS:
            if version in migracoes_aplicadas:
                continue

            migration_fn(connection)
            _registrar_migracao(connection, version, name)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_database_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
