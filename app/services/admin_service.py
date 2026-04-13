from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.generation import Generation
from app.models.user import User
from app.services.audit_service import registrar_acao_usuario
from app.services.plan_service import obter_plano_usuario
from app.models.writing_profile import WritingProfile
from app.services.user_service import atualizar_status_usuario, buscar_usuario_por_id, listar_usuarios


def obter_totais_sistema(db: Session) -> dict[str, int]:
    return {
        "usuarios": db.query(User).count(),
        "usuarios_ativos": db.query(User).filter(User.is_active.is_(True)).count(),
        "admins": db.query(User).filter(User.is_admin.is_(True)).count(),
        "documentos": db.query(Document).filter(Document.deleted_at.is_(None)).count(),
        "perfis": db.query(WritingProfile).filter(WritingProfile.deleted_at.is_(None)).count(),
        "geracoes": db.query(Generation).filter(Generation.deleted_at.is_(None)).count(),
        "auditorias": db.query(AuditLog).count(),
    }


def obter_metricas_basicas_admin(db: Session) -> dict[str, Any]:
    agora = datetime.now()
    inicio_7_dias = agora - timedelta(days=6)
    inicio_30_dias = agora - timedelta(days=29)

    atividades_recentes = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .filter(AuditLog.created_at >= inicio_7_dias)
        .group_by(AuditLog.action)
        .all()
    )

    cadastros_recentes = db.query(User).filter(User.created_at >= inicio_30_dias).count()
    geracoes_recentes = db.query(Generation).filter(Generation.deleted_at.is_(None), Generation.created_at >= inicio_7_dias).count()
    uploads_recentes = db.query(Document).filter(Document.deleted_at.is_(None), Document.created_at >= inicio_7_dias).count()

    return {
        "cadastros_30_dias": cadastros_recentes,
        "geracoes_7_dias": geracoes_recentes,
        "uploads_7_dias": uploads_recentes,
        "acoes_auditoria_7_dias": [
            {"acao": action, "total": total}
            for action, total in atividades_recentes
        ],
    }


def listar_usuarios_admin(db: Session) -> list[dict[str, Any]]:
    usuarios = listar_usuarios(db)

    documentos_por_usuario = {
        user_id: total
        for user_id, total in db.query(Document.user_id, func.count(Document.id))
        .filter(Document.deleted_at.is_(None))
        .group_by(Document.user_id)
        .all()
    }
    perfis_por_usuario = {
        user_id: total
        for user_id, total in db.query(WritingProfile.user_id, func.count(WritingProfile.id))
        .filter(WritingProfile.deleted_at.is_(None))
        .group_by(WritingProfile.user_id)
        .all()
    }
    geracoes_por_usuario = {
        user_id: total
        for user_id, total in db.query(Generation.user_id, func.count(Generation.id))
        .filter(Generation.deleted_at.is_(None))
        .group_by(Generation.user_id)
        .all()
    }
    auditorias_por_usuario = {
        user_id: total
        for user_id, total in db.query(AuditLog.user_id, func.count(AuditLog.id)).group_by(AuditLog.user_id).all()
    }

    usuarios_resumo: list[dict[str, Any]] = []
    for usuario in usuarios:
        plano = obter_plano_usuario(usuario)
        usuarios_resumo.append(
            {
                "id": usuario.id,
                "full_name": usuario.full_name,
                "email": usuario.email,
                "is_active": bool(usuario.is_active),
                "is_admin": bool(usuario.is_admin),
                "plan_slug": plano.slug,
                "plan_name": plano.name,
                "created_at": usuario.created_at,
                "documentos": int(documentos_por_usuario.get(usuario.id, 0) or 0),
                "perfis": int(perfis_por_usuario.get(usuario.id, 0) or 0),
                "geracoes": int(geracoes_por_usuario.get(usuario.id, 0) or 0),
                "auditorias": int(auditorias_por_usuario.get(usuario.id, 0) or 0),
            }
        )

    return usuarios_resumo


def obter_uso_geral_sistema(db: Session) -> dict[str, Any]:
    usuarios = listar_usuarios_admin(db)
    recentes = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(12)
        .all()
    )

    entidades = Counter()
    for evento in recentes:
        entidades[evento.entity_type or "desconhecido"] += 1

    return {
        "usuarios": usuarios,
        "eventos_recentes": recentes,
        "resumo_entidades": [{"entidade": chave, "total": total} for chave, total in entidades.most_common()],
    }


