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


async def salvar_arquivo_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise ValueError("Nenhum arquivo foi enviado.")

    extensao = validar_extensao(file.filename)

    conteudo = await file.read()

    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")

    tamanho_arquivo = len(conteudo)

    if tamanho_arquivo > MAX_UPLOAD_SIZE_BYTES:
        tamanho_limite_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise ValueError(
            f"O arquivo excede o limite permitido de {tamanho_limite_mb} MB."
        )

    nome_seguro = f"{uuid4().hex}{extensao}"
    destino = UPLOAD_PATH / nome_seguro

    destino.write_bytes(conteudo)
    await file.close()

    return destino