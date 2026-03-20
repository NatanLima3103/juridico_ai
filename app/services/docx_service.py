from pathlib import Path

from docx import Document


def extrair_texto_docx(file_path: Path) -> str:
    document = Document(str(file_path))
    paragrafos = [
        paragrafo.text
        for paragrafo in document.paragraphs
        if paragrafo.text.strip()
    ]
    return "\n".join(paragrafos).strip()