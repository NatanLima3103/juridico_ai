from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE


@dataclass(slots=True)
class TextChunk:
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict = field(default_factory=dict)


def _normalizar_texto(texto: str | None) -> str:
    return " ".join(str(texto or "").replace("\x00", " ").split())


def _validar_parametros(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero.")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap nao pode ser negativo.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap deve ser menor que chunk_size.")


def split_text(
    texto: str | None,
    *,
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> list[TextChunk]:
    _validar_parametros(chunk_size, chunk_overlap)

    texto_normalizado = _normalizar_texto(texto)
    if not texto_normalizado:
        return []

    chunks: list[TextChunk] = []
    inicio = 0
    indice = 0
    tamanho_texto = len(texto_normalizado)

    while inicio < tamanho_texto:
        fim_limite = min(inicio + chunk_size, tamanho_texto)
        fim = fim_limite

        if fim_limite < tamanho_texto:
            ultimo_espaco = texto_normalizado.rfind(" ", inicio, fim_limite)
            if ultimo_espaco > inicio:
                fim = ultimo_espaco

        conteudo = texto_normalizado[inicio:fim].strip()
        if conteudo:
            chunks.append(
                TextChunk(
                    text=conteudo,
                    chunk_index=indice,
                    start_char=inicio,
                    end_char=fim,
                    metadata={
                        "chunk_size": len(conteudo),
                        "chunk_overlap": chunk_overlap,
                    },
                )
            )
            indice += 1

        if fim >= tamanho_texto:
            break

        proximo_inicio = max(fim - chunk_overlap, 0)
        if proximo_inicio <= inicio:
            proximo_inicio = fim
        inicio = proximo_inicio

    return chunks
