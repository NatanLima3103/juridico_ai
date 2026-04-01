from datetime import date, datetime, time, timedelta
from io import BytesIO

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from sqlalchemy import or_
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


def _parse_date_input(raw_value: str | None) -> date | None:
    valor = (raw_value or "").strip()

    if not valor:
        return None

    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalizar_filtros_listagem(
    search_term: str = "",
    document_type: str = "",
    writing_profile_id: int | None = None,
    sem_perfil: bool = False,
    client_name: str = "",
    case_subject: str = "",
    created_from: str = "",
    created_to: str = "",
    sort_by: str = "updated_desc",
) -> dict:
    opcoes_ordenacao = {
        "updated_desc",
        "updated_asc",
        "created_desc",
        "created_asc",
        "client_asc",
        "client_desc",
    }

    return {
        "search_term": (search_term or "").strip(),
        "document_type": (document_type or "").strip(),
        "writing_profile_id": writing_profile_id if isinstance(writing_profile_id, int) and writing_profile_id > 0 else None,
        "sem_perfil": bool(sem_perfil),
        "client_name": (client_name or "").strip(),
        "case_subject": (case_subject or "").strip(),
        "created_from": _parse_date_input(created_from),
        "created_to": _parse_date_input(created_to),
        "sort_by": sort_by if sort_by in opcoes_ordenacao else "updated_desc",
    }


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


def listar_geracoes(
    db: Session,
    *,
    search_term: str = "",
    document_type: str = "",
    writing_profile_id: int | None = None,
    sem_perfil: bool = False,
    client_name: str = "",
    case_subject: str = "",
    created_from: str = "",
    created_to: str = "",
    sort_by: str = "updated_desc",
) -> list[Generation]:
    filtros = normalizar_filtros_listagem(
        search_term=search_term,
        document_type=document_type,
        writing_profile_id=writing_profile_id,
        sem_perfil=sem_perfil,
        client_name=client_name,
        case_subject=case_subject,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
    )

    query = db.query(Generation).options(joinedload(Generation.writing_profile))

    if filtros["search_term"]:
        termo = f"%{filtros['search_term']}%"
        query = query.filter(
            or_(
                Generation.client_name.ilike(termo),
                Generation.document_type.ilike(termo),
                Generation.case_subject.ilike(termo),
                Generation.facts.ilike(termo),
                Generation.requests.ilike(termo),
                Generation.generated_text.ilike(termo),
            )
        )

    if filtros["client_name"]:
        query = query.filter(Generation.client_name.ilike(f"%{filtros['client_name']}%"))

    if filtros["case_subject"]:
        query = query.filter(Generation.case_subject.ilike(f"%{filtros['case_subject']}%"))

    if filtros["document_type"]:
        query = query.filter(Generation.document_type == filtros["document_type"])

    if filtros["sem_perfil"]:
        query = query.filter(Generation.writing_profile_id.is_(None))
    elif filtros["writing_profile_id"] is not None:
        query = query.filter(Generation.writing_profile_id == filtros["writing_profile_id"])

    if filtros["created_from"] is not None:
        data_inicio = datetime.combine(filtros["created_from"], time.min)
        query = query.filter(Generation.created_at >= data_inicio)

    if filtros["created_to"] is not None:
        proximo_dia = filtros["created_to"] + timedelta(days=1)
        data_limite = datetime.combine(proximo_dia, time.min)
        query = query.filter(Generation.created_at < data_limite)

    ordenacoes = {
        "updated_desc": [Generation.updated_at.desc(), Generation.created_at.desc()],
        "updated_asc": [Generation.updated_at.asc(), Generation.created_at.asc()],
        "created_desc": [Generation.created_at.desc(), Generation.updated_at.desc()],
        "created_asc": [Generation.created_at.asc(), Generation.updated_at.asc()],
        "client_asc": [Generation.client_name.asc(), Generation.created_at.desc()],
        "client_desc": [Generation.client_name.desc(), Generation.created_at.desc()],
    }

    return query.order_by(Generation.is_pinned.desc(), *ordenacoes[filtros["sort_by"]]).all()


def toggle_fixacao_geracao(db: Session, generation_id: int) -> Generation | None:
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        return None

    geracao.is_pinned = not bool(geracao.is_pinned)
    geracao.updated_at = agora_brasil()

    db.add(geracao)
    db.commit()
    db.refresh(geracao)
    return geracao


def buscar_geracao_por_id(db: Session, generation_id: int) -> Generation | None:
    return (
        db.query(Generation)
        .options(joinedload(Generation.writing_profile))
        .filter(Generation.id == generation_id)
        .first()
    )




