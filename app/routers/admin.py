from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_admin_user
from app.models.user import User
from app.routers.common import templates
from app.services.admin_service import (
    alternar_admin_usuario,
    alternar_status_usuario_admin,
    listar_registros_problematicos,
    listar_usuarios_admin,
    obter_metricas_basicas_admin,
    obter_resumo_lgpd_admin,
    obter_resumo_retencao_admin,
    obter_totais_sistema,
    obter_uso_geral_sistema,
    remover_registro_problematico,
)
from app.services.audit_service import registrar_acao_usuario
from app.services.lgpd_service import anonimizar_titular_lgpd, exportar_dados_titular_lgpd
from app.services.retention_service import aplicar_politica_retencao

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_admin_user)],
)


@router.get("")
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    totais = obter_totais_sistema(db)
    metricas = obter_metricas_basicas_admin(db)
    uso_geral = obter_uso_geral_sistema(db)
    problematicos = listar_registros_problematicos(db)
    retencao = obter_resumo_retencao_admin(db)
    lgpd = obter_resumo_lgpd_admin(db)

    totais_problematicos = sum(len(itens) for itens in problematicos.values())

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "title": "Administração do sistema",
            "admin": admin,
            "totais": totais,
            "metricas": metricas,
            "uso_geral": uso_geral,
            "problematicos": problematicos,
            "totais_problematicos": totais_problematicos,
            "retencao": retencao,
            "lgpd": lgpd,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.get("/users")
def admin_users(
    request: Request,
    db: Session = Depends(get_db),
):
    usuarios = listar_usuarios_admin(db)
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "title": "Usuários do sistema",
            "usuarios": usuarios,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.post("/users/{user_id}/toggle-active")
def admin_toggle_user_active(
    user_id: int = Path(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sucesso, mensagem = alternar_status_usuario_admin(db, admin_atual=admin, user_id=user_id)
    destino = "/admin/users"
    parametro = "sucesso" if sucesso else "erro"
    return RedirectResponse(
        url=f"{destino}?{parametro}={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/users/{user_id}/toggle-admin")
def admin_toggle_user_admin(
    user_id: int = Path(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sucesso, mensagem = alternar_admin_usuario(db, admin_atual=admin, user_id=user_id)
    destino = "/admin/users"
    parametro = "sucesso" if sucesso else "erro"
    return RedirectResponse(
        url=f"{destino}?{parametro}={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/users/{user_id}/lgpd-export")
def admin_export_user_lgpd(
    user_id: int = Path(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    payload = exportar_dados_titular_lgpd(db, user_id)
    if payload is None:
        return RedirectResponse(
            url=f"/admin/users?erro={quote('Usuario nao encontrado.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    registrar_acao_usuario(
        db,
        action="admin_lgpd_export_user",
        usuario=admin,
        metadata={"target_user_id": user_id},
    )
    return JSONResponse(payload)


@router.post("/users/{user_id}/lgpd-anonymize")
def admin_anonymize_user_lgpd(
    user_id: int = Path(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sucesso, mensagem, relatorio = anonimizar_titular_lgpd(
        db,
        user_id=user_id,
        admin_atual=admin,
    )
    parametro = "sucesso" if sucesso else "erro"
    if relatorio is not None:
        mensagem = (
            f"{mensagem} Registros tratados: {relatorio.total_records}; "
            f"arquivos removidos: {relatorio.files_deleted}."
        )
    return RedirectResponse(
        url=f"/admin/users?{parametro}={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/problem-records/{entity_type}/{entity_id}/delete")
def admin_delete_problem_record(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sucesso, mensagem = remover_registro_problematico(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        admin_atual=admin,
    )
    parametro = "sucesso" if sucesso else "erro"
    return RedirectResponse(
        url=f"/admin?{parametro}={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/retention/apply")
def admin_apply_retention_policy(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    relatorio = aplicar_politica_retencao(db, admin_atual=admin)
    mensagem = (
        "Política de retenção aplicada: "
        f"{relatorio.total_records} registros removidos e "
        f"{relatorio.files_deleted} arquivo(s) físico(s) apagado(s)."
    )
    return RedirectResponse(
        url=f"/admin?sucesso={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
