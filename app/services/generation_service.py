from datetime import datetime
from io import BytesIO

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
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


def agora_brasil():
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        except ZoneInfoNotFoundError:
            pass
        except Exception:
            pass

    return datetime.now()


def validar_dados_geracao(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str = "",
) -> dict:
    client_name = (client_name or "").strip()
    document_type = (document_type or "").strip()
    case_subject = (case_subject or "").strip()
    facts = (facts or "").strip()
    requests = (requests or "").strip()
    legal_basis = (legal_basis or "").strip()

    if not client_name:
        raise ValueError("Informe o nome do cliente.")

    if len(client_name) < 3:
        raise ValueError("O nome do cliente deve ter pelo menos 3 caracteres.")

    if not document_type:
        raise ValueError("Selecione o tipo de documento.")

    if document_type not in TIPOS_DE_DOCUMENTO:
        raise ValueError("Selecione um tipo de documento válido.")

    if not case_subject:
        raise ValueError("Informe o assunto do caso.")

    if len(case_subject) < 8:
        raise ValueError("Descreva melhor o assunto do caso.")

    if not facts:
        raise ValueError("Informe os fatos do caso.")

    if len(facts) < 30:
        raise ValueError("Descreva melhor os fatos do caso, com mais detalhes.")

    if not requests:
        raise ValueError("Informe os pedidos.")

    if len(requests) < 15:
        raise ValueError("Detalhe melhor os pedidos que deseja incluir na minuta.")

    return {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
    }


def serializar_ids_documentos(document_ids: list[int]) -> str:
    ids_validos = []

    for item in document_ids or []:
        if isinstance(item, int) and item > 0:
            ids_validos.append(str(item))

    return ",".join(ids_validos)


def desserializar_ids_documentos(source_document_ids: str | None) -> list[int]:
    if not source_document_ids:
        return []

    ids = []

    for item in source_document_ids.split(","):
        item_limpo = item.strip()
        if item_limpo.isdigit():
            ids.append(int(item_limpo))

    return ids


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
    source_document_ids: str | None = None,
) -> Generation:
    agora = agora_brasil()

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
        source_document_ids=source_document_ids,
        created_at=agora,
        updated_at=agora,
    )
    db.add(geracao)
    db.commit()
    db.refresh(geracao)
    return geracao


def atualizar_geracao(
    db: Session,
    geracao: Generation,
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    context_used: str,
    generated_text: str,
    writing_profile_id: int | None = None,
    source_document_ids: str | None = None,
) -> Generation:
    geracao.client_name = client_name
    geracao.document_type = document_type
    geracao.case_subject = case_subject
    geracao.facts = facts
    geracao.requests = requests
    geracao.legal_basis = legal_basis
    geracao.context_used = context_used
    geracao.generated_text = generated_text
    geracao.writing_profile_id = writing_profile_id
    geracao.source_document_ids = source_document_ids
    geracao.updated_at = agora_brasil()

    db.add(geracao)
    db.commit()
    db.refresh(geracao)
    return geracao


def listar_geracoes(db: Session) -> list[Generation]:
    return (
        db.query(Generation)
        .options(joinedload(Generation.writing_profile))
        .order_by(Generation.updated_at.desc(), Generation.created_at.desc())
        .all()
    )


def buscar_geracao_por_id(db: Session, generation_id: int) -> Generation | None:
    return (
        db.query(Generation)
        .options(joinedload(Generation.writing_profile))
        .filter(Generation.id == generation_id)
        .first()
    )


def excluir_geracao(db: Session, generation_id: int) -> bool:
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        return False

    db.delete(geracao)
    db.commit()
    return True


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


def _tipo_normalizado(document_type: str) -> str:
    return (document_type or "").strip().lower()


