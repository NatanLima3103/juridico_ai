from __future__ import annotations

from hashlib import sha256
import math
import re

from app.core.config import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, RAG_VECTOR_DIMENSION


class EmbeddingServiceError(Exception):
    pass


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def _tokenizar(texto: str | None) -> list[str]:
    return TOKEN_PATTERN.findall(str(texto or "").lower())


def _normalizar_vetor(vetor: list[float]) -> list[float]:
    norma = math.sqrt(sum(valor * valor for valor in vetor))
    if norma == 0:
        return vetor
    return [valor / norma for valor in vetor]


def gerar_embedding_local(texto: str | None, *, dimensions: int = RAG_VECTOR_DIMENSION) -> list[float]:
    if dimensions <= 0:
        raise EmbeddingServiceError("dimensions deve ser maior que zero.")

    vetor = [0.0] * dimensions
    for token in _tokenizar(texto):
        digest = sha256(token.encode("utf-8")).digest()
        indice_1 = digest[0] % dimensions
        indice_2 = digest[1] % dimensions
        indice_3 = digest[2] % dimensions
        peso_1 = 1.0 + (digest[3] / 255.0)
        peso_2 = 0.75 + (digest[4] / 255.0)
        peso_3 = 0.5 + (digest[5] / 255.0)

        vetor[indice_1] += peso_1
        vetor[indice_2] += peso_2
        vetor[indice_3] += peso_3

    return _normalizar_vetor(vetor)


def _gerar_embeddings_openai(textos: list[str]) -> list[list[float]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise EmbeddingServiceError(
            "SDK da OpenAI nao esta instalado. Adicione 'openai' as dependencias do projeto."
        ) from exc

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=textos)
    except Exception as exc:
        raise EmbeddingServiceError(f"Falha ao gerar embeddings com OpenAI: {exc}") from exc

    data = getattr(response, "data", None) or []
    embeddings = [list(item.embedding) for item in data if getattr(item, "embedding", None) is not None]
    if len(embeddings) != len(textos):
        raise EmbeddingServiceError("Quantidade de embeddings retornada difere da quantidade solicitada.")
    return embeddings


def gerar_embeddings(
    textos: list[str],
    *,
    provider: str = "auto",
    dimensions: int = RAG_VECTOR_DIMENSION,
) -> list[list[float]]:
    textos_normalizados = [str(texto or "").strip() for texto in textos]
    if not textos_normalizados:
        return []

    usar_openai = provider in {"auto", "openai"} and bool(OPENAI_API_KEY)
    if usar_openai:
        try:
            return _gerar_embeddings_openai(textos_normalizados)
        except EmbeddingServiceError:
            if provider == "openai":
                raise

    return [gerar_embedding_local(texto, dimensions=dimensions) for texto in textos_normalizados]


def gerar_embedding(texto: str, *, provider: str = "auto", dimensions: int = RAG_VECTOR_DIMENSION) -> list[float]:
    embeddings = gerar_embeddings([texto], provider=provider, dimensions=dimensions)
    return embeddings[0] if embeddings else []
