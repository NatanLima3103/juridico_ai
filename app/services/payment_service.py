from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core import config
from app.models.user import User
from app.services.plan_service import (
    FREE_PLAN_SLUG,
    PLAN_DEFINITIONS,
    PRO_PLAN_SLUG,
    PlanDefinition,
    obter_plano_usuario,
)


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


# --- Confirmacao do provedor (webhook) ---------------------------------------
#
# Contrato generico enquanto nenhum provedor especifico esta integrado:
#   POST /plans/payment/webhook
#   X-Payment-Timestamp: <unix timestamp em segundos>
#   X-Payment-Signature: sha256=<HMAC-SHA256 de "<timestamp>.<corpo bruto>" com PAYMENT_WEBHOOK_SECRET>
#   {"event_id": "...", "event": "subscription.activated" | "subscription.canceled",
#    "user_id": 123, "plan_slug": "pro"}

WEBHOOK_TOLERANCE_SECONDS = 5 * 60
WEBHOOK_EVENT_ACTIVATED = "subscription.activated"
WEBHOOK_EVENT_CANCELED = "subscription.canceled"


class PaymentWebhookError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class PaymentWebhookEvent:
    event_id: str
    event: str
    user_id: int
    plan_slug: str


def webhook_configurado() -> bool:
    return bool(config.PAYMENT_WEBHOOK_SECRET)


def assinar_webhook(timestamp: str, body: bytes, secret: str | None = None) -> str:
    chave = (secret if secret is not None else config.PAYMENT_WEBHOOK_SECRET).encode("utf-8")
    mensagem = timestamp.encode("utf-8") + b"." + body
    return "sha256=" + hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def validar_webhook(
    *,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    agora: float | None = None,
) -> PaymentWebhookEvent:
    if not webhook_configurado():
        raise PaymentWebhookError("Webhook de pagamento nao configurado.", status_code=503)

    if not timestamp or not signature:
        raise PaymentWebhookError("Assinatura ausente.", status_code=401)

    try:
        momento = int(timestamp)
    except ValueError as exc:
        raise PaymentWebhookError("Timestamp invalido.", status_code=401) from exc

    agora = time.time() if agora is None else agora
    if abs(agora - momento) > WEBHOOK_TOLERANCE_SECONDS:
        # Evita que uma requisicao antiga capturada seja reenviada depois.
        raise PaymentWebhookError("Timestamp fora da janela permitida.", status_code=401)

    if not hmac.compare_digest(assinar_webhook(timestamp, body), signature.strip()):
        raise PaymentWebhookError("Assinatura invalida.", status_code=401)

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PaymentWebhookError("Corpo do webhook nao e um JSON valido.") from exc

    if not isinstance(payload, dict):
        raise PaymentWebhookError("Corpo do webhook deve ser um objeto JSON.")

    event = str(payload.get("event") or "").strip()
    if event not in {WEBHOOK_EVENT_ACTIVATED, WEBHOOK_EVENT_CANCELED}:
        raise PaymentWebhookError("Evento de pagamento desconhecido.")

    user_id = payload.get("user_id")
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise PaymentWebhookError("user_id invalido.")

    plan_slug = str(payload.get("plan_slug") or PRO_PLAN_SLUG).strip().lower()
    plano = PLAN_DEFINITIONS.get(plan_slug)
    if not plano or plano.slug == FREE_PLAN_SLUG:
        raise PaymentWebhookError("plan_slug invalido.")

    return PaymentWebhookEvent(
        event_id=str(payload.get("event_id") or "").strip()[:100],
        event=event,
        user_id=user_id,
        plan_slug=plano.slug,
    )


def aplicar_evento_pagamento(db: Session, evento: PaymentWebhookEvent) -> tuple[User, str, str]:
    """Aplica o evento ao usuario e devolve (usuario, plano_anterior, plano_novo).

    Reenvios do mesmo evento sao inofensivos: o plano final e sempre o mesmo.
    """
    usuario = db.query(User).filter(User.id == evento.user_id).first()
    if not usuario:
        raise PaymentWebhookError("Usuario nao encontrado.", status_code=404)

    plano_anterior = obter_plano_usuario(usuario).slug
    if evento.event == WEBHOOK_EVENT_ACTIVATED:
        plano_novo = evento.plan_slug
    elif plano_anterior == evento.plan_slug:
        plano_novo = FREE_PLAN_SLUG
    else:
        # Cancelamento de um plano que o usuario nem tem mais: nada a fazer.
        plano_novo = plano_anterior

    if plano_novo != plano_anterior:
        usuario.plan_slug = plano_novo
        db.add(usuario)
        db.flush()

    return usuario, plano_anterior, plano_novo
