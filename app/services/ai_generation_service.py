from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
)
from app.services.llm_service import LLMServiceError, gerar_texto_juridico_com_fallback


@dataclass
class AIGenerationResult:
    text: str
    generation_strategy: str
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_response_id: str | None = None
    llm_error: str | None = None


def openai_disponivel() -> bool:
    return bool(OPENAI_API_KEY)


def _normalizar_texto_saida(texto: str | None) -> str:
    return str(texto or "").strip()


def _montar_parametros_openai(prompt_payload: dict) -> dict:
    parametros: dict = {
        "model": OPENAI_MODEL,
        "instructions": str(prompt_payload.get("system_prompt") or "").strip(),
        "input": str(prompt_payload.get("user_prompt") or "").strip(),
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
    }

    if OPENAI_REASONING_EFFORT:
        parametros["reasoning"] = {"effort": OPENAI_REASONING_EFFORT}

    return parametros


def _gerar_texto_com_openai(prompt_payload: dict) -> AIGenerationResult:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMServiceError(
            "SDK da OpenAI nao esta instalado. Adicione 'openai' as dependencias do projeto."
        ) from exc

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.responses.create(**_montar_parametros_openai(prompt_payload))
    except Exception as exc:
        raise LLMServiceError(f"Falha ao chamar a API da OpenAI: {exc}") from exc

    texto = _normalizar_texto_saida(getattr(response, "output_text", None))
    if not texto:
        raise LLMServiceError("A OpenAI respondeu sem texto utilizavel para a minuta.")

    return AIGenerationResult(
        text=texto,
        generation_strategy="ai_openai",
        llm_provider="openai",
        llm_model=OPENAI_MODEL,
        llm_response_id=str(getattr(response, "id", "") or "").strip() or None,
        llm_error=None,
    )


def gerar_resultado_juridico_com_fallback(
    *,
    prompt_payload: dict,
    fallback_generator: Callable[[], str],
) -> AIGenerationResult:
    fallback_text = _normalizar_texto_saida(
        gerar_texto_juridico_com_fallback(
            prompt_payload={"system_prompt": "", "user_prompt": ""},
            fallback_generator=fallback_generator,
        )
    )

    if not openai_disponivel():
        return AIGenerationResult(
            text=fallback_text,
            generation_strategy="rule_based",
            llm_error="OPENAI_API_KEY nao configurada.",
        )

    if not isinstance(prompt_payload, dict):
        raise LLMServiceError("Payload de prompt invalido para a camada de IA.")

    try:
        return _gerar_texto_com_openai(prompt_payload)
    except LLMServiceError as exc:
        return AIGenerationResult(
            text=fallback_text,
            generation_strategy="rule_based",
            llm_provider="openai",
            llm_model=OPENAI_MODEL,
            llm_error=str(exc),
        )
