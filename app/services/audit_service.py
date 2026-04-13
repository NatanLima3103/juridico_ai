import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


MAX_USER_AGENT_LENGTH = 500


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


def _normalizar_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {str(key): _normalizar_valor(item) for key, item in value.items()}


def _coletar_contexto_requisicao(request: Any | None) -> dict[str, Any]:
    if request is None:
        return {}

    client_host = None
    client = getattr(request, "client", None)
    if client is not None:
        client_host = getattr(client, "host", None)

    headers = getattr(request, "headers", {}) or {}
    user_agent = headers.get("user-agent") if hasattr(headers, "get") else None
    if user_agent and len(user_agent) > MAX_USER_AGENT_LENGTH:
        user_agent = f"{user_agent[:MAX_USER_AGENT_LENGTH]}..."

    url = getattr(request, "url", None)

    return {
        "ip": client_host,
        "method": getattr(request, "method", None),
        "path": getattr(url, "path", None),
        "user_agent": user_agent,
    }


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


def registrar_acao_usuario(
    db: Session,
    *,
    action: str,
    usuario: User | None = None,
    user_id: int | None = None,
    request: Any | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    usuario_id = usuario.id if usuario is not None else user_id
    snapshot: dict[str, Any] = {
        "user_id": usuario_id,
        "request": _coletar_contexto_requisicao(request),
        "metadata": _normalizar_mapping(metadata),
    }

    if usuario is not None:
        snapshot["user"] = {
            "id": usuario.id,
            "full_name": usuario.full_name,
            "email": usuario.email,
            "is_active": bool(usuario.is_active),
            "is_admin": bool(getattr(usuario, "is_admin", False)),
            "plan_slug": getattr(usuario, "plan_slug", None),
        }

    evento = registrar_evento_auditoria(
        db,
        user_id=usuario_id,
        entity_type="user" if usuario_id is not None else "auth",
        entity_id=int(usuario_id or 0),
        action=action,
        entity_version=1,
        snapshot=snapshot,
    )

    if commit:
        db.commit()

    return evento
