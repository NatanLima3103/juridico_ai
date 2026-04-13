from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import PAYMENT_CANCEL_URL, PAYMENT_SUCCESS_URL
from app.database import get_db
from app.dependencies.auth import get_authenticated_user
from app.models.user import User
from app.routers.common import templates
from app.services.audit_service import registrar_acao_usuario
from app.services.payment_service import (
    PaymentIntegrationUnavailable,
    iniciar_checkout_plano,
    pagamento_configurado,
)
from app.services.plan_service import listar_planos_disponiveis, obter_uso_plano_usuario

router = APIRouter(
    prefix="/plans",
    tags=["plans"],
    dependencies=[Depends(get_authenticated_user)],
)


def _render_plans_page(
    request: Request,
    db: Session,
    usuario: User,
    *,
    erro: str | None = None,
    sucesso: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    plan_usage = obter_uso_plano_usuario(db, usuario)

    return templates.TemplateResponse(
        "plans.html",
        {
            "request": request,
            "title": "Planos",
            "plan_usage": plan_usage,
            "planos": listar_planos_disponiveis(),
            "pagamento_configurado": pagamento_configurado(),
            "erro": erro,
            "sucesso": sucesso,
        },
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
def plans_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    return _render_plans_page(request, db, usuario)


@router.post("/checkout", response_class=HTMLResponse)
def checkout_plan(
    request: Request,
    plan_slug: str = Form(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    success_url = PAYMENT_SUCCESS_URL or str(request.url_for("payment_success"))
    cancel_url = PAYMENT_CANCEL_URL or str(request.url_for("payment_cancel"))

    try:
        checkout = iniciar_checkout_plano(
            usuario=usuario,
            plan_slug=plan_slug,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except PaymentIntegrationUnavailable as exc:
        registrar_acao_usuario(
            db,
            action="plan_checkout_failed",
            usuario=usuario,
            request=request,
            metadata={"plan_slug": plan_slug, "reason": "payment_unavailable"},
        )
        return _render_plans_page(
            request,
            db,
            usuario,
            erro=str(exc),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except ValueError as exc:
        registrar_acao_usuario(
            db,
            action="plan_checkout_failed",
            usuario=usuario,
            request=request,
            metadata={"plan_slug": plan_slug, "reason": str(exc)},
        )
        return _render_plans_page(
            request,
            db,
            usuario,
            erro=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    registrar_acao_usuario(
        db,
        action="plan_checkout_started",
        usuario=usuario,
        request=request,
        metadata={"plan_slug": checkout.plan.slug, "provider": checkout.provider},
    )

    return RedirectResponse(checkout.redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/payment/success", response_class=HTMLResponse, name="payment_success")
def payment_success(
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    registrar_acao_usuario(
        db,
        action="plan_payment_success_return",
        usuario=usuario,
        request=request,
    )
    return _render_plans_page(
        request,
        db,
        usuario,
        sucesso="Pagamento recebido. A confirmacao do provedor atualizara seu plano em seguida.",
    )


@router.get("/payment/cancel", response_class=HTMLResponse, name="payment_cancel")
def payment_cancel(
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    registrar_acao_usuario(
        db,
        action="plan_payment_cancel_return",
        usuario=usuario,
        request=request,
    )
    return _render_plans_page(
        request,
        db,
        usuario,
        erro="Pagamento cancelado. Seu plano atual permanece ativo.",
    )
