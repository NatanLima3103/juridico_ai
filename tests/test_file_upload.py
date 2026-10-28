import io
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import UploadFile

from app.models.document import Document
from app.services.file_service import salvar_arquivo_upload
from tests.test_documents import create_documents_test_client, criar_usuario_teste, fazer_login


def criar_upload(nome: str, conteudo: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(conteudo), filename=nome)


class SalvarArquivoUploadTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = Path(".tmp_pytest") / f"uploads-{uuid4().hex}"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        patcher = patch("app.services.file_service.UPLOAD_PATH", self.upload_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.upload_dir, ignore_errors=True)

    def test_saves_valid_files(self):
        casos = [
            ("peticao.pdf", b"%PDF-1.7\n conteudo"),
            ("contrato.docx", b"PK\x03\x04 conteudo zip"),
            ("notas.txt", "texto simples com acentuação".encode("utf-8")),
        ]
        for nome, conteudo in casos:
            with self.subTest(nome=nome):
                destino = salvar_arquivo_upload(criar_upload(nome, conteudo))
                self.assertEqual(destino.read_bytes(), conteudo)
                self.assertEqual(destino.suffix, Path(nome).suffix)

    def test_rejects_content_that_does_not_match_extension(self):
        casos = [
            ("falso.pdf", b"MZ\x90\x00 executavel"),
            ("falso.docx", b"%PDF-1.7 na verdade um pdf"),
            ("falso.txt", b"bin\x00ario"),
        ]
        for nome, conteudo in casos:
            with self.subTest(nome=nome):
                with self.assertRaises(ValueError):
                    salvar_arquivo_upload(criar_upload(nome, conteudo))
        self.assertEqual(list(self.upload_dir.iterdir()), [])

    def test_rejects_empty_file(self):
        with self.assertRaisesRegex(ValueError, "vazio"):
            salvar_arquivo_upload(criar_upload("vazio.txt", b""))

    def test_oversized_file_is_rejected_and_not_left_on_disk(self):
        conteudo = b"a" * (3 * 1024 * 1024)
        with patch("app.services.file_service.MAX_UPLOAD_SIZE_BYTES", 2 * 1024 * 1024):
            with self.assertRaisesRegex(ValueError, "excede o limite"):
                salvar_arquivo_upload(criar_upload("grande.txt", conteudo))
        self.assertEqual(list(self.upload_dir.iterdir()), [])


class UploadRouteErrorTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = Path(".tmp_pytest") / f"uploads-{uuid4().hex}"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        patcher = patch("app.services.file_service.UPLOAD_PATH", self.upload_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.upload_dir, ignore_errors=True)

    def test_unreadable_pdf_shows_friendly_error_and_removes_file(self):
        client, testing_session_local = create_documents_test_client()
        criar_usuario_teste(testing_session_local, nome="Ana Souza", email="ana@example.com")
        fazer_login(client, email="ana@example.com")

        response = client.post(
            "/documents/upload",
            files={"file": ("quebrado.pdf", b"%PDF-1.7 sem estrutura valida", "application/pdf")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Não foi possível ler o conteúdo do arquivo", response.text)
        self.assertEqual(list(self.upload_dir.iterdir()), [])

        db = testing_session_local()
        try:
            self.assertEqual(db.query(Document).count(), 0)
        finally:
            db.close()

    def test_unexpected_error_does_not_leak_details(self):
        client, testing_session_local = create_documents_test_client()
        criar_usuario_teste(testing_session_local, nome="Ana Souza", email="ana@example.com")
        fazer_login(client, email="ana@example.com")

        with patch(
            "app.routers.documents.criar_documento",
            side_effect=RuntimeError("detalhe interno do banco"),
        ):
            response = client.post(
                "/documents/upload",
                files={"file": ("notas.txt", b"conteudo", "text/plain")},
            )

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("detalhe interno do banco", response.text)
        self.assertIn("erro inesperado", response.text)
        self.assertEqual(list(self.upload_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
