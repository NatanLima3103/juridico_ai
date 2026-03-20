from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import UPLOAD_PATH

EXTENSOES_PERMITIDAS = {".pdf", ".docx"}


def validar_extensao(nome_arquivo: str) -> str:
    extensao = Path(nome_arquivo).suffix.lower()

    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Apenas arquivos PDF e DOCX são permitidos.")

    return extensao


async def salvar_arquivo_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise ValueError("Nenhum arquivo foi enviado.")

    extensao = validar_extensao(file.filename)
    nome_seguro = f"{uuid4().hex}{extensao}"
    destino = UPLOAD_PATH / nome_seguro

    with destino.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return destino