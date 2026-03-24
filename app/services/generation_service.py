from sqlalchemy.orm import Session, joinedload

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
    writing_profile_id: int | None = None,
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
        writing_profile_id=writing_profile_id,
    )
    db.add(geracao)
    db.commit()
    db.refresh(geracao)
    return geracao


def listar_geracoes(db: Session) -> list[Generation]:
    return (
        db.query(Generation)
        .options(joinedload(Generation.writing_profile))
        .order_by(Generation.created_at.desc())
        .all()
    )


def buscar_geracao_por_id(db: Session, generation_id: int) -> Generation | None:
    return (
        db.query(Generation)
        .options(joinedload(Generation.writing_profile))
        .filter(Generation.id == generation_id)
        .first()
    )


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


def montar_contexto_perfil_escrita(profile) -> str:
    if not profile:
        return "Nenhum perfil de escrita selecionado."

    expressoes = (profile.recurring_expressions or "").strip()
    observacoes = (profile.legal_style_notes or "").strip()

    return (
        f"Perfil de escrita selecionado:\n"
        f"- Nome do perfil: {profile.profile_name}\n"
        f"- Advogado: {profile.lawyer_name or 'Não informado'}\n"
        f"- Escritório: {profile.office_name or 'Não informado'}\n"
        f"- Tom: {profile.tone or 'Formal'}\n"
        f"- Estilo de qualificação: {profile.qualification_style or 'Não informado'}\n"
        f"- Frase de abertura: {profile.opening_phrase or 'Não informada'}\n"
        f"- Introdução dos pedidos: {profile.request_intro or 'Não informada'}\n"
        f"- Frase de fechamento: {profile.closing_phrase or 'Não informada'}\n"
        f"- Observações de estilo: {observacoes or 'Não informado'}\n"
        f"- Expressões recorrentes: {expressoes or 'Não informado'}"
    )


def _bloco_estrutura_por_tipo(document_type: str) -> str:
    tipo = (document_type or "").strip().lower()

    if tipo == "petição inicial":
        return (
            "- endereçamento;\n"
            "- qualificação das partes;\n"
            "- exposição detalhada dos fatos;\n"
            "- fundamentos jurídicos;\n"
            "- pedidos;\n"
            "- valor da causa;\n"
            "- provas;\n"
            "- requerimentos finais."
        )

    if tipo == "contestação":
        return (
            "- endereçamento;\n"
            "- síntese da demanda;\n"
            "- preliminares, se cabíveis;\n"
            "- impugnação dos fatos;\n"
            "- fundamentos jurídicos defensivos;\n"
            "- pedidos finais;\n"
            "- provas."
        )

    if tipo == "recurso":
        return (
            "- tempestividade;\n"
            "- cabimento;\n"
            "- resumo da decisão recorrida;\n"
            "- razões recursais;\n"
            "- pedidos de reforma ou anulação;\n"
            "- requerimentos finais."
        )

    if tipo == "contrato":
        return (
            "- qualificação das partes;\n"
            "- objeto;\n"
            "- obrigações;\n"
            "- prazo;\n"
            "- valores;\n"
            "- multas e penalidades;\n"
            "- rescisão;\n"
            "- foro."
        )

    if tipo == "notificação extrajudicial":
        return (
            "- identificação das partes;\n"
            "- descrição objetiva dos fatos;\n"
            "- fundamento da notificação;\n"
            "- providência exigida;\n"
            "- prazo para cumprimento;\n"
            "- advertências cabíveis."
        )

    return (
        "- endereçamento, se aplicável;\n"
        "- contextualização do caso;\n"
        "- exposição dos fatos;\n"
        "- fundamentação;\n"
        "- pedidos ou conclusões;\n"
        "- fechamento formal."
    )


def gerar_rascunho_juridico(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    context_used: str,
    writing_profile=None,
) -> str:
    base_legal = (
        legal_basis.strip()
        if legal_basis
        else "A fundamentação jurídica específica deverá ser aprofundada conforme a legislação aplicável, a jurisprudência pertinente e a estratégia processual adotada."
    )

    estrutura_tipo = _bloco_estrutura_por_tipo(document_type)

    tom = "Formal"
    qualificacao = "já qualificado(a) nos autos ou a ser devidamente qualificado(a)"
    abertura = "vem, com o devido respeito, à presença de Vossa Excelência, apresentar a presente:"
    fechamento = "Termos em que,\nPede deferimento."
    introducao_pedidos = "Diante do exposto, requer:"
    observacoes_estilo = "Utilizar linguagem jurídica formal, objetiva e técnica."
    expressoes = "data venia; conforme entendimento jurisprudencial; nos termos da legislação aplicável"
    advogado = ""
    escritorio = ""

    if writing_profile:
        tom = writing_profile.tone or tom
        qualificacao = writing_profile.qualification_style or qualificacao
        abertura = writing_profile.opening_phrase or abertura
        fechamento = writing_profile.closing_phrase or fechamento
        introducao_pedidos = writing_profile.request_intro or introducao_pedidos
        observacoes_estilo = writing_profile.legal_style_notes or observacoes_estilo
        expressoes = writing_profile.recurring_expressions or expressoes
        advogado = writing_profile.lawyer_name or ""
        escritorio = writing_profile.office_name or ""

    assinatura_bloco = []
    if advogado:
        assinatura_bloco.append(advogado)
    if escritorio:
        assinatura_bloco.append(escritorio)

    assinatura_final = "\n".join(assinatura_bloco)

    texto = f"""
MINUTA JURÍDICA INICIAL

Cliente:
{client_name}

Tipo de documento:
{document_type}

Assunto do caso:
{case_subject}

Tom de escrita sugerido:
{tom}

1. Abertura sugerida
{qualificacao}, {abertura}

2. Síntese inicial
Trata-se de elaboração de {document_type.lower()} relacionada ao seguinte assunto:
{case_subject}

3. Exposição dos fatos
{facts}

4. Fundamentação jurídica inicial
{base_legal}

5. Diretrizes de estilo aplicadas
- tom predominante: {tom}
- observações de estilo: {observacoes_estilo}
- expressões recorrentes sugeridas: {expressoes}

6. Contexto documental e estratégico utilizado
{context_used}

7. Estrutura sugerida para continuidade
Sugere-se que a peça final observe a seguinte organização:

{estrutura_tipo}

8. Bloco de pedidos sugerido
{introducao_pedidos}

{requests}

9. Diretriz de revisão
Antes do uso prático do documento, recomenda-se revisar:
- nomes das partes;
- datas;
- pedidos;
- fundamentos legais;
- competência;
- documentação probatória;
- adequação estratégica ao caso concreto.

10. Fechamento sugerido
{fechamento}
""".strip()

    if assinatura_final:
        texto += f"\n\n{assinatura_final}"

    return texto