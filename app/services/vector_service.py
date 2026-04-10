from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass(slots=True)
class VectorEntry:
    id: str
    vector: list[float]
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class VectorSearchResult:
    entry: VectorEntry
    score: float


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0

    numerador = sum(valor_a * valor_b for valor_a, valor_b in zip(vector_a, vector_b))
    norma_a = math.sqrt(sum(valor * valor for valor in vector_a))
    norma_b = math.sqrt(sum(valor * valor for valor in vector_b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return numerador / (norma_a * norma_b)


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self._entries: list[VectorEntry] = []

    def clear(self) -> None:
        self._entries.clear()

    def add(self, entry: VectorEntry) -> None:
        self._entries.append(entry)

    def extend(self, entries: list[VectorEntry]) -> None:
        self._entries.extend(entries)

    def count(self) -> int:
        return len(self._entries)

    def search(self, query_vector: list[float], *, top_k: int = 4, min_score: float = 0.0) -> list[VectorSearchResult]:
        resultados: list[VectorSearchResult] = []
        for entry in self._entries:
            score = cosine_similarity(query_vector, entry.vector)
            if score >= min_score:
                resultados.append(VectorSearchResult(entry=entry, score=score))

        resultados.sort(key=lambda item: item.score, reverse=True)
        return resultados[: max(top_k, 0)]
