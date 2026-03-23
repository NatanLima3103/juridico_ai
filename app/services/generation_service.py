from sqlalchemy.orm import Session

from app.models.generation import Generation


TIPOS_DE_DOCUMENTO = [
    "Petição inicial",
    "Contestação",
    "Réplica",
    "Manifestação",
    "Parecer jurídico",
    "Contrato",
    "Notificação extrajudicial",
    "Recurso",
    "Outro",
]


def criar_geracao(
    db: Session,
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    context_used: str,
    generated_text: str,
) -> Generation:
    geracao = Generation(
        client_name=client_name,
        document_type=document_type,
        case_subject=case_subject,
        facts=facts,
        requests=requests,
        legal_basis=legal_basis,
        context_used=context_used,
        generated_text=generated_text,
    )
    db.add(geracao)
    db.commit()
    db.refresh(geracao)
    return geracao


def listar_geracoes(db: Session) -> list[Generation]:
    return db.query(Generation).order_by(Generation.created_at.desc()).all()


def buscar_geracao_por_id(db: Session, generation_id: int) -> Generation | None:
    return db.query(Generation).filter(Generation.id == generation_id).first()


def resumir_texto(texto: str, limite: int = 220) -> str:
    texto_limpo = " ".join((texto or "").split())

    if not texto_limpo:
        return "Sem conteúdo."

    if len(texto_limpo) <= limite:
        return texto_limpo

    return texto_limpo[:limite].rstrip() + "..."


def montar_contexto_documental(documentos: list) -> str:
    if not documentos:
        return "Nenhum documento base selecionado."

    blocos = []

    for indice, documento in enumerate(documentos, start=1):
        texto = " ".join((documento.extracted_text or "").split())

        if len(texto) > 1200:
            texto = texto[:1200].rstrip() + "..."

        bloco = (
            f"Documento {indice}\n"
            f"ID: {documento.id}\n"
            f"Nome original: {documento.original_filename}\n"
            f"Tipo: {documento.file_type}\n"
            f"Trecho extraído:\n{texto}\n"
        )
        blocos.append(bloco)

    return "\n" + ("\n" + ("-" * 60) + "\n").join(blocos)


def gerar_rascunho_juridico(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    context_used: str,
) -> str:
    base_legal = legal_basis.strip() if legal_basis else "A fundamentação jurídica específica deverá ser aprofundada conforme a legislação aplicável, a jurisprudência pertinente e a estratégia processual adotada."

    return f"""
MINUTA JURÍDICA INICIAL

Cliente:
{client_name}

Tipo de documento:
{document_type}

Assunto do caso:
{case_subject}

1. Síntese inicial
Trata-se de elaboração de {document_type.lower()} relacionada ao seguinte assunto:
{case_subject}

2. Exposição dos fatos
{facts}

3. Pedidos e objetivos pretendidos
{requests}

4. Fundamentação jurídica inicial
{base_legal}

5. Contexto documental utilizado
{context_used}

6. Estrutura sugerida para continuidade
Sugere-se que a peça final observe, conforme cabível:
- endereçamento;
- qualificação das partes;
- resumo dos fatos;
- fundamentos jurídicos;
- pedidos;
- requerimentos finais;
- provas;
- demais elementos formais aplicáveis.

7. Observação
Este texto representa um rascunho jurídico inicial automatizado, elaborado como base de apoio para revisão, complementação e personalização posterior pelo profissional responsável.
""".strip()