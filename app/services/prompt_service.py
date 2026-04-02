from __future__ import annotations

import re
from typing import Any

MAX_DOC_SNIPPETS = 3
MAX_SNIPPET_CHARS = 420
MAX_CONTEXT_CHARS = 1800

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "um", "uma", "uns", "umas", "ao", "aos", "à", "às", "que", "se",
    "já", "foi", "são", "ser", "como", "mais", "menos", "sobre", "entre", "após", "antes", "contra",
    "parte", "autor", "autora", "réu", "ré", "caso", "fatos", "pedido", "pedidos", "jurídica",
    "juridica", "documento", "documentos", "minuta", "processo", "ação", "acao", "presente", "respectivamente",
}


def _normalize_spaces(text: str) -> str:
    return " ".join((text or "").split())


def _truncate(text: str, limit: int) -> str:
    clean = _normalize_spaces(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def _extract_keywords(*parts: str) -> list[str]:
    text = " ".join(_normalize_spaces(part).lower() for part in parts if part)
    raw_tokens = re.findall(r"[a-zà-ú0-9]{4,}", text, flags=re.IGNORECASE)

    keywords: list[str] = []
    for token in raw_tokens:
        if token in STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:14]


def _score_sentence(sentence: str, keywords: list[str]) -> int:
    sentence_l = sentence.lower()
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


def _build_profile_directives(profile: Any | None) -> str:
    if not profile:
        return "Nenhum perfil de escrita selecionado. Utilize linguagem jurídica técnica, clara e profissional."

    directives = [
        f"Nome do perfil: {getattr(profile, 'profile_name', '') or 'Sem nome'}",
        f"Tom predominante: {getattr(profile, 'tone', '') or 'Formal'}",
        f"Advogado responsável: {getattr(profile, 'lawyer_name', '') or 'Não informado'}",
        f"Escritório: {getattr(profile, 'office_name', '') or 'Não informado'}",
        f"Qualificação preferida: {getattr(profile, 'qualification_style', '') or 'Não informada'}",
        f"Abertura preferida: {getattr(profile, 'opening_phrase', '') or 'Não informada'}",
        f"Introdução dos pedidos: {getattr(profile, 'request_intro', '') or 'Não informada'}",
        f"Fechamento preferido: {getattr(profile, 'closing_phrase', '') or 'Não informado'}",
        f"Observações de estilo: {getattr(profile, 'legal_style_notes', '') or 'Não informado'}",
        f"Expressões recorrentes: {getattr(profile, 'recurring_expressions', '') or 'Não informado'}",
    ]
    return "\n".join(f"- {item}" for item in directives)


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
    blocks.append(f"Tipo de peça: {document_type}")
    blocks.append(f"Assunto central: {_truncate(case_subject, 220)}")
    blocks.append(f"Fatos essenciais: {_truncate(facts, 480)}")
    blocks.append(f"Pedidos principais: {_truncate(requests, 320)}")
    blocks.append(
        "Fundamentação inicial: " + (
            _truncate(legal_basis, 320)
            if legal_basis.strip()
            else "Não informada pelo usuário; aprofundar conforme o caso."
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

            bloco_doc = [
                f"Documento {index}: {filename}",
                f"Tipo: {file_type}",
            ]
            for snippet_index, snippet in enumerate(snippets, start=1):
                bloco_doc.append(f"Trecho relevante {snippet_index}: {snippet}")
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

    system_prompt = (
        "Você é um assistente jurídico redator. Gere uma minuta jurídica em português do Brasil, "
        "com estrutura compatível com o tipo de peça solicitado, redação profissional, objetividade, "
        "coerência interna e fidelidade ao contexto informado. Não invente fatos. Não cite jurisprudência "
        "ou artigos específicos se eles não tiverem sido informados. Quando a base jurídica estiver genérica, "
        "mantenha a redação útil e prudente, indicando fundamentos em tese, sem afirmar existência de prova inexistente."
    )

    user_prompt = f"""
[TAREFA]
Redigir uma minuta jurídica do tipo "{document_type}" para o cliente "{client_name}".

[OBJETIVO]
Produzir um texto juridicamente apresentável, bem organizado e aderente ao assunto "{case_subject}".

[ENTRADAS PRINCIPAIS]
- Cliente: {client_name}
- Tipo de documento: {document_type}
- Assunto: {case_subject}
- Fatos: {facts}
- Pedidos: {requests}
- Fundamentação jurídica inicial: {legal_basis or 'Não informada'}
- Quantidade de documentos base: {document_count}
- Observações de estilo prioritárias: {style_note or 'Manter estilo jurídico formal e claro.'}
- Expressões recorrentes preferenciais: {recurring or 'Usar somente quando fizer sentido ao contexto.'}

[REGRAS DE REDAÇÃO]
1. Respeite a estrutura natural do tipo de peça.
2. Use os documentos base apenas como reforço contextual.
3. Mantenha consistência entre fatos, fundamentos e pedidos.
4. Evite linguagem excessivamente genérica quando houver contexto suficiente.
5. Não invente nomes, datas, provas ou acontecimentos não informados.
6. Entregue o texto pronto para revisão humana.

[CONTEXTO INTELIGENTE]
{smart_context}
""".strip()

    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }