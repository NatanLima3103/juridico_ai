from __future__ import annotations

from typing import Callable


class LLMServiceError(Exception):
    pass


def gerar_texto_juridico_com_fallback(
    *,
    prompt_payload: dict,
    fallback_generator: Callable[[], str],
) -> str:
    """
    Camada preparada para futura integração com IA real.

    Hoje, o projeto ainda usa a geração local como fallback principal.
    Quando a integração com um provedor real for adicionada, a troca deverá
    acontecer aqui, preservando o restante do fluxo da aplicação.
    """
    if not isinstance(prompt_payload, dict):
        raise LLMServiceError("Payload de prompt inválido para a camada de IA.")

    fallback_text = fallback_generator()

    if not fallback_text or not str(fallback_text).strip():
        raise LLMServiceError("A geração fallback retornou texto vazio.")

    return str(fallback_text).strip()