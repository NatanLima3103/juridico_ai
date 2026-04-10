from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from sqlalchemy.orm import Session

from app.core.config import FREE_PLAN_MONTHLY_GENERATION_LIMIT, PRO_PLAN_MONTHLY_GENERATION_LIMIT
from app.models.generation import Generation
from app.models.user import User


FREE_PLAN_SLUG = "free"
PRO_PLAN_SLUG = "pro"


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    slug: str
    name: str
    monthly_generation_limit: int
    description: str


@dataclass(frozen=True, slots=True)
class PlanUsage:
    plan: PlanDefinition
    used_generations: int
    remaining_generations: int
    can_create_generation: bool
    reset_label: str


FREE_PLAN = PlanDefinition(
    slug=FREE_PLAN_SLUG,
    name="Plano gratuito",
    monthly_generation_limit=FREE_PLAN_MONTHLY_GENERATION_LIMIT,
    description="Inclui geracoes mensais limitadas para validar o produto antes de contratar um plano pago.",
)

PRO_PLAN = PlanDefinition(
    slug=PRO_PLAN_SLUG,
    name="Plano Pro",
    monthly_generation_limit=PRO_PLAN_MONTHLY_GENERATION_LIMIT,
    description="Plano pago para uso recorrente, com limite mensal ampliado de geracoes juridicas.",
)

PLAN_DEFINITIONS = {
    FREE_PLAN.slug: FREE_PLAN,
    PRO_PLAN.slug: PRO_PLAN,
}


def agora_brasil() -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        except ZoneInfoNotFoundError:
            pass
        except Exception:
            pass

    return datetime.now()


def obter_plano_usuario(usuario: User) -> PlanDefinition:
    plan_slug = (getattr(usuario, "plan_slug", "") or FREE_PLAN_SLUG).strip().lower()
    return PLAN_DEFINITIONS.get(plan_slug, FREE_PLAN)


def _intervalo_mes_atual(referencia: datetime | None = None) -> tuple[datetime, datetime]:
    referencia = referencia or agora_brasil()
    inicio = referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if inicio.month == 12:
        fim = inicio.replace(year=inicio.year + 1, month=1)
    else:
        fim = inicio.replace(month=inicio.month + 1)

    return inicio, fim


def contar_geracoes_usuario_no_mes(
    db: Session,
    user_id: int,
    *,
    referencia: datetime | None = None,
) -> int:
    inicio, fim = _intervalo_mes_atual(referencia)
    return (
        db.query(Generation)
        .filter(Generation.user_id == user_id)
        .filter(Generation.created_at >= inicio)
        .filter(Generation.created_at < fim)
        .count()
    )


def obter_uso_plano_usuario(
    db: Session,
    usuario: User,
    *,
    referencia: datetime | None = None,
) -> PlanUsage:
    plano = obter_plano_usuario(usuario)
    usadas = contar_geracoes_usuario_no_mes(db, usuario.id, referencia=referencia)
    restantes = max(plano.monthly_generation_limit - usadas, 0)

    return PlanUsage(
        plan=plano,
        used_generations=usadas,
        remaining_generations=restantes,
        can_create_generation=usadas < plano.monthly_generation_limit,
        reset_label="no inicio do proximo mes",
    )


def montar_mensagem_limite_plano(usage: PlanUsage) -> str:
    return (
        f"Voce atingiu o limite do {usage.plan.name}: "
        f"{usage.used_generations}/{usage.plan.monthly_generation_limit} geracoes neste mes. "
        f"O limite reinicia {usage.reset_label}."
    )


def listar_planos_disponiveis() -> list[PlanDefinition]:
    return [FREE_PLAN, PRO_PLAN]
