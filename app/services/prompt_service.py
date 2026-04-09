from __future__ import annotations

import re
from typing import Any

MAX_DOC_SNIPPETS = 3
MAX_SNIPPET_CHARS = 420
MAX_CONTEXT_CHARS = 1800
MAX_DOC_PASSAGES = 2
MAX_DOC_PASSAGE_CHARS = 700

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "um", "uma", "uns", "umas", "ao", "aos", "a", "as", "que", "se",
    "ja", "foi", "sao", "ser", "como", "mais", "menos", "sobre", "entre", "apos", "antes", "contra",
    "parte", "autor", "autora", "reu", "re", "caso", "fatos", "pedido", "pedidos", "juridica",
    "documento", "documentos", "minuta", "processo", "acao", "presente", "respectivamente",
}


def _normalize_spaces(text: str) -> str:
    return " ".join((text or "").split())


def _truncate(text: str, limit: int) -> str:
    clean = _normalize_spaces(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def _normalize_document_type(value: str) -> str:
    normalized = _normalize_spaces(value).lower()
    replacements = str.maketrans({
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    })
    return normalized.translate(replacements)


def _extract_keywords(*parts: str) -> list[str]:
    text = " ".join(_normalize_document_type(part) for part in parts if part)
    raw_tokens = re.findall(r"[a-z0-9]{4,}", text, flags=re.IGNORECASE)

    keywords: list[str] = []
    for token in raw_tokens:
        if token in STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:14]


