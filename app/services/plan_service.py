from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from sqlalchemy.orm import Session

from app.core.config import (
    FREE_PLAN_DAILY_GENERATION_LIMIT,
    FREE_PLAN_WRITING_PROFILE_LIMIT,
    PRO_PLAN_MONTHLY_GENERATION_LIMIT,
    PRO_PLAN_WRITING_PROFILE_LIMIT,
)
from app.models.generation import Generation
from app.models.user import User
from app.models.writing_profile import WritingProfile


FREE_PLAN_SLUG = "free"
PRO_PLAN_SLUG = "pro"


@dataclass(frozen=True, slots=True)
class PremiumResource:
    slug: str
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    slug: str
    name: str
    monthly_generation_limit: int
    writing_profile_limit: int
    description: str
    generation_limit_period: str = "monthly"
    premium_resources: tuple[PremiumResource, ...] = ()

    @property
    def generation_usage_label(self) -> str:
        if self.generation_limit_period == "daily":
            return "hoje"
        return "neste mês"

    @property
    def generation_limit_label(self) -> str:
        if self.generation_limit_period == "daily":
            return "diário"
        return "mensal"

    @property
    def generation_reset_label(self) -> str:
        if self.generation_limit_period == "daily":
            return "amanhã"
        return "no início do próximo mês"


@dataclass(frozen=True, slots=True)
class PlanUsage:
    plan: PlanDefinition
    used_generations: int
    remaining_generations: int
    can_create_generation: bool
    used_writing_profiles: int
    remaining_writing_profiles: int
    can_create_writing_profile: bool
    reset_label: str
    upgrade_plan: PlanDefinition | None


PRO_PREMIUM_RESOURCES = (
    PremiumResource(
        slug="monthly_generation_limit",
        title=f"{PRO_PLAN_MONTHLY_GENERATION_LIMIT} gerações mensais",
        description="Limite ampliado para manter a produção jurídica recorrente dentro do mesmo ciclo mensal.",
    ),
    PremiumResource(
        slug="writing_profile_limit",
        title=f"{PRO_PLAN_WRITING_PROFILE_LIMIT} perfis de escrita",
        description="Mais espaço para estilos por área, advogado, cliente ou tipo de peça.",
    ),
)


FREE_PLAN = PlanDefinition(
    slug=FREE_PLAN_SLUG,
    name="Plano gratuito",
    monthly_generation_limit=FREE_PLAN_DAILY_GENERATION_LIMIT,
    writing_profile_limit=FREE_PLAN_WRITING_PROFILE_LIMIT,
    description="Inclui gerações diárias limitadas para validar o produto antes de contratar um plano pago.",
    generation_limit_period="daily",
)

PRO_PLAN = PlanDefinition(
    slug=PRO_PLAN_SLUG,
    name="Plano Pro",
    monthly_generation_limit=PRO_PLAN_MONTHLY_GENERATION_LIMIT,
    writing_profile_limit=PRO_PLAN_WRITING_PROFILE_LIMIT,
    description="Plano pago para uso recorrente, com recursos premium e limites ampliados.",
    premium_resources=PRO_PREMIUM_RESOURCES,
)

PLAN_DEFINITIONS = {
    FREE_PLAN.slug: FREE_PLAN,
    PRO_PLAN.slug: PRO_PLAN,
}


def agora_brasil() -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("América/Sao_Paulo")).replace(tzinfo=None)
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


def _intervalo_dia_atual(referencia: datetime | None = None) -> tuple[datetime, datetime]:
    referencia = referencia or agora_brasil()
    inicio = referencia.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = inicio + timedelta(days=1)

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
        .filter(Generation.deleted_at.is_(None))
        .filter(Generation.created_at >= inicio)
        .filter(Generation.created_at < fim)
        .count()
    )


def contar_geracoes_usuario_no_dia(
    db: Session,
    user_id: int,
    *,
    referencia: datetime | None = None,
) -> int:
    inicio, fim = _intervalo_dia_atual(referencia)
    return (
        db.query(Generation)
        .filter(Generation.user_id == user_id)
        .filter(Generation.deleted_at.is_(None))
        .filter(Generation.created_at >= inicio)
        .filter(Generation.created_at < fim)
        .count()
    )


def contar_perfis_escrita_usuario(db: Session, user_id: int) -> int:
    return (
        db.query(WritingProfile)
        .filter(WritingProfile.user_id == user_id, WritingProfile.deleted_at.is_(None))
        .count()
    )


def obter_uso_plano_usuario(
    db: Session,
    usuario: User,
    *,
    referencia: datetime | None = None,
) -> PlanUsage:
    plano = obter_plano_usuario(usuario)
    if plano.generation_limit_period == "daily":
        usadas = contar_geracoes_usuario_no_dia(db, usuario.id, referencia=referencia)
    else:
        usadas = contar_geracoes_usuario_no_mes(db, usuario.id, referencia=referencia)

    perfis_usados = contar_perfis_escrita_usuario(db, usuario.id)
    restantes = max(plano.monthly_generation_limit - usadas, 0)
    perfis_restantes = max(plano.writing_profile_limit - perfis_usados, 0)

    return PlanUsage(
        plan=plano,
        used_generations=usadas,
        remaining_generations=restantes,
        can_create_generation=usadas < plano.monthly_generation_limit,
        used_writing_profiles=perfis_usados,
        remaining_writing_profiles=perfis_restantes,
        can_create_writing_profile=perfis_usados < plano.writing_profile_limit,
        reset_label=plano.generation_reset_label,
        upgrade_plan=PRO_PLAN if plano.slug != PRO_PLAN_SLUG else None,
    )


def montar_mensagem_limite_plano(usage: PlanUsage) -> str:
    return (
        f"Voce atingiu o limite do {usage.plan.name}: "
        f"{usage.used_generations}/{usage.plan.monthly_generation_limit} gerações {usage.plan.generation_usage_label}. "
        f"O limite reinicia {usage.reset_label}."
    )


def montar_mensagem_limite_perfis(usage: PlanUsage) -> str:
    return (
        f"Voce atingiu o limite do {usage.plan.name}: "
        f"{usage.used_writing_profiles}/{usage.plan.writing_profile_limit} perfis de escrita cadastrados. "
        "Exclua um perfil existente ou migre para um plano com limite maior."
    )


def validar_criacao_geracao_por_plano(
    db: Session,
    usuario: User,
    *,
    referencia: datetime | None = None,
) -> tuple[bool, PlanUsage, str | None]:
    usage = obter_uso_plano_usuario(db, usuario, referencia=referencia)
    if usage.can_create_generation:
        return True, usage, None
    return False, usage, montar_mensagem_limite_plano(usage)


def validar_criacao_perfil_por_plano(db: Session, usuario: User) -> tuple[bool, PlanUsage, str | None]:
    usage = obter_uso_plano_usuario(db, usuario)
    if usage.can_create_writing_profile:
        return True, usage, None
    return False, usage, montar_mensagem_limite_perfis(usage)


def listar_planos_disponiveis() -> list[PlanDefinition]:
    return [FREE_PLAN, PRO_PLAN]


def listar_recursos_premium() -> tuple[PremiumResource, ...]:
    return PRO_PLAN.premium_resources
