import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _normalizar_valor(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, Iterable) and not isinstance(value, (dict, str, bytes)):
        return [_normalizar_valor(item) for item in value]
    return str(value)


def serializar_entidade_para_auditoria(entity: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}

    table = getattr(entity, "__table__", None)
    if table is not None:
        for column in table.columns:
            snapshot[column.name] = _normalizar_valor(getattr(entity, column.name, None))

    if hasattr(entity, "document_ids"):
        snapshot["document_ids"] = _normalizar_valor(getattr(entity, "document_ids"))

    if hasattr(entity, "writing_profile_name"):
        snapshot["writing_profile_name"] = _normalizar_valor(getattr(entity, "writing_profile_name"))

    return snapshot


def registrar_evento_auditoria(
    db: Session,
    *,
    user_id: int | None = None,
    entity_type: str,
    entity_id: int,
    action: str,
    entity_version: int,
    snapshot: dict[str, Any],
) -> AuditLog:
    user_id_auditoria = user_id
    if user_id_auditoria is None:
        user_id_snapshot = snapshot.get("user_id")
        if isinstance(user_id_snapshot, int):
            user_id_auditoria = user_id_snapshot

    evento = AuditLog(
        user_id=user_id_auditoria,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        entity_version=entity_version,
        payload=json.dumps(snapshot, ensure_ascii=True, sort_keys=True),
    )
    db.add(evento)
    return evento
