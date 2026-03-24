from io import BytesIO

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
            "- razões recursais;\n"
            "- pedido de reforma, anulação ou adequação;\n"
            "- requerimentos finais."
        )

    return (
        "- contextualização do caso;\n"
        "- exposição dos fatos;\n"
        "- fundamentação;\n"
        "- pedidos ou conclusões;\n"
        "- fechamento formal."
    )


def _introducao_especifica_por_tipo(document_type: str, case_subject: str) -> str:
    tipo = _tipo_normalizado(document_type)
    assunto = (case_subject or "").strip()

    if tipo == "petição inicial":
        return (
            f"Trata-se de minuta de petição inicial relacionada ao caso envolvendo {assunto}, "
            "estruturada para viabilizar a formulação da pretensão em juízo, com exposição clara dos fatos, "
            "adequada correlação entre causa de pedir e pedidos, e linguagem técnica compatível com a fase inaugural da demanda."
        )

    if tipo == "contestação":
        return (
            f"Cuida-se de minuta de contestação referente ao litígio relativo a {assunto}, "
            "voltada à apresentação de defesa técnica, com enfoque na impugnação específica dos fatos, "
            "na resistência à pretensão adversa e na construção de argumentos aptos a conduzir à improcedência total ou parcial do pedido."
        )

    if tipo == "réplica":
        return (
            f"Trata-se de minuta de réplica relacionada ao caso envolvendo {assunto}, "
            "elaborada para enfrentar os argumentos defensivos lançados em contestação, reforçar a narrativa inicial "
            "e demonstrar a manutenção da procedência da pretensão deduzida pela parte autora."
        )

    if tipo == "manifestação":
        return (
            f"Cuida-se de minuta de manifestação processual sobre {assunto}, "
            "estruturada para expor, de forma objetiva e técnica, esclarecimentos, posicionamentos e requerimentos "
            "compatíveis com o momento processual e com a necessidade específica do caso concreto."
        )

    if tipo == "parecer jurídico":
        return (
            f"Trata-se de minuta de parecer jurídico acerca da matéria {assunto}, "
            "elaborada para examinar tecnicamente os fatos apresentados, a legislação aplicável e os riscos ou consequências jurídicas pertinentes, "
            "com conclusão opinativa fundamentada."
        )

    if tipo == "contrato":
        return (
            f"Trata-se de minuta contratual relativa ao objeto {assunto}, "
            "desenvolvida para formalizar de maneira clara e organizada as obrigações, responsabilidades, condições e salvaguardas essenciais do ajuste pretendido."
        )

    if tipo == "notificação extrajudicial":
        return (
            f"Cuida-se de minuta de notificação extrajudicial referente ao tema {assunto}, "
            "voltada à formalização de comunicação expressa, com delimitação objetiva dos fatos, do fundamento da exigência "
            "e da providência esperada da parte notificada."
        )

    if tipo == "recurso":
        return (
            f"Trata-se de minuta recursal relativa ao caso envolvendo {assunto}, "
            "estruturada para demonstrar o desacerto, vício ou inadequação da decisão impugnada, com apresentação de razões jurídicas aptas a justificar sua revisão."
        )

    return (
        f"Trata-se de minuta jurídica relacionada ao caso envolvendo {assunto}, "
        "elaborada com base nas informações fornecidas, para posterior revisão, complementação e adequação ao caso concreto."
    )


def _titulo_secao_fatos_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "I - DO RELATÓRIO"
    if tipo == "contrato":
        return "I - DA CONTEXTUALIZAÇÃO DO AJUSTE"
    if tipo == "recurso":
        return "I - DA SÍNTESE DA DEMANDA E DA DECISÃO RECORRIDA"
    return "I - DOS FATOS"


