from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from app.core import config
from app.models.user import User
from app.services.plan_service import PLAN_DEFINITIONS, PRO_PLAN_SLUG, PlanDefinition, obter_plano_usuario


class PaymentIntegrationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PaymentCheckout:
    provider: str
    plan: PlanDefinition
    redirect_url: str


def pagamento_configurado() -> bool:
    return bool(config.PAYMENT_CHECKOUT_URL)


def _montar_checkout_url(
    *,
    plano: PlanDefinition,
    usuario: User,
    success_url: str,
    cancel_url: str,
) -> str:
    parametros = {
        "plan_slug": plano.slug,
        "user_id": str(usuario.id),
        "email": usuario.email,
        "success_url": success_url,
        "cancel_url": cancel_url,
    }

    checkout_url = config.PAYMENT_CHECKOUT_URL
    if "{" in checkout_url and "}" in checkout_url:
        return checkout_url.format(**parametros)

    separador = "&" if "?" in checkout_url else "?"
    return f"{checkout_url}{separador}{urlencode(parametros)}"


def iniciar_checkout_plano(
    *,
    usuario: User,
    plan_slug: str,
    success_url: str,
    cancel_url: str,
) -> PaymentCheckout:
    plan_slug = (plan_slug or "").strip().lower()
    plano = PLAN_DEFINITIONS.get(plan_slug)

    if not plano or plano.slug != PRO_PLAN_SLUG:
        raise ValueError("Selecione um plano pago disponivel para continuar.")

    plano_atual = obter_plano_usuario(usuario)
    if plano_atual.slug == plano.slug:
        raise ValueError("Este plano ja esta ativo na sua conta.")

    if not pagamento_configurado():
        raise PaymentIntegrationUnavailable(
            "Checkout de pagamento ainda nao configurado. Defina PAYMENT_CHECKOUT_URL para ativar a integracao."
        )

    return PaymentCheckout(
        provider=config.PAYMENT_PROVIDER,
        plan=plano,
        redirect_url=_montar_checkout_url(
            plano=plano,
            usuario=usuario,
            success_url=success_url,
            cancel_url=cancel_url,
        ),
    )