def _score_sentence(sentence: str, keywords: list[str]) -> int:
    sentence_l = _normalize_document_type(sentence)
    score = 0
    for keyword in keywords:
        if keyword in sentence_l:
            score += 3
    score += min(len(sentence.split()) // 8, 3)
    return score


def _split_sentences(text: str) -> list[str]:
    clean = _normalize_spaces(text)
    if not clean:
        return []

    parts = re.split(r"(?<=[\.!?;:])\s+", clean)
    return [part.strip() for part in parts if part.strip()]


def _split_paragraphs(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n")
    raw_parts = [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
    paragraphs: list[str] = []

    for part in raw_parts:
        compact = _normalize_spaces(part)
        if not compact:
            continue
        if len(compact) <= MAX_DOC_PASSAGE_CHARS:
            paragraphs.append(compact)
            continue

        sentences = _split_sentences(compact)
        if not sentences:
            paragraphs.append(_truncate(compact, MAX_DOC_PASSAGE_CHARS))
            continue

        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > MAX_DOC_PASSAGE_CHARS:
                paragraphs.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            paragraphs.append(current)

    return paragraphs


def _select_relevant_snippets(text: str, keywords: list[str], *, max_snippets: int = MAX_DOC_SNIPPETS) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    scored = []
    for sentence in sentences:
        score = _score_sentence(sentence, keywords)
        scored.append((score, sentence))

    scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)

    chosen: list[str] = []
    for score, sentence in scored:
        if len(chosen) >= max_snippets:
            break
        if score <= 0 and chosen:
            continue
        snippet = _truncate(sentence, MAX_SNIPPET_CHARS)
        if snippet not in chosen:
            chosen.append(snippet)

    if not chosen:
        chosen.append(_truncate(sentences[0], MAX_SNIPPET_CHARS))

    return chosen


def _select_relevant_passages(text: str, keywords: list[str], *, max_passages: int = MAX_DOC_PASSAGES) -> list[str]:
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    scored: list[tuple[int, str]] = []
    for paragraph in paragraphs:
        score = _score_sentence(paragraph, keywords)
        if len(paragraph) > 280:
            score += 2
        scored.append((score, paragraph))

    scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)

    chosen: list[str] = []
    for score, paragraph in scored:
        if len(chosen) >= max_passages:
            break
        if score <= 0 and chosen:
            continue
        passage = _truncate(paragraph, MAX_DOC_PASSAGE_CHARS)
        if passage not in chosen:
            chosen.append(passage)

    if not chosen:
        chosen.append(_truncate(paragraphs[0], MAX_DOC_PASSAGE_CHARS))

    return chosen


def _build_profile_directives(profile: Any | None) -> str:
    if not profile:
        return "Nenhum perfil de escrita selecionado. Utilize linguagem juridica tecnica, clara e profissional."

    directives = [
        f"Nome do perfil: {getattr(profile, 'profile_name', '') or 'Sem nome'}",
        f"Tom predominante: {getattr(profile, 'tone', '') or 'Formal'}",
        f"Advogado responsavel: {getattr(profile, 'lawyer_name', '') or 'Nao informado'}",
        f"Escritorio: {getattr(profile, 'office_name', '') or 'Nao informado'}",
        f"Qualificacao preferida: {getattr(profile, 'qualification_style', '') or 'Nao informada'}",
        f"Abertura preferida: {getattr(profile, 'opening_phrase', '') or 'Nao informada'}",
        f"Introducao dos pedidos: {getattr(profile, 'request_intro', '') or 'Nao informada'}",
        f"Fechamento preferido: {getattr(profile, 'closing_phrase', '') or 'Nao informado'}",
        f"Observacoes de estilo: {getattr(profile, 'legal_style_notes', '') or 'Nao informado'}",
        f"Expressoes recorrentes: {getattr(profile, 'recurring_expressions', '') or 'Nao informado'}",
    ]
    return "\n".join(f"- {item}" for item in directives)


def _build_output_style_directives(profile: Any | None) -> str:
    if not profile:
        return "\n".join(
            [
                "- Utilize linguagem juridica tecnica, clara, profissional e pronta para revisao humana.",
                "- Mantenha tom formal e objetivo, sem floreios desnecessarios.",
                "- Use formulas de abertura, desenvolvimento e fechamento compativeis com a pratica forense brasileira.",
            ]
        )

    tone = getattr(profile, "tone", "") or "Formal"
    qualification_style = getattr(profile, "qualification_style", "") or "Nao informada"
    opening_phrase = getattr(profile, "opening_phrase", "") or "Nao informada"
    request_intro = getattr(profile, "request_intro", "") or "Nao informada"
    closing_phrase = getattr(profile, "closing_phrase", "") or "Nao informada"
    style_notes = getattr(profile, "legal_style_notes", "") or "Nao informado"
    recurring = getattr(profile, "recurring_expressions", "") or "Nao informado"

    directives = [
        "Use o perfil de escrita como estilo principal da saida final, e nao apenas como contexto auxiliar.",
        f"Adote o tom predominante '{tone}' ao longo da redacao.",
        f"Quando compativel com a peca, siga a qualificacao preferida: {qualification_style}.",
        f"Quando compativel com a abertura da peca, siga a frase de abertura preferida: {opening_phrase}.",
        f"Introduza os pedidos, quando existirem, com formula compativel com: {request_intro}.",
        f"Feche a minuta com formula compativel com: {closing_phrase}.",
        f"Observe como diretriz prioritaria de redacao: {style_notes}.",
        f"Use expressoes recorrentes do perfil apenas quando soarem naturais e uteis ao contexto: {recurring}.",
    ]
    return "\n".join(f"- {item}" for item in directives)


def _build_piece_specific_directives(document_type: str) -> str:
    normalized = _normalize_document_type(document_type)

    directives_map = {
        "peticao inicial": [
            "Organize a minuta com introducao compativel, fatos, fundamentos, pedidos e fechamento.",
            "Explicite a pretensao principal e, quando fizer sentido, pedidos acessorios e requerimentos de prova.",
            "Se houver urgencia indicada no contexto, trate a tutela provisoria com cautela e apenas se houver suporte fatico.",
        ],
        "contestacao": [
            "Estruture a defesa com sintese da demanda, preliminares apenas se houver base no contexto, merito e requerimentos finais.",
            "Priorize impugnacao especifica dos fatos, documentos e pedidos da parte autora, evitando negativas genericas.",
            "Se o contexto nao trouxer elemento para preliminar processual, concentre a redacao no merito defensivo.",
        ],
        "replica": [
            "Estruture a peca para responder a contestacao, enfrentando preliminares, prejudiciais e argumentos defensivos relevantes.",
            "Reforce a coerencia com a narrativa da inicial sem repetir trechos desnecessariamente.",
            "Mostre por que os argumentos da parte contraria nao afastam os fatos, fundamentos e pedidos ja formulados.",
        ],
        "manifestacao": [
            "Delimite com objetividade qual fato processual, documento, decisao ou andamento esta sendo enfrentado.",
            "Evite introducoes longas e conduza a peca para a providencia processual concreta pretendida.",
            "Mantenha a redacao focada no ponto controvertido e no pedido imediato ao juizo.",
        ],
        "parecer juridico": [
            "Estruture o texto em relatorio, analise juridica e conclusao, com natureza consultiva e tecnica.",
            "Apresente riscos, alternativas, condicionantes e grau de viabilidade sem tom de peticao judicial.",
            "Na conclusao, indique orientacao pratica objetiva e ressalve dependencias faticas quando necessario.",
        ],
        "contrato": [
            "Redija em formato contratual, com clausulas claras, numeradas e voltadas a executabilidade do ajuste.",
            "Inclua objeto, obrigacoes, prazo, remuneracao, rescisao, penalidades e foro apenas conforme compativeis com o contexto.",
            "Nao use linguagem de peticao ao juizo; trate as partes como contratantes e preserve clareza operacional.",
        ],
        "notificacao extrajudicial": [
            "Adote tom formal, direto e persuasivo, com narrativa objetiva do inadimplemento ou da irregularidade.",
            "Indique a providencia exigida, o prazo aplicavel se houver base no contexto e as consequencias do descumprimento.",
            "Evite pedidos tipicos de peca judicial e mantenha a finalidade de comunicacao formal e constituicao em mora.",
        ],
        "recurso": [
            "Estruture o texto com sintese da decisao recorrida, admissibilidade quando pertinente, razoes recursais e pedidos.",
            "Ataque especificamente os fundamentos da decisao, destacando erro de fato, de direito ou de valoracao probatoria quando houver suporte.",
            "Mencione efeitos recursais apenas se fizerem sentido diante do contexto apresentado.",
        ],
    }

    directives = directives_map.get(normalized, [
        "Adapte a estrutura a natureza da peca informada, com secoes coerentes e compativeis com a finalidade pratica do documento.",
        "Se o tipo de peca for incomum ou generico, privilegie clareza estrutural, fidelidade ao contexto e utilidade para revisao humana.",
        "Evite reproduzir modelos estanques quando o contexto apontar uma necessidade documental diferente.",
    ])

    return "\n".join(f"- {directive}" for directive in directives)


def build_smart_context(
    *,
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    writing_profile: Any | None,
    documentos_selecionados: list[Any] | None,
) -> str:
    keywords = _extract_keywords(document_type, case_subject, facts, requests, legal_basis)
    documentos = documentos_selecionados or []

    blocks: list[str] = []
    blocks.append("[RESUMO DO CASO]")
    blocks.append(f"Cliente: {client_name}")
    blocks.append(f"Tipo de peca: {document_type}")
    blocks.append(f"Assunto central: {_truncate(case_subject, 220)}")
    blocks.append(f"Fatos essenciais: {_truncate(facts, 480)}")
    blocks.append(f"Pedidos principais: {_truncate(requests, 320)}")
    blocks.append(
        "Fundamentacao inicial: " + (
            _truncate(legal_basis, 320)
            if legal_basis.strip()
            else "Nao informada pelo usuario; aprofundar conforme o caso."
        )
    )

    blocks.append("\n[PERFIL DE ESCRITA]")
    blocks.append(_build_profile_directives(writing_profile))

    blocks.append("\n[DOCUMENTOS BASE PRIORIZADOS]")
    if not documentos:
        blocks.append("Nenhum documento base selecionado.")
    else:
        for index, documento in enumerate(documentos, start=1):
            filename = getattr(documento, "original_filename", f"Documento {index}")
            file_type = getattr(documento, "file_type", "desconhecido")
            extracted_text = getattr(documento, "extracted_text", "") or ""
            snippets = _select_relevant_snippets(extracted_text, keywords)
            passages = _select_relevant_passages(extracted_text, keywords)

            bloco_doc = [
                f"Documento {index}: {filename}",
                f"Tipo: {file_type}",
                f"Tamanho textual aproximado: {len(_normalize_spaces(extracted_text))} caracteres",
            ]
            for snippet_index, snippet in enumerate(snippets, start=1):
                bloco_doc.append(f"Trecho relevante {snippet_index}: {snippet}")
            if passages:
                bloco_doc.append("Contexto documental prioritario:")
                for passage_index, passage in enumerate(passages, start=1):
                    bloco_doc.append(f"Excerto literal {passage_index}: {passage}")
            blocks.append("\n".join(bloco_doc))

    context = "\n".join(blocks).strip()
    return _truncate(context, MAX_CONTEXT_CHARS * 2)


def build_advanced_prompt(
    *,
    client_name: str,
    document_type: str,
    case_subject: str,
    facts: str,
    requests: str,
    legal_basis: str,
    smart_context: str,
    writing_profile: Any | None,
    documentos_selecionados: list[Any] | None,
) -> dict[str, str]:
    document_count = len(documentos_selecionados or [])
    style_note = getattr(writing_profile, "legal_style_notes", "") if writing_profile else ""
    recurring = getattr(writing_profile, "recurring_expressions", "") if writing_profile else ""
    piece_specific_directives = _build_piece_specific_directives(document_type)
    output_style_directives = _build_output_style_directives(writing_profile)

    system_prompt = (
        "Voce e um assistente juridico redator. Gere uma minuta juridica em portugues do Brasil, "
        "com estrutura compativel com o tipo de peca solicitado, redacao profissional, objetividade, "
        "coerencia interna e fidelidade ao contexto informado. Nao invente fatos. Nao cite jurisprudencia "
        "ou artigos especificos se eles nao tiverem sido informados. Quando a base juridica estiver generica, "
        "mantenha a redacao util e prudente, indicando fundamentos em tese, sem afirmar existencia de prova inexistente."
    )

    user_prompt = f"""
[TAREFA]
Redigir uma minuta juridica do tipo "{document_type}" para o cliente "{client_name}".

[OBJETIVO]
Produzir um texto juridicamente apresentavel, bem organizado e aderente ao assunto "{case_subject}".

[ENTRADAS PRINCIPAIS]
- Cliente: {client_name}
- Tipo de documento: {document_type}
- Assunto: {case_subject}
- Fatos: {facts}
- Pedidos: {requests}
- Fundamentacao juridica inicial: {legal_basis or 'Nao informada'}
- Quantidade de documentos base: {document_count}
- Observacoes de estilo prioritarias: {style_note or 'Manter estilo juridico formal e claro.'}
- Expressoes recorrentes preferenciais: {recurring or 'Usar somente quando fizer sentido ao contexto.'}

[REGRAS DE REDACAO]
1. Respeite a estrutura natural do tipo de peca.
2. Use os documentos base como contexto factual prioritario quando trouxerem informacoes especificas e compativeis com o caso.
3. Mantenha consistencia entre fatos, fundamentos e pedidos.
4. Evite linguagem excessivamente generica quando houver contexto suficiente.
5. Nao invente nomes, datas, provas ou acontecimentos nao informados.
6. Entregue o texto pronto para revisao humana.
7. Ao usar os documentos base, prefira os excertos literais e dados concretos extraidos deles, sem copiar trechos irrelevantes.

[ESTILO DE SAIDA]
{output_style_directives}

[DIRETRIZES ESPECIFICAS DO TIPO DE PECA]
{piece_specific_directives}

[CONTEXTO INTELIGENTE]
{smart_context}
""".strip()

    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }
