from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_TOP_K
from app.models.document import Document
from app.services.chunk_service import TextChunk, split_text
from app.services.document_service import listar_documentos
from app.services.embedding_service import gerar_embedding, gerar_embeddings
from app.services.vector_service import InMemoryVectorIndex, VectorEntry


@dataclass(slots=True)
class RAGSearchHit:
    document_id: int
    document_name: str
    chunk_index: int
    score: float
    text: str
    metadata: dict


class RAGService:
    def __init__(self, *, vector_index: InMemoryVectorIndex | None = None) -> None:
        self.vector_index = vector_index or InMemoryVectorIndex()

    def reset(self) -> None:
        self.vector_index.clear()

    def index_document(
        self,
        document: Document,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        provider: str = "auto",
    ) -> int:
        chunks = self._chunks_do_documento(
            document,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not chunks:
            return 0

        embeddings = gerar_embeddings([chunk.text for chunk in chunks], provider=provider)
        entries: list[VectorEntry] = []
        for chunk, embedding in zip(chunks, embeddings):
            entries.append(
                VectorEntry(
                    id=f"doc:{document.id}:chunk:{chunk.chunk_index}",
                    vector=embedding,
                    text=chunk.text,
                    metadata={
                        "document_id": document.id,
                        "document_name": document.original_filename,
                        "chunk_index": chunk.chunk_index,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                        "user_id": document.user_id,
                    },
                )
            )

        self.vector_index.extend(entries)
        return len(entries)

    def index_documents(
        self,
        documents: list[Document],
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        provider: str = "auto",
    ) -> int:
        total = 0
        for document in documents:
            total += self.index_document(
                document,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                provider=provider,
            )
        return total

    def index_user_documents(self, db: Session, user_id: int, *, provider: str = "auto") -> int:
        documentos = listar_documentos(db, user_id)
        return self.index_documents(documentos, provider=provider)

    def search(
        self,
        question: str,
        *,
        top_k: int = RAG_TOP_K,
        min_score: float = 0.05,
        provider: str = "auto",
        user_id: int | None = None,
        document_ids: list[int] | None = None,
    ) -> list[RAGSearchHit]:
        query_vector = gerar_embedding(question, provider=provider)
        resultados = self.vector_index.search(query_vector, top_k=max(top_k * 3, top_k), min_score=min_score)

        permitidos = set(document_ids or [])
        hits: list[RAGSearchHit] = []
        for resultado in resultados:
            metadata = resultado.entry.metadata
            if user_id is not None and metadata.get("user_id") != user_id:
                continue
            if permitidos and metadata.get("document_id") not in permitidos:
                continue

            hits.append(
                RAGSearchHit(
                    document_id=int(metadata["document_id"]),
                    document_name=str(metadata["document_name"]),
                    chunk_index=int(metadata["chunk_index"]),
                    score=float(resultado.score),
                    text=resultado.entry.text,
                    metadata=dict(metadata),
                )
            )

            if len(hits) >= top_k:
                break

        return hits

    def build_context(self, hits: list[RAGSearchHit]) -> str:
        if not hits:
            return ""

        blocos: list[str] = []
        for indice, hit in enumerate(hits, start=1):
            blocos.append(
                (
                    f"[Fonte {indice}] Documento: {hit.document_name} "
                    f"(ID {hit.document_id}, chunk {hit.chunk_index}, score {hit.score:.3f})\n"
                    f"{hit.text}"
                )
            )

        return "\n\n".join(blocos)

    def _chunks_do_documento(
        self,
        document: Document,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[TextChunk]:
        return split_text(
            document.extracted_text,
            chunk_size=chunk_size or RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP if chunk_overlap is None else chunk_overlap,
        )
