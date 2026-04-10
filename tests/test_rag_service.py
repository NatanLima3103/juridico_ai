import unittest

from app.models.document import Document
from app.services.chunk_service import split_text
from app.services.embedding_service import gerar_embedding_local
from app.services.rag_service import RAGService
from app.services.vector_service import InMemoryVectorIndex, VectorEntry, cosine_similarity


class ChunkServiceTests(unittest.TestCase):
    def test_split_text_creates_ordered_chunks_with_overlap(self):
        texto = (
            "Contrato de locacao com clausula de reajuste anual e garantia fidejussoria. "
            "O locatario deve pagar aluguel e encargos ate o quinto dia util. "
            "Em caso de inadimplemento, incidem multa e juros."
        )

        chunks = split_text(texto, chunk_size=80, chunk_overlap=15)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertLess(chunks[0].start_char, chunks[1].start_char)
        self.assertLess(chunks[1].start_char, chunks[0].end_char)
        self.assertTrue(chunks[0].text)
        self.assertTrue(chunks[1].text)


class EmbeddingAndVectorTests(unittest.TestCase):
    def test_local_embedding_is_deterministic_and_normalized(self):
        vetor_1 = gerar_embedding_local("rescisao contratual por inadimplemento", dimensions=32)
        vetor_2 = gerar_embedding_local("rescisao contratual por inadimplemento", dimensions=32)

        self.assertEqual(vetor_1, vetor_2)
        norma = sum(valor * valor for valor in vetor_1) ** 0.5
        self.assertAlmostEqual(norma, 1.0, places=6)

    def test_vector_index_returns_most_similar_entry_first(self):
        indice = InMemoryVectorIndex()
        indice.add(
            VectorEntry(
                id="1",
                vector=gerar_embedding_local("execucao de titulo extrajudicial", dimensions=32),
                text="execucao de titulo extrajudicial",
            )
        )
        indice.add(
            VectorEntry(
                id="2",
                vector=gerar_embedding_local("guarda compartilhada e alimentos", dimensions=32),
                text="guarda compartilhada e alimentos",
            )
        )

        query = gerar_embedding_local("titulo extrajudicial inadimplido", dimensions=32)
        resultados = indice.search(query, top_k=2, min_score=-1.0)

        self.assertEqual(len(resultados), 2)
        self.assertEqual(resultados[0].entry.id, "1")
        self.assertGreaterEqual(resultados[0].score, resultados[1].score)
        self.assertGreater(cosine_similarity(query, resultados[0].entry.vector), 0)


class RAGServiceTests(unittest.TestCase):
    def test_rag_service_indexes_documents_and_returns_context(self):
        documento_a = Document(
            id=10,
            original_filename="contrato-locacao.pdf",
            saved_filename="contrato-locacao.pdf",
            file_path="C:/tmp/contrato-locacao.pdf",
            file_type=".pdf",
            extracted_text=(
                "Contrato de locacao residencial. O aluguel vence no quinto dia util. "
                "Ha previsao de multa moratoria em caso de atraso."
            ),
            user_id=1,
        )
        documento_b = Document(
            id=11,
            original_filename="guarda-filhos.docx",
            saved_filename="guarda-filhos.docx",
            file_path="C:/tmp/guarda-filhos.docx",
            file_type=".docx",
            extracted_text=(
                "Acao de guarda compartilhada com pedidos relativos a convivencia e alimentos. "
                "Prioriza o melhor interesse da crianca."
            ),
            user_id=1,
        )

        service = RAGService()
        total_chunks = service.index_documents([documento_a, documento_b], chunk_size=70, chunk_overlap=10)
        resultados = service.search(
            "aluguel vence no quinto dia util e multa moratoria por atraso",
            top_k=2,
            user_id=1,
        )
        contexto = service.build_context(resultados)

        self.assertGreaterEqual(total_chunks, 2)
        self.assertTrue(resultados)
        self.assertEqual(resultados[0].document_id, 10)
        self.assertIn("contrato-locacao.pdf", contexto)
        self.assertIn("multa", contexto.lower())

    def test_rag_service_can_filter_by_document_ids(self):
        documento_a = Document(
            id=21,
            original_filename="trabalhista.txt",
            saved_filename="trabalhista.txt",
            file_path="C:/tmp/trabalhista.txt",
            file_type=".txt",
            extracted_text="Horas extras habituais e reflexos nas verbas rescisorias.",
            user_id=3,
        )
        documento_b = Document(
            id=22,
            original_filename="tributario.txt",
            saved_filename="tributario.txt",
            file_path="C:/tmp/tributario.txt",
            file_type=".txt",
            extracted_text="Execucao fiscal e discussao sobre prescricao intercorrente.",
            user_id=3,
        )

        service = RAGService()
        service.index_documents([documento_a, documento_b], chunk_size=80, chunk_overlap=10)

        resultados = service.search(
            "prescricao em execucao fiscal",
            top_k=2,
            user_id=3,
            document_ids=[22],
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0].document_id, 22)


if __name__ == "__main__":
    unittest.main()