def duplicar_geracao(db: Session, generation_id: int) -> Generation | None:
    geracao_origem = buscar_geracao_por_id(db, generation_id)

    if not geracao_origem:
        return None

    return criar_geracao(
        db=db,
        client_name=geracao_origem.client_name,
        document_type=geracao_origem.document_type,
        case_subject=geracao_origem.case_subject,
        facts=geracao_origem.facts,
        requests=geracao_origem.requests,
        legal_basis=geracao_origem.legal_basis or "",
        context_used=geracao_origem.context_used,
        generated_text=geracao_origem.generated_text,
        writing_profile_id=geracao_origem.writing_profile_id,
        source_document_ids=geracao_origem.source_document_ids,
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


def _limpar_pontuacao_final(texto: str) -> str:
    return (texto or "").strip().rstrip(".;:,")


def _primeira_frase(texto: str, limite: int = 220) -> str:
    texto_limpo = " ".join((texto or "").split())

    if not texto_limpo:
        return ""

    for separador in [". ", "; ", ": "]:
        if separador in texto_limpo:
            trecho = texto_limpo.split(separador)[0].strip()
            if trecho:
                return trecho[:limite].rstrip(".,;:") + "."

    if len(texto_limpo) <= limite:
        return texto_limpo.rstrip(".,;:") + "."

    return texto_limpo[:limite].rstrip(".,;:") + "..."


def _texto_em_linhas(texto: str) -> list[str]:
    linhas = []
    for linha in (texto or "").splitlines():
        linha_limpa = linha.strip()
        if linha_limpa:
            linhas.append(linha_limpa)
    return linhas


def _bulletizar_texto(texto: str) -> str:
    linhas = _texto_em_linhas(texto)

    if not linhas:
        texto_limpo = (texto or "").strip()
        return texto_limpo

    bullets = []
    for linha in linhas:
        bullets.append(f"- {_limpar_pontuacao_final(linha)};")

    if bullets:
        bullets[-1] = bullets[-1].rstrip(";") + "."

    return "\n".join(bullets)


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


def _qualificacao_base_por_tipo(document_type: str, client_name: str) -> str:
    tipo = _tipo_normalizado(document_type)
    cliente = (client_name or "").strip()

    if tipo == "contrato":
        return f"As partes interessadas, dentre elas {cliente}, de comum acordo,"
    if tipo == "parecer jurídico":
        return f"Em atenção à consulta formulada por {cliente},"
    if tipo == "notificação extrajudicial":
        return f"{cliente}, na qualidade de parte notificante,"
    return f"{cliente}, já devidamente qualificado(a),"


def _abertura_base_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "petição inicial":
        return "vem, respeitosamente, à presença de Vossa Excelência, propor a presente"
    if tipo == "contestação":
        return "vem, respeitosamente, à presença de Vossa Excelência, apresentar"
    if tipo == "réplica":
        return "vem, respeitosamente, à presença de Vossa Excelência, apresentar"
    if tipo == "manifestação":
        return "vem, respeitosamente, à presença de Vossa Excelência, apresentar a presente"
    if tipo == "parecer jurídico":
        return "apresentar o presente parecer jurídico"
    if tipo == "contrato":
        return "resolvem firmar a presente minuta contratual"
    if tipo == "notificação extrajudicial":
        return "vem, por meio da presente, promover a presente notificação extrajudicial"
    if tipo == "recurso":
        return "vem, respeitosamente, à presença de Vossa Excelência, interpor o presente"
    return "vem, respeitosamente, apresentar a presente minuta"


def _texto_parece_placeholder(texto: str) -> bool:
    texto_limpo = (texto or "").strip().lower()

    if not texto_limpo:
        return True

    marcadores_ruins = [
        "...",
        "já qualificado nos autos",
        "a presença de vossa",
        "diante do exposto, requer-se",
        "termos, em que",
        "peço, por gentileza",
        "peço, com a devida gentileza",
        "artigos, teses",
        "principais fatos do caso",
        "os principais fatos do caso são",
    ]

    return any(marcador in texto_limpo for marcador in marcadores_ruins)


def _texto_curto_demais(texto: str, minimo: int = 12) -> bool:
    return len((texto or "").strip()) < minimo


def _usar_texto_do_perfil(texto: str, minimo: int = 12) -> bool:
    if not texto:
        return False
    if _texto_curto_demais(texto, minimo=minimo):
        return False
    if _texto_parece_placeholder(texto):
        return False
    return True


def _introducao_especifica_por_tipo(document_type: str, case_subject: str, facts: str) -> str:
    tipo = _tipo_normalizado(document_type)
    assunto = _limpar_pontuacao_final(case_subject)

    if tipo == "petição inicial":
        return (
            f"A presente demanda decorre de {assunto.lower()}, "
            "conforme fatos e fundamentos a seguir expostos."
        )

    if tipo == "contestação":
        return (
            f"A presente defesa refere-se à controvérsia envolvendo {assunto.lower()}, "
            "passando-se à exposição das razões defensivas pertinentes."
        )

    if tipo == "réplica":
        return (
            f"Em atenção à controvérsia relativa a {assunto.lower()}, "
            "apresenta-se a presente réplica para impugnação dos argumentos defensivos."
        )

    if tipo == "manifestação":
        return (
            f"No contexto da matéria relativa a {assunto.lower()}, "
            "apresenta-se a presente manifestação para apreciação do ponto controvertido."
        )

    if tipo == "parecer jurídico":
        return (
            f"Submete-se à análise a questão jurídica relacionada a {assunto.lower()}, "
            "passando-se ao exame técnico da matéria."
        )

    if tipo == "contrato":
        return (
            f"A presente minuta tem por objeto disciplinar a relação jurídica referente a {assunto.lower()}, "
            "mediante a definição das cláusulas e condições essenciais do ajuste."
        )

    if tipo == "notificação extrajudicial":
        return (
            f"A presente notificação extrajudicial refere-se a {assunto.lower()}, "
            "para ciência formal da parte notificada e adoção das providências cabíveis."
        )

    if tipo == "recurso":
        return (
            f"O presente recurso decorre da controvérsia relativa a {assunto.lower()}, "
            "passando-se à exposição das razões recursais cabíveis."
        )

    return (
        f"A presente minuta refere-se à questão envolvendo {assunto.lower()}, "
        "conforme os elementos apresentados a seguir."
    )


def _titulo_secao_fatos_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "I - DO RELATÓRIO"
    if tipo == "contrato":
        return "I - DO CONTEXTO CONTRATUAL"
    return "I - DOS FATOS"


def _conteudo_secao_fatos_por_tipo(document_type: str, facts: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contrato":
        return (
            "Considerando o ajuste pretendido entre as partes, tem-se o seguinte contexto:\n\n"
            f"{facts}"
        )

    if tipo == "parecer jurídico":
        return (
            "Os fatos submetidos à análise podem ser assim resumidos:\n\n"
            f"{facts}"
        )

    if tipo == "notificação extrajudicial":
        return (
            "Os fatos que motivam a presente notificação podem ser descritos da seguinte forma:\n\n"
            f"{facts}"
        )

    return facts


def _titulo_secao_fundamentacao_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "II - DA ANÁLISE JURÍDICA"
    if tipo == "contrato":
        return "II - DOS FUNDAMENTOS JURÍDICOS"
    return "II - DA FUNDAMENTAÇÃO JURÍDICA"


def _secao_fundamentacao_por_tipo(document_type: str, base_legal: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contestação":
        return (
            "A defesa poderá ser sustentada pelos fundamentos jurídicos a seguir indicados:\n\n"
            f"{base_legal}"
        )

    if tipo == "réplica":
        return (
            "A parte autora poderá rebater os argumentos defensivos com apoio nos seguintes fundamentos:\n\n"
            f"{base_legal}"
        )

    if tipo == "manifestação":
        return (
            "A presente manifestação poderá ser amparada pelos seguintes fundamentos jurídicos e processuais:\n\n"
            f"{base_legal}"
        )

    if tipo == "parecer jurídico":
        return (
            "A análise da matéria pode ser desenvolvida a partir das seguintes premissas jurídicas:\n\n"
            f"{base_legal}"
        )

    if tipo == "contrato":
        return (
            "A elaboração da minuta deve observar os seguintes fundamentos e premissas jurídicas:\n\n"
            f"{base_legal}"
        )

    if tipo == "notificação extrajudicial":
        return (
            "A presente notificação encontra respaldo, em tese, nos seguintes fundamentos:\n\n"
            f"{base_legal}"
        )

    if tipo == "recurso":
        return (
            "A pretensão recursal poderá ser sustentada pelos seguintes fundamentos jurídicos:\n\n"
            f"{base_legal}"
        )

    if tipo == "petição inicial":
        return (
            "A pretensão deduzida encontra amparo, em tese, nos seguintes fundamentos jurídicos:\n\n"
            f"{base_legal}"
        )

    return base_legal


def _titulo_secao_final_por_tipo(document_type: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "contrato":
        return "III - DAS CLÁUSULAS ESSENCIAIS"
    if tipo == "parecer jurídico":
        return "III - DA CONCLUSÃO"
    if tipo == "notificação extrajudicial":
        return "III - DA PROVIDÊNCIA EXIGIDA"
    return "III - DOS PEDIDOS"


def _introducao_secao_final_por_tipo(document_type: str, request_intro: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "Diante do exposto, conclui-se que:"
    if tipo == "contrato":
        return "As cláusulas essenciais da presente minuta poderão contemplar:"
    if tipo == "notificação extrajudicial":
        return "Diante do exposto, fica a parte notificada instada a:"
    return request_intro


def _conteudo_secao_final_por_tipo(document_type: str, requests: str) -> str:
    return _bulletizar_texto(requests)


def _fechamento_por_tipo(document_type: str, fechamento_padrao: str) -> str:
    tipo = _tipo_normalizado(document_type)

    if tipo == "parecer jurídico":
        return "É o parecer, s.m.j."
    if tipo == "contrato":
        return "E, por estarem assim ajustadas, as partes poderão firmar o instrumento correspondente."
    if tipo == "notificação extrajudicial":
        return "Sem mais para o momento, firma-se a presente para os devidos fins de direito."
    if tipo == "recurso":
        return "Nesses termos, requer-se o regular processamento do recurso."
    return fechamento_padrao


def _cabecalho_contextual_por_tipo(
    document_type: str,
    case_subject: str,
    qualificacao: str,
    abertura: str,
) -> str:
    tipo = _tipo_normalizado(document_type)
    assunto = _limpar_pontuacao_final(case_subject)

    if tipo == "parecer jurídico":
        return (
            f"Assunto: {assunto}\n\n"
            f"{qualificacao}, passa a {abertura}, nos seguintes termos:"
        )

    if tipo == "contrato":
        return (
            f"{qualificacao}, tendo por objeto {assunto.lower()}, "
            f"{abertura}, mediante as cláusulas e condições a seguir:"
        )

    if tipo == "notificação extrajudicial":
        return (
            f"{qualificacao}, em razão de {assunto.lower()}, "
            f"{abertura}, nos seguintes termos:"
        )

    return f"{qualificacao} {abertura}, nos termos a seguir expostos:"


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
        else "A fundamentação jurídica específica deverá ser aprofundada conforme a legislação aplicável, a jurisprudência pertinente e a estratégia adotada para o caso concreto."
    )

    titulo_documento = _titulo_documento(document_type)
    introducao_especifica = _introducao_especifica_por_tipo(document_type, case_subject, facts)

    qualificacao = _qualificacao_base_por_tipo(document_type, client_name)
    abertura = _abertura_base_por_tipo(document_type)
    introducao_pedidos = "Diante do exposto, requer:"
    fechamento = "Termos em que,\nPede deferimento."

    advogado = ""
    escritorio = ""

    if writing_profile:
        texto_qualificacao = (writing_profile.qualification_style or "").strip()
        texto_abertura = (writing_profile.opening_phrase or "").strip()
        texto_pedidos = (writing_profile.request_intro or "").strip()
        texto_fechamento = (writing_profile.closing_phrase or "").strip()

        if _usar_texto_do_perfil(texto_qualificacao, minimo=18):
            qualificacao = f"{client_name}, {texto_qualificacao.rstrip(',')}"

        if _usar_texto_do_perfil(texto_abertura, minimo=20):
            abertura = texto_abertura.rstrip(" .,:;")

        if _usar_texto_do_perfil(texto_pedidos, minimo=12):
            introducao_pedidos = texto_pedidos.rstrip(" .,:;") + ":"

        if _usar_texto_do_perfil(texto_fechamento, minimo=12):
            fechamento = texto_fechamento

        advogado = (writing_profile.lawyer_name or "").strip()
        escritorio = (writing_profile.office_name or "").strip()

    titulo_fatos = _titulo_secao_fatos_por_tipo(document_type)
    conteudo_fatos = _conteudo_secao_fatos_por_tipo(document_type, facts)

    titulo_fundamentacao = _titulo_secao_fundamentacao_por_tipo(document_type)
    conteudo_fundamentacao = _secao_fundamentacao_por_tipo(document_type, base_legal)

    titulo_final = _titulo_secao_final_por_tipo(document_type)
    introducao_final = _introducao_secao_final_por_tipo(document_type, introducao_pedidos)
    conteudo_final = _conteudo_secao_final_por_tipo(document_type, requests)

    fechamento_final = _fechamento_por_tipo(document_type, fechamento)
    cabecalho_contextual = _cabecalho_contextual_por_tipo(
        document_type=document_type,
        case_subject=case_subject,
        qualificacao=qualificacao,
        abertura=abertura,
    )

    assinatura_bloco = []
    if advogado:
        assinatura_bloco.append(advogado)
    if escritorio:
        assinatura_bloco.append(escritorio)

    assinatura_final = "\n".join(assinatura_bloco)

    texto = f"""
{titulo_documento}

{cabecalho_contextual}

{introducao_especifica}

{titulo_fatos}

{conteudo_fatos}

{titulo_fundamentacao}

{conteudo_fundamentacao}

{titulo_final}

{introducao_final}

{conteudo_final}

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