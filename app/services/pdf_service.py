from pathlib import Path

from pypdf import PdfReader


def extrair_texto_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    textos = []

    for pagina in reader.pages:
        texto = pagina.extract_text()
        if texto:
            textos.append(texto)

    return "\n\n".join(textos).strip()