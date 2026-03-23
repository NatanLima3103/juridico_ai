import re

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.generation import Generation
from app.models.writing_profile import WritingProfile
from app.schemas.generation import GenerationCreate


def buscar_documentos_recentes(db: Session, limite: int = 3) -> list[Document]:
    return (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .limit(limite)
        .all()
    )


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [linha.strip() for linha in texto.split("\n")]
    linhas_processadas = []
    ultima_linha_vazia = False

    for linha in linhas:
        if linha:
            linhas_processadas.append(linha)
            ultima_linha_vazia = False
        else:
            if not ultima_linha_vazia:
                linhas_processadas.append("")
            ultima_linha_vazia = True

    texto_final = "\n".join(linhas_processadas).strip()
    texto_final = re.sub(r"[ \t]+", " ", texto_final)

    return texto_final


def validar_dados_geracao(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str | None = None,
) -> dict:
    dados = {
        "client_name": normalizar_texto(client_name),
        "document_type": normalizar_texto(document_type),
        "case_subject": normalizar_texto(case_subject),
        "facts": normalizar_texto(facts),
        "requests": normalizar_texto(requests),
        "legal_basis": normalizar_texto(legal_basis or ""),
    }

    if not dados["client_name"]:
        raise ValueError("Informe o nome do cliente.")

    if len(dados["client_name"]) < 3:
        raise ValueError("O nome do cliente deve ter pelo menos 3 caracteres.")

    if not dados["document_type"]:
        raise ValueError("Informe o tipo de peça.")

    if len(dados["document_type"]) < 3:
        raise ValueError("O tipo de peça deve ter pelo menos 3 caracteres.")

    if not dados["case_subject"]:
        raise ValueError("Informe o tema do caso.")

    if len(dados["case_subject"]) < 3:
        raise ValueError("O tema do caso deve ter pelo menos 3 caracteres.")

    if not dados["facts"]:
        raise ValueError("Informe os fatos do caso.")

    if len(dados["facts"]) < 20:
        raise ValueError(
            "Os fatos devem ter pelo menos 20 caracteres para gerar uma minuta minimamente útil."
        )

    if not dados["requests"]:
        raise ValueError("Informe os pedidos.")

    if len(dados["requests"]) < 10:
        raise ValueError("Os pedidos devem ter pelo menos 10 caracteres.")

    return dados


def quebrar_em_itens(texto: str) -> list[str]:
    if not texto:
        return []

    texto = texto.replace(";", "\n")
    linhas = [linha.strip(" -•\t") for linha in texto.split("\n")]
    itens = [linha for linha in linhas if linha]

    return itens


def formatar_secao_em_topicos(texto: str) -> str:
    itens = quebrar_em_itens(texto)

    if not itens:
        return "Não informado."

    if len(itens) == 1:
        return itens[0]

    linhas_formatadas = [
        f"{indice}. {item}" for indice, item in enumerate(itens, start=1)
    ]
    return "\n".join(linhas_formatadas)


def resumir_texto_documento(
    texto: str,
    limite_linhas: int = 6,
    limite_caracteres: int = 900,
) -> str:
    texto = normalizar_texto(texto)

    if not texto:
        return "Documento sem texto extraído."

    linhas = [linha for linha in texto.split("\n") if linha.strip()]
    resumo = "\n".join(linhas[:limite_linhas]).strip()

    if len(resumo) > limite_caracteres:
        resumo = resumo[:limite_caracteres].rstrip() + "..."

    return resumo


def montar_contexto_documentos(
    documentos: list[Document],
    limite_caracteres: int = 4000,
) -> str:
    if not documentos:
        return "Nenhum documento de referência foi encontrado no sistema."

    partes = [
        f"Foram encontrados {len(documentos)} documento(s) de referência mais recente(s) no sistema."
    ]

    for indice, documento in enumerate(documentos, start=1):
        resumo = resumir_texto_documento(documento.extracted_text)
        parte = (
            f"[Documento {indice}]\n"
            f"Nome original: {documento.original_filename}\n"
            f"Tipo do arquivo: {documento.file_type}\n"
            f"Resumo do conteúdo extraído:\n{resumo}"
        )
        partes.append(parte)

    contexto = "\n\n---\n\n".join(partes)

    if len(contexto) > limite_caracteres:
        contexto = (
            contexto[:limite_caracteres].rstrip()
            + "\n\n[Contexto truncado por limite de caracteres.]"
        )

    return contexto


def montar_fundamentacao(case_subject: str, legal_basis: str | None) -> str:
    if legal_basis and legal_basis.strip():
        return legal_basis.strip()

    return (
        f"A presente demanda trata de matéria relacionada a {case_subject}. "
        "A fundamentação jurídica específica deverá ser aprofundada com base na legislação aplicável, "
        "na jurisprudência pertinente e nos documentos do caso concreto."
    )


def montar_observacoes_perfil(perfil: WritingProfile | None) -> str:
    if not perfil:
        return "Nenhum perfil de escrita ativo foi utilizado."

    partes = [
        f"Perfil ativo: {perfil.profile_name}",
        f"Tom: {perfil.tone}",
    ]

    if perfil.lawyer_name:
        partes.append(f"Advogado: {perfil.lawyer_name}")

    if perfil.office_name:
        partes.append(f"Escritório: {perfil.office_name}")

    if perfil.legal_style_notes:
        partes.append(f"Observações de estilo: {perfil.legal_style_notes}")

    if perfil.recurring_expressions:
        partes.append(f"Expressões recorrentes: {perfil.recurring_expressions}")

    return "\n".join(partes)


def gerar_minuta_inicial(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str | None,
    context_used: str,
    perfil_ativo: WritingProfile | None = None,
) -> str:
    fatos_formatados = formatar_secao_em_topicos(facts)
    pedidos_formatados = formatar_secao_em_topicos(requests)
    fundamentacao = montar_fundamentacao(case_subject, legal_basis)

    qualificacao = (
        perfil_ativo.qualification_style
        if perfil_ativo and perfil_ativo.qualification_style
        else "já qualificado(a) nos autos ou a ser devidamente qualificado(a)"
    )

    abertura = (
        perfil_ativo.opening_phrase
        if perfil_ativo and perfil_ativo.opening_phrase
        else "vem, com o devido respeito, à presença de Vossa Excelência, apresentar a presente:"
    )

    intro_pedidos = (
        perfil_ativo.request_intro
        if perfil_ativo and perfil_ativo.request_intro
        else "Diante do exposto, requer:"
    )

    encerramento = (
        perfil_ativo.closing_phrase
        if perfil_ativo and perfil_ativo.closing_phrase
        else "Termos em que,\nPede deferimento."
    )

    observacoes_perfil = montar_observacoes_perfil(perfil_ativo)

    minuta = f"""
EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) JUIZ(A) DE DIREITO DA VARA COMPETENTE

{client_name}, {qualificacao}, por intermédio de seu advogado, {abertura}

{document_type.upper()}

em face da parte contrária, pelos fatos e fundamentos a seguir expostos.

I - SÍNTESE DA DEMANDA

Trata-se de demanda relacionada ao seguinte tema: {case_subject}.

II - DOS FATOS

{fatos_formatados}

III - DO DIREITO

{fundamentacao}

IV - DOS PEDIDOS

{intro_pedidos}

{pedidos_formatados}

V - PERFIL DE ESCRITA UTILIZADO

{observacoes_perfil}

VI - DOCUMENTOS DE REFERÊNCIA ANALISADOS

Para auxiliar na elaboração desta minuta inicial, o sistema considerou o seguinte contexto:

{context_used}

{encerramento}
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