def _titulo_documento(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return "PETIÇÃO INICIAL"
    if tipo == "contestação":
        return "CONTESTAÇÃO"
    if tipo == "réplica":
        return "RÉPLICA"
    if tipo == "manifestação":
        return "MANIFESTAÇÃO"
    if tipo == "parecer jurídico":
        return "PARECER JURÍDICO"
    if tipo == "contrato":
        return "MINUTA CONTRATUAL"
    if tipo == "notificação extrajudicial":
        return "NOTIFICAÇÃO EXTRAJUDICIAL"
    if tipo == "recurso":
        return "RECURSO"
    return "MINUTA JURÍDICA"


def _qualificacao_base_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contrato":
        return "As partes abaixo identificadas, de comum acordo,"
    if tipo == "parecer jurídico":
        return "Submete-se à apreciação jurídica a situação abaixo delineada,"
    if tipo == "notificação extrajudicial":
        return "A parte notificante, por meio da presente,"
    return "já qualificado(a) nos autos ou a ser devidamente qualificado(a)"


def _abertura_base_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return "vem, com o devido respeito, à presença de Vossa Excelência, propor a presente:"
    if tipo == "contestação":
        return "vem, com o devido respeito, à presença de Vossa Excelência, apresentar:"
    if tipo == "réplica":
        return "vem, respeitosamente, à presença de Vossa Excelência, apresentar:"
    if tipo == "manifestação":
        return "vem, respeitosamente, à presença de Vossa Excelência, apresentar a presente:"
    if tipo == "parecer jurídico":
        return "para emitir o presente parecer:"
    if tipo == "contrato":
        return "resolvem firmar a presente minuta:"
    if tipo == "notificação extrajudicial":
        return "promove a presente notificação:"
    if tipo == "recurso":
        return "vem, com o devido respeito, à presença de Vossa Excelência, interpor o presente:"
    return "vem, com o devido respeito, à presença de Vossa Excelência, apresentar a presente:"


def _bloco_estrutura_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return (
            "- endereçamento;\n"
            "- qualificação das partes;\n"
            "- exposição dos fatos;\n"
            "- fundamentos jurídicos;\n"
            "- pedidos;\n"
            "- provas;\n"
            "- requerimentos finais."
        )

    if tipo == "contestação":
        return (
            "- endereçamento;\n"
            "- síntese da demanda;\n"
            "- preliminares, se cabíveis;\n"
            "- impugnação específica dos fatos;\n"
            "- fundamentos defensivos;\n"
            "- pedidos finais;\n"
            "- provas."
        )

    if tipo == "réplica":
        return (
            "- síntese da contestação;\n"
            "- impugnação dos argumentos defensivos;\n"
            "- reforço da tese autoral;\n"
            "- ratificação dos pedidos;\n"
            "- requerimentos finais."
        )

    if tipo == "manifestação":
        return (
            "- contextualização do ponto processual;\n"
            "- esclarecimentos relevantes;\n"
            "- argumentação objetiva;\n"
            "- requerimento correspondente;\n"
            "- fechamento."
        )

    if tipo == "parecer jurídico":
        return (
            "- relatório;\n"
            "- questão submetida à análise;\n"
            "- fundamentação jurídica;\n"
            "- conclusão."
        )

    if tipo == "contrato":
        return (
            "- identificação das partes;\n"
            "- objeto;\n"
            "- obrigações e responsabilidades;\n"
            "- prazo e vigência;\n"
            "- valores e forma de pagamento;\n"
            "- penalidades;\n"
            "- rescisão;\n"
            "- foro."
        )

    if tipo == "notificação extrajudicial":
        return (
            "- identificação das partes;\n"
            "- relato objetivo dos fatos;\n"
            "- fundamento da exigência;\n"
            "- providência esperada;\n"
            "- prazo para cumprimento;\n"
            "- advertência final."
        )

    if tipo == "recurso":
        return (
            "- tempestividade;\n"
            "- cabimento;\n"
            "- síntese da decisão recorrida;\n"
            "- fundamentos para reforma ou invalidação;\n"
            "- pedido recursal."
        )

    return (
        "- qualificação das partes;\n"
        "- exposição dos fatos;\n"
        "- fundamentos aplicáveis;\n"
        "- pedidos ou conclusão;\n"
        "- encerramento."
    )


def _introducao_especifica_por_tipo(document_type: str, case_subject: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return (
            f"A presente demanda tem por objeto a apreciação de pretensão relacionada a {case_subject}, "
            "conforme os fundamentos fáticos e jurídicos a seguir expostos."
        )
    if tipo == "contestação":
        return (
            f"Trata-se de manifestação defensiva apresentada em face de demanda relacionada a {case_subject}, "
            "nos termos a seguir delineados."
        )
    if tipo == "réplica":
        return (
            f"A presente réplica refere-se à demanda que versa sobre {case_subject}, "
            "com o objetivo de impugnar os argumentos defensivos apresentados."
        )
    if tipo == "manifestação":
        return (
            f"A presente manifestação refere-se ao tema {case_subject}, "
            "sendo apresentada para esclarecimento e requerimento do que for de direito."
        )
    if tipo == "parecer jurídico":
        return (
            f"O presente parecer examina a questão jurídica relacionada a {case_subject}, "
            "considerando os elementos informados e as premissas técnicas aplicáveis."
        )
    if tipo == "contrato":
        return (
            f"A presente minuta contratual tem por objeto disciplinar juridicamente a relação envolvendo {case_subject}, "
            "observadas as cláusulas essenciais abaixo estruturadas."
        )
    if tipo == "notificação extrajudicial":
        return (
            f"A presente notificação extrajudicial refere-se à situação relacionada a {case_subject}, "
            "com o propósito de formalizar ciência e exigir a providência cabível."
        )
    if tipo == "recurso":
        return (
            f"O presente recurso versa sobre controvérsia atinente a {case_subject}, "
            "buscando a revisão da decisão impugnada nos termos a seguir expostos."
        )

    return (
        f"A presente minuta jurídica versa sobre {case_subject}, "
        "conforme os elementos apresentados."
    )


def _titulo_secao_fatos_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "I - DO RELATÓRIO"
    if tipo == "contrato":
        return "I - DO CONTEXTO CONTRATUAL"
    if tipo == "notificação extrajudicial":
        return "I - DOS FATOS"
    return "I - DOS FATOS"


def _conteudo_secao_fatos_por_tipo(document_type: str, facts: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contrato":
        return (
            "Para adequada compreensão do objeto contratual e das obrigações a serem delimitadas, "
            "considera-se o seguinte contexto:\n\n"
            f"{facts}"
        )

    if tipo == "parecer jurídico":
        return (
            "Submetem-se à análise os seguintes fatos e elementos relevantes:\n\n"
            f"{facts}"
        )

    return facts


def _titulo_secao_fundamentacao_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "II - DA ANÁLISE JURÍDICA"
    if tipo == "contrato":
        return "II - DOS FUNDAMENTOS JURÍDICOS E DAS PREMISSAS CONTRATUAIS"
    return "II - DA FUNDAMENTAÇÃO JURÍDICA"


def _secao_fundamentacao_por_tipo(document_type: str, base_legal: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contestação":
        return (
            "À luz da narrativa inicial e dos elementos apresentados, a defesa poderá desenvolver, "
            "conforme pertinência, as seguintes teses e fundamentos:\n\n"
            f"{base_legal}"
        )

    if tipo == "réplica":
        return (
            "Em impugnação aos argumentos defensivos, a parte autora poderá reforçar a pretensão inicial "
            "com base nos seguintes fundamentos:\n\n"
            f"{base_legal}"
        )

    if tipo == "manifestação":
        return (
            "A presente manifestação poderá ser sustentada com base nos seguintes fundamentos jurídicos e processuais:\n\n"
            f"{base_legal}"
        )

    if tipo == "parecer jurídico":
        return (
            "A análise jurídica preliminar da matéria pode ser desenvolvida a partir das seguintes premissas, normas e interpretações:\n\n"
            f"{base_legal}"
        )

    if tipo == "contrato":
        return (
            "A estruturação da minuta deve observar as seguintes premissas legais, obrigações essenciais e critérios de equilíbrio contratual:\n\n"
            f"{base_legal}"
        )

    if tipo == "notificação extrajudicial":
        return (
            "A exigência formulada por meio da presente notificação pode ser amparada nos seguintes fundamentos:\n\n"
            f"{base_legal}"
        )

    if tipo == "recurso":
        return (
            "A insurgência recursal poderá ser construída com base nos seguintes fundamentos jurídicos:\n\n"
            f"{base_legal}"
        )

    return base_legal


def _titulo_secao_estrategica_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "III - DA ESTRUTURA DE ANÁLISE"
    if tipo == "contrato":
        return "III - DA ORGANIZAÇÃO DA MINUTA"
    if tipo == "notificação extrajudicial":
        return "III - DA ORGANIZAÇÃO DA COMUNICAÇÃO"
    if tipo == "recurso":
        return "III - DA ESTRUTURA RECURSAL"
    return "III - DA ESTRUTURA SUGERIDA"


def _texto_secao_estrategica_por_tipo(document_type: str, estrutura_tipo: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        prefixo = (
            "Para melhor organização da peça e adequada apresentação da pretensão, recomenda-se observar a seguinte estrutura:"
        )
    elif tipo == "contestação":
        prefixo = (
            "Para melhor sistematização da defesa, sugere-se observar a seguinte estrutura:"
        )
    elif tipo == "réplica":
        prefixo = (
            "Para adequada impugnação da defesa e reforço da tese autoral, sugere-se observar a seguinte estrutura:"
        )
    elif tipo == "manifestação":
        prefixo = (
            "Para melhor objetividade e adequação ao momento processual, sugere-se adotar a seguinte estrutura:"
        )
    elif tipo == "parecer jurídico":
        prefixo = (
            "Para construção de conclusão técnica consistente, recomenda-se observar as seguintes premissas estruturais:"
        )
    elif tipo == "contrato":
        prefixo = (
            "Para organização clara do instrumento contratual, com definição equilibrada de direitos e obrigações, "
            "recomenda-se observar a seguinte estrutura:"
        )
    elif tipo == "notificação extrajudicial":
        prefixo = (
            "Para assegurar clareza e efetividade à comunicação formal, recomenda-se observar a seguinte organização:"
        )
    elif tipo == "recurso":
        prefixo = (
            "Para adequada formulação da insurgência recursal, recomenda-se estruturar a peça segundo os seguintes elementos:"
        )
    else:
        prefixo = "Para fins de organização e revisão, recomenda-se observar a seguinte estrutura:"

    return f"{prefixo}\n\n{estrutura_tipo}"


def _titulo_secao_final_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contrato":
        return "IV - DAS CLÁUSULAS E CONDIÇÕES ESSENCIAIS"
    if tipo == "parecer jurídico":
        return "IV - DA CONCLUSÃO"
    if tipo == "notificação extrajudicial":
        return "IV - DA PROVIDÊNCIA EXIGIDA"
    return "IV - DOS PEDIDOS"


def _introducao_secao_final_por_tipo(document_type: str, request_intro: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contestação":
        return "Diante do exposto, requer a parte demandada:"
    if tipo == "réplica":
        return "Diante do exposto, requer a parte autora:"
    if tipo == "manifestação":
        return "Ante o exposto, requer-se:"
    if tipo == "parecer jurídico":
        return "À vista do exposto, conclui-se:"
    if tipo == "contrato":
        return "As cláusulas e condições essenciais podem ser organizadas nos seguintes termos:"
    if tipo == "notificação extrajudicial":
        return "Diante do exposto, fica a parte notificada cientificada para:"
    if tipo == "recurso":
        return "Diante do exposto, requer o recorrente:"
    return request_intro


def _conteudo_secao_final_por_tipo(document_type: str, requests: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return (
            "Os pedidos devem guardar correspondência direta com os fatos narrados e com a tutela pretendida, "
            "podendo ser organizados da seguinte forma:\n\n"
            f"{requests}"
        )

    if tipo == "contestação":
        return (
            "Os requerimentos defensivos podem ser organizados de forma a contemplar, conforme o caso, "
            "preliminares, improcedência, produção probatória e demais consequências jurídicas pertinentes:\n\n"
            f"{requests}"
        )

    if tipo == "réplica":
        return (
            "A parte autora pode, nesta fase, ratificar a pretensão inicial, impugnar teses defensivas e requerer o prosseguimento do feito nos seguintes termos:\n\n"
            f"{requests}"
        )

    if tipo == "manifestação":
        return (
            "Os requerimentos da presente manifestação podem ser estruturados da seguinte forma, em consonância com o objetivo processual desta peça:\n\n"
            f"{requests}"
        )

    if tipo == "parecer jurídico":
        return (
            "Com base nos elementos analisados, a conclusão jurídica preliminar pode ser sintetizada nos seguintes termos:\n\n"
            f"{requests}"
        )

    if tipo == "contrato":
        return (
            "Considerando o objeto do ajuste, as cláusulas e condições essenciais podem ser organizadas da seguinte forma:\n\n"
            f"{requests}"
        )

    if tipo == "notificação extrajudicial":
        return (
            "A providência esperada da parte notificada pode ser delimitada, de forma clara e objetiva, nos seguintes termos:\n\n"
            f"{requests}"
        )

    if tipo == "recurso":
        return (
            "O pedido recursal pode ser estruturado com foco na revisão da decisão impugnada e nos efeitos pretendidos, nos seguintes termos:\n\n"
            f"{requests}"
        )

    return requests


def _secao_final_estilo(tom: str, observacoes_estilo: str, expressoes: str) -> str:
    return (
        "V - OBSERVAÇÕES FINAIS DE ESTILO\n\n"
        f"- tom predominante: {tom}\n"
        f"- observações de estilo: {observacoes_estilo}\n"
        f"- expressões recorrentes sugeridas: {expressoes}"
    )


def _fechamento_por_tipo(document_type: str, fechamento_padrao: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "É o parecer, s.m.j."
    if tipo == "contrato":
        return "E, por estarem assim ajustadas, as partes poderão firmar o instrumento correspondente."
    if tipo == "notificação extrajudicial":
        return "Sem mais para o momento, firma-se a presente para os fins de direito."
    if tipo == "recurso":
        return "Nesses termos, requer o recorrente o regular processamento do recurso."
    return fechamento_padrao


def gerar_rascunho_juridico(
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    context_used: str,
    writing_profile=None,
    documentos_selecionados: list | None = None,
) -> str:
    base_legal = (
        legal_basis.strip()
        if legal_basis
        else "A fundamentação jurídica específica deverá ser aprofundada conforme a legislação aplicável, a jurisprudência pertinente e a estratégia processual adotada."
    )

    titulo_documento = _titulo_documento(document_type)
    estrutura_tipo = _bloco_estrutura_por_tipo(document_type)
    introducao_especifica = _introducao_especifica_por_tipo(document_type, case_subject)

    tom = "Formal"
    qualificacao = _qualificacao_base_por_tipo(document_type)
    abertura = _abertura_base_por_tipo(document_type)
    fechamento = "Termos em que,\nPede deferimento."
    introducao_pedidos_padrao = "Diante do exposto, requer:"
    observacoes_estilo = "Utilizar linguagem jurídica formal, objetiva e técnica."
    expressoes = "data venia; conforme entendimento jurisprudencial; nos termos da legislação aplicável"
    advogado = ""
    escritorio = ""

    if writing_profile:
        tom = writing_profile.tone or tom
        qualificacao = writing_profile.qualification_style or qualificacao
        abertura = writing_profile.opening_phrase or abertura
        fechamento = writing_profile.closing_phrase or fechamento
        introducao_pedidos_padrao = writing_profile.request_intro or introducao_pedidos_padrao
        observacoes_estilo = writing_profile.legal_style_notes or observacoes_estilo
        expressoes = writing_profile.recurring_expressions or expressoes
        advogado = writing_profile.lawyer_name or ""
        escritorio = writing_profile.office_name or ""

    titulo_fatos = _titulo_secao_fatos_por_tipo(document_type)
    conteudo_fatos = _conteudo_secao_fatos_por_tipo(document_type, facts)

    titulo_fundamentacao = _titulo_secao_fundamentacao_por_tipo(document_type)
    conteudo_fundamentacao = _secao_fundamentacao_por_tipo(document_type, base_legal)

    titulo_estrategico = _titulo_secao_estrategica_por_tipo(document_type)
    conteudo_estrategico = _texto_secao_estrategica_por_tipo(document_type, estrutura_tipo)

    titulo_final = _titulo_secao_final_por_tipo(document_type)
    introducao_final = _introducao_secao_final_por_tipo(document_type, introducao_pedidos_padrao)
    conteudo_final = _conteudo_secao_final_por_tipo(document_type, requests)

    fechamento_final = _fechamento_por_tipo(document_type, fechamento)

    assinatura_bloco = []
    if advogado:
        assinatura_bloco.append(advogado)
    if escritorio:
        assinatura_bloco.append(escritorio)

    assinatura_final = "\n".join(assinatura_bloco)

    texto = f"""
{titulo_documento}

Cliente:
{client_name}

Tipo de documento:
{document_type}

Assunto do caso:
{case_subject}

{qualificacao}, {abertura}

{introducao_especifica}

{titulo_fatos}

{conteudo_fatos}

{titulo_fundamentacao}

{conteudo_fundamentacao}

{titulo_estrategico}

{conteudo_estrategico}

{titulo_final}

{introducao_final}

{conteudo_final}

{_secao_final_estilo(tom, observacoes_estilo, expressoes)}

{fechamento_final}
""".strip()

    if assinatura_final:
        texto += f"\n\n{assinatura_final}"

    return texto


def gerar_docx_da_geracao(geracao: Generation) -> bytes:
    documento = DocxDocument()

    estilo_normal = documento.styles["Normal"]
    estilo_normal.font.name = "Times New Roman"
    estilo_normal.font.size = Pt(12)

    titulo = documento.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_titulo = titulo.add_run(geracao.document_type or "Minuta Jurídica")
    run_titulo.bold = True
    run_titulo.font.name = "Times New Roman"
    run_titulo.font.size = Pt(14)

    subtitulo = documento.add_paragraph()
    subtitulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_subtitulo = subtitulo.add_run(f"Cliente: {geracao.client_name}")
    run_subtitulo.italic = True
    run_subtitulo.font.name = "Times New Roman"
    run_subtitulo.font.size = Pt(11)

    documento.add_paragraph("")

    blocos = [bloco.strip() for bloco in (geracao.generated_text or "").split("\n\n") if bloco.strip()]

    for bloco in blocos:
        paragrafo = documento.add_paragraph()
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = paragrafo.add_run(bloco)
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
        paragrafo.paragraph_format.space_after = Pt(10)
        paragrafo.paragraph_format.first_line_indent = Pt(24)

    buffer = BytesIO()
    documento.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()