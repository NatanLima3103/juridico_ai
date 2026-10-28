from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import MAX_UPLOAD_SIZE_BYTES, UPLOAD_PATH

EXTENSOES_PERMITIDAS = {".pdf", ".docx", ".txt"}


def validar_extensao(nome_arquivo: str) -> str:
    extensao = Path(nome_arquivo).suffix.lower()

    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Apenas arquivos PDF, DOCX e TXT são permitidos.")

    return extensao


def formatar_tamanho_bytes(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"

    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"

    return f"{size_in_bytes / (1024 * 1024):.2f} MB"


TAMANHO_BLOCO_LEITURA = 1024 * 1024


def _validar_assinatura_arquivo(extensao: str, inicio: bytes) -> None:
    # A extensao vem do nome enviado pelo usuario; confere se o conteudo bate com ela.
    if extensao == ".pdf" and b"%PDF-" not in inicio[:1024]:
        raise ValueError("O arquivo não parece ser um PDF válido.")
    if extensao == ".docx" and not inicio.startswith(b"PK\x03\x04"):
        raise ValueError("O arquivo não parece ser um DOCX válido.")
    if extensao == ".txt" and b"\x00" in inicio:
        raise ValueError("O arquivo não parece ser um texto simples (TXT).")


def salvar_arquivo_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise ValueError("Nenhum arquivo foi enviado.")

    extensao = validar_extensao(file.filename)

    nome_seguro = f"{uuid4().hex}{extensao}"
    destino = UPLOAD_PATH / nome_seguro
    tamanho_arquivo = 0

    try:
        # Copia em blocos para nao carregar o arquivo inteiro na memoria e
        # interromper assim que o limite de tamanho for ultrapassado.
        file.file.seek(0)
        inicio = file.file.read(TAMANHO_BLOCO_LEITURA)
        if not inicio:
            raise ValueError("O arquivo enviado está vazio.")
        _validar_assinatura_arquivo(extensao, inicio)

        with destino.open("wb") as saida:
            bloco = inicio
            while bloco:
                tamanho_arquivo += len(bloco)
                if tamanho_arquivo > MAX_UPLOAD_SIZE_BYTES:
                    tamanho_limite_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
                    raise ValueError(
                        f"O arquivo excede o limite permitido de {tamanho_limite_mb} MB."
                    )
                saida.write(bloco)
                bloco = file.file.read(TAMANHO_BLOCO_LEITURA)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    return destino
