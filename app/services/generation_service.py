from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.generation import Generation
from app.schemas.generation import GenerationCreate


def buscar_documentos_recentes(db: Session, limite: int = 3) -> list[Document]:
    return (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .limit(limite)
        .all()
    )


def montar_contexto_documentos(documentos: list[Document], limite_caracteres: int = 3000) -> str:
    if not documentos:
        return "Nenhum documento de referência foi encontrado."

    partes = []

    for documento in documentos:
        trecho = documento.extracted_text[:1000].strip()
        partes.append(
            f"Documento: {documento.original_filename}\n"
            f"Tipo: {documento.file_type}\n"
            f"Trecho:\n{trecho}"
        )

    contexto = "\n\n---\n\n".join(partes)
    return contexto[:limite_caracteres]


def gerar_minuta_inicial(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str | None,
    context_used: str,
) -> str:
    fundamento = legal_basis if legal_basis else "Fundamentação jurídica a ser complementada conforme o caso concreto."

    minuta = f"""
EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) JUIZ(A) DE DIREITO DA VARA COMPETENTE

{client_name}, já qualificado(a) ou a ser devidamente qualificado(a) nos autos, por intermédio de seu advogado, vem, respeitosamente, à presença de Vossa Excelência, propor a presente:

{document_type.upper()}

em face da parte contrária competente, pelos fatos e fundamentos a seguir expostos.

I - DOS FATOS

{facts}

II - DO DIREITO

A presente demanda versa sobre o seguinte tema: {case_subject}.

{fundamento}

III - DOS PEDIDOS

Diante do exposto, requer:

{requests}

IV - DOCUMENTOS DE REFERÊNCIA UTILIZADOS

Os seguintes documentos salvos no sistema foram considerados como base contextual para esta minuta:

{context_used}

Termos em que,
Pede deferimento.
""".strip()

    return minuta


def criar_geracao(db: Session, generation_data: GenerationCreate) -> Generation:
    geracao = Generation(
        client_name=generation_data.client_name,
        document_type=generation_data.document_type,
        case_subject=generation_data.case_subject,
        facts=generation_data.facts,
        requests=generation_data.requests,
        legal_basis=generation_data.legal_basis,
        context_used=generation_data.context_used,
        generated_text=generation_data.generated_text,
    )
    db.add(geracao)
    db.commit()
    db.refresh(geracao)
    return geracao


def listar_geracoes(db: Session) -> list[Generation]:
    return db.query(Generation).order_by(Generation.created_at.desc()).all()


def buscar_geracao_por_id(db: Session, generation_id: int) -> Generation | None:
    return db.query(Generation).filter(Generation.id == generation_id).first()