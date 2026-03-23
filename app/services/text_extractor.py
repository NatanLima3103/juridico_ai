from pathlib import Path

from app.services.docx_service import extrair_texto_docx
from app.services.pdf_service import extrair_texto_pdf


def extrair_texto_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore").strip()


def extrair_texto_arquivo(file_path: Path) -> str:
    extensao = file_path.suffix.lower()

    if extensao == ".pdf":
        texto = extrair_texto_pdf(file_path)
    elif extensao == ".docx":
        texto = extrair_texto_docx(file_path)
    elif extensao == ".txt":
        texto = extrair_texto_txt(file_path)
    else:
        raise ValueError("Formato de arquivo não suportado.")

    if not texto:
        return "Nenhum texto foi encontrado no arquivo."

    return texto