def listar_registros_problematicos(db: Session) -> dict[str, list[dict[str, Any]]]:
    documentos_problematicos: list[dict[str, Any]] = []
    for documento in db.query(Document).filter(Document.deleted_at.is_(None)).order_by(Document.created_at.desc(), Document.id.desc()).all():
        problemas: list[str] = []
        if documento.user_id is None:
            problemas.append("Sem usuário vinculado")
        caminho_texto = (documento.file_path or "").strip()
        caminho = Path(caminho_texto) if caminho_texto else None
        if not caminho_texto:
            problemas.append("Caminho do arquivo não informado")
        elif caminho is not None and not caminho.exists():
            problemas.append("Arquivo ausente no armazenamento")
        if problemas:
            documentos_problematicos.append(
                {
                    "id": documento.id,
                    "label": documento.original_filename,
                    "user_id": documento.user_id,
                    "created_at": documento.created_at,
                    "problemas": problemas,
                    "entity_type": "document",
                }
            )

    perfis_problematicos = [
        {
            "id": perfil.id,
            "label": perfil.profile_name,
            "user_id": perfil.user_id,
            "created_at": perfil.created_at,
            "problemas": ["Sem usuário vinculado"],
            "entity_type": "writing_profile",
        }
        for perfil in db.query(WritingProfile)
        .filter(WritingProfile.user_id.is_(None), WritingProfile.deleted_at.is_(None))
        .all()
    ]

    geracoes_problematicas = [
        {
            "id": geracao.id,
            "label": f"{geracao.document_type} - {geracao.client_name}",
            "user_id": geracao.user_id,
            "created_at": geracao.created_at,
            "problemas": ["Sem usuário vinculado"],
            "entity_type": "generation",
        }
        for geracao in db.query(Generation)
        .filter(Generation.user_id.is_(None), Generation.deleted_at.is_(None))
        .all()
    ]

    auditorias_problematicas = [
        {
            "id": evento.id,
            "label": f"{evento.entity_type} #{evento.entity_id} - {evento.action}",
            "user_id": evento.user_id,
            "created_at": evento.created_at,
            "problemas": ["Sem usuário vinculado"],
            "entity_type": "audit_log",
        }
        for evento in db.query(AuditLog)
        .filter(AuditLog.user_id.is_(None), AuditLog.entity_type != "auth")
        .all()
    ]

    return {
        "documents": documentos_problematicos,
        "writing_profiles": perfis_problematicos,
        "generations": geracoes_problematicas,
        "audit_logs": auditorias_problematicas,
    }


def alternar_status_usuario_admin(db: Session, *, admin_atual: User, user_id: int) -> tuple[bool, str]:
    usuario = buscar_usuario_por_id(db, user_id)
    if not usuario:
        return False, "Usuário não encontrado."
    if usuario.id == admin_atual.id and bool(usuario.is_active):
        return False, "Você não pode desativar a própria conta administradora."

    usuario = atualizar_status_usuario(db, usuario, is_active=not bool(usuario.is_active))
    registrar_acao_usuario(
        db,
        action="admin_toggle_user_active",
        usuario=admin_atual,
        metadata={
            "target_user_id": usuario.id,
            "target_user_email": usuario.email,
            "target_is_active": bool(usuario.is_active),
        },
    )
    mensagem = "Usuário ativado com sucesso." if usuario.is_active else "Usuário desativado com sucesso."
    return True, mensagem


def alternar_admin_usuario(db: Session, *, admin_atual: User, user_id: int) -> tuple[bool, str]:
    usuario = buscar_usuario_por_id(db, user_id)
    if not usuario:
        return False, "Usuário não encontrado."
    if usuario.id == admin_atual.id and bool(usuario.is_admin):
        return False, "Você não pode remover seu próprio acesso administrativo."

    usuario = atualizar_status_usuario(db, usuario, is_admin=not bool(usuario.is_admin))
    registrar_acao_usuario(
        db,
        action="admin_toggle_user_admin",
        usuario=admin_atual,
        metadata={
            "target_user_id": usuario.id,
            "target_user_email": usuario.email,
            "target_is_admin": bool(usuario.is_admin),
        },
    )
    mensagem = "Permissão administrativa concedida com sucesso." if usuario.is_admin else "Permissão administrativa removida com sucesso."
    return True, mensagem


def remover_registro_problematico(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    admin_atual: User | None = None,
) -> tuple[bool, str]:
    mapa = {
        "document": Document,
        "writing_profile": WritingProfile,
        "generation": Generation,
        "audit_log": AuditLog,
    }
    modelo = mapa.get(entity_type)
    if not modelo:
        return False, "Tipo de registro inválido."

    registro = db.query(modelo).filter(modelo.id == entity_id).first()
    if not registro:
        return False, "Registro não encontrado."

    if admin_atual is not None:
        registrar_acao_usuario(
            db,
            action="admin_delete_problem_record",
            usuario=admin_atual,
            metadata={
                "target_entity_type": entity_type,
                "target_entity_id": entity_id,
            },
            commit=False,
        )

    db.delete(registro)
    db.commit()
    return True, "Registro problemático removido com sucesso."