def _conteudo_secao_fatos_por_tipo(document_type: str, facts: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return (
            "Os fatos relevantes devem ser apresentados em sequência lógica, destacando a origem do conflito, "
            "a conduta das partes, as tentativas de solução prévia, quando existentes, e os prejuízos ou consequências jurídicas daí decorrentes.\n\n"
            f"{facts}"
        )

    if tipo == "contestação":
        return (
            "Para fins defensivos, os fatos narrados devem ser enfrentados sob a ótica da controvérsia instaurada, "
            "com impugnação específica dos pontos que não correspondam à realidade ou que demandem redimensionamento interpretativo.\n\n"
            f"{facts}"
        )

    if tipo == "réplica":
        return (
            "A presente réplica parte da necessidade de enfrentar os argumentos suscitados em contestação, "
            "preservando a coerência da narrativa inicial e enfatizando os fatos que sustentam a procedência da demanda.\n\n"
            f"{facts}"
        )

    if tipo == "manifestação":
        return (
            "Os fatos abaixo são expostos de forma objetiva, com foco estrito no ponto processual ou material que exige pronunciamento nesta etapa.\n\n"
            f"{facts}"
        )

    if tipo == "parecer jurídico":
        return (
            "Passa-se à síntese dos fatos submetidos à apreciação, tal como apresentados para análise, "
            "de modo a delimitar com precisão o objeto do parecer.\n\n"
            f"{facts}"
        )

    if tipo == "contrato":
        return (
            "O ajuste pretendido decorre do contexto fático abaixo resumido, que servirá de base para a organização das cláusulas e condições contratuais.\n\n"
            f"{facts}"
        )

    if tipo == "notificação extrajudicial":
        return (
            "Os fatos que ensejam a presente notificação podem ser assim resumidos, em ordem objetiva e suficiente para demonstrar a razão da comunicação formal.\n\n"
            f"{facts}"
        )

    if tipo == "recurso":
        return (
            "Para adequada compreensão das razões recursais, apresenta-se a síntese do caso, dos fatos relevantes e do contexto em que foi proferida a decisão combatida.\n\n"
            f"{facts}"
        )

    return facts


def _titulo_secao_fundamentacao_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "II - DA ANÁLISE JURÍDICA"
    if tipo == "contrato":
        return "II - DOS FUNDAMENTOS E DIRETRIZES DO AJUSTE"
    return "II - DA FUNDAMENTAÇÃO JURÍDICA"


def _secao_fundamentacao_por_tipo(document_type: str, base_legal: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        introducao = (
            "A pretensão deduzida deve ser examinada à luz do ordenamento jurídico aplicável, "
            "com observância da legislação incidente, dos princípios pertinentes e da adequada relação entre os fatos narrados e a tutela jurisdicional pretendida."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "contestação":
        introducao = (
            "A defesa deve ser construída de modo a demonstrar a improcedência, limitação, inadequação ou inaplicabilidade da pretensão adversa, "
            "com atenção à distribuição do ônus argumentativo e à coerência entre a narrativa defensiva e o regime jurídico aplicável."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "réplica":
        introducao = (
            "A presente réplica deve enfrentar, de maneira técnica e objetiva, os argumentos defensivos apresentados, "
            "reforçando os fundamentos da pretensão inicial, afastando teses contrárias e evidenciando eventual insuficiência das alegações da parte adversa."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "manifestação":
        introducao = (
            "A presente manifestação deve manter pertinência temática com o ponto submetido a exame, "
            "amparando-se no regime processual e material aplicável, com foco no requerimento ou esclarecimento que se pretende formular."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "parecer jurídico":
        introducao = (
            "A análise jurídica deve considerar os fatos apresentados, os dispositivos normativos pertinentes, "
            "a interpretação técnica adequada e os potenciais efeitos práticos da solução examinada."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "contrato":
        introducao = (
            "A estrutura contratual deve observar a autonomia privada, a boa-fé objetiva, a função social do contrato "
            "e os requisitos de validade, eficácia e equilíbrio do negócio jurídico correspondente."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "notificação extrajudicial":
        introducao = (
            "A presente notificação deve estar apoiada em base jurídica suficiente para demonstrar a legitimidade da exigência, "
            "cobrança, advertência ou providência pretendida, sempre com clareza e objetividade."
        )
        return f"{introducao}\n\n{base_legal}"

    if tipo == "recurso":
        introducao = (
            "A fundamentação recursal deve evidenciar o desacerto, vício, nulidade, omissão, contradição ou inadequação da decisão impugnada, "
            "conforme a espécie recursal e os limites da insurgência deduzida."
        )
        return f"{introducao}\n\n{base_legal}"

    return base_legal


def _titulo_secao_estrategica_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return "III - DA ESTRUTURA RECOMENDADA DA PRETENSÃO"
    if tipo == "contestação":
        return "III - DA ESTRATÉGIA DEFENSIVA RECOMENDADA"
    if tipo == "réplica":
        return "III - DOS PONTOS A SEREM IMPUGNADOS"
    if tipo == "manifestação":
        return "III - DO ENCAMINHAMENTO PROCESSUAL"
    if tipo == "parecer jurídico":
        return "III - DAS PREMISSAS PARA A CONCLUSÃO"
    if tipo == "contrato":
        return "III - DA ESTRUTURA CONTRATUAL RECOMENDADA"
    if tipo == "notificação extrajudicial":
        return "III - DA ESTRUTURA RECOMENDADA DA NOTIFICAÇÃO"
    if tipo == "recurso":
        return "III - DAS RAZÕES RECURSAIS ESSENCIAIS"
    return "III - DA ESTRUTURA RECOMENDADA PARA A PEÇA"


def _texto_secao_estrategica_por_tipo(document_type: str, estrutura_tipo: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        prefixo = (
            "Para elaboração consistente da peça inicial, recomenda-se organizar a narrativa e os fundamentos "
            "em torno dos seguintes elementos estruturais:"
        )
    elif tipo == "contestação":
        prefixo = (
            "Para construção de defesa sólida, recomenda-se observar a seguinte linha estrutural, "
            "com foco em impugnação, coerência defensiva e delimitação da resistência à pretensão:"
        )
    elif tipo == "réplica":
        prefixo = (
            "Para adequada réplica à defesa apresentada, recomenda-se concentrar a argumentação nos seguintes pontos:"
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