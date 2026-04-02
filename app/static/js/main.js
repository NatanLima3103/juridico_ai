document.addEventListener("DOMContentLoaded", function () {
    inicializarSeletorDocumentos();
    inicializarAlertas();
    inicializarLoading();
    inicializarConfirmacoes();
    inicializarTemplatesJuridicos();
});

function inicializarSeletorDocumentos() {
    const selector = document.querySelector("[data-document-selector]");

    if (!selector) {
        return;
    }

    const checkboxes = selector.querySelectorAll("[data-document-checkbox]");
    const countElement = selector.querySelector("[data-selected-count]");
    const countLabelElement = selector.querySelector("[data-selected-count-label]");
    const labelElement = selector.querySelector("[data-selected-label]");

    function obterTextoSelecionados(totalSelecionados) {
        return totalSelecionados === 1 ? "selecionado" : "selecionados";
    }

    function obterTextoStatus(totalSelecionados) {
        if (totalSelecionados === 0) {
            return "Nenhum documento selecionado no momento.";
        }

        if (totalSelecionados === 1) {
            return "1 documento selecionado para compor a geração.";
        }

        return `${totalSelecionados} documentos selecionados para compor a geração.`;
    }

    function atualizarEstadoDocumentos() {
        let totalSelecionados = 0;

        checkboxes.forEach(function (checkbox) {
            const card = checkbox.closest("[data-document-card]");
            const marker = card ? card.querySelector("[data-marker]") : null;
            const badge = card ? card.querySelector("[data-selected-badge]") : null;

            if (checkbox.checked) {
                totalSelecionados += 1;

                if (card) {
                    card.classList.add("selecionado");
                }

                if (marker) {
                    marker.textContent = "✓ Documento marcado para uso";
                }

                if (badge) {
                    badge.classList.add("visivel");
                }
            } else {
                if (card) {
                    card.classList.remove("selecionado");
                }

                if (marker) {
                    marker.textContent = "Marcar este documento como base";
                }

                if (badge) {
                    badge.classList.remove("visivel");
                }
            }
        });

        if (countElement) {
            countElement.textContent = String(totalSelecionados);
        }

        if (countLabelElement) {
            countLabelElement.textContent = obterTextoSelecionados(totalSelecionados);
        }

        if (labelElement) {
            labelElement.textContent = obterTextoStatus(totalSelecionados);
        }
    }

    checkboxes.forEach(function (checkbox) {
        checkbox.addEventListener("change", atualizarEstadoDocumentos);
    });

    atualizarEstadoDocumentos();
}

function inicializarAlertas() {
    const alertas = document.querySelectorAll("[data-alerta]");

    alertas.forEach(function (alerta) {
        const fechar = alerta.querySelector("[data-fechar-alerta]");

        if (fechar) {
            fechar.addEventListener("click", function () {
                alerta.classList.add("alerta-saindo");

                window.setTimeout(function () {
                    alerta.remove();
                }, 180);
            });
        }
    });
}

function exibirLoading(form) {
    const overlay = document.getElementById("loading-overlay");
    const texto = document.getElementById("loading-texto");

    if (!overlay || !texto || !form) {
        return;
    }

    const mensagem = form.dataset.loadingMessage || "Aguarde um instante.";
    const botao = form.querySelector('[type="submit"]');
    const botaoTextoLoading = form.dataset.loadingButtonText || "Processando.";

    overlay.classList.add("ativo");
    overlay.setAttribute("aria-hidden", "false");
    texto.textContent = mensagem;

    if (botao) {
        botao.disabled = true;
        botao.innerHTML = `<span class="spinner-botao" aria-hidden="true"></span>${botaoTextoLoading}`;
    }
}

function esconderLoading() {
    const overlay = document.getElementById("loading-overlay");
    const texto = document.getElementById("loading-texto");

    if (!overlay || !texto) {
        return;
    }

    overlay.classList.remove("ativo");
    overlay.setAttribute("aria-hidden", "true");
    texto.textContent = "Aguarde um instante.";
}

function inicializarLoading() {
    const forms = document.querySelectorAll("form[data-loading-form]");

    if (forms.length === 0) {
        return;
    }

    forms.forEach(function (form) {
        form.addEventListener("submit", function () {
            if (form.hasAttribute("data-confirm-action")) {
                return;
            }

            exibirLoading(form);
        });
    });
}

function inicializarConfirmacoes() {
    const modal = document.getElementById("modal-confirmacao");
    const titulo = document.getElementById("modal-confirmacao-titulo");
    const mensagem = document.getElementById("modal-confirmacao-mensagem");
    const botaoConfirmar = document.getElementById("modal-confirmacao-confirmar");
    const botoesFechar = document.querySelectorAll("[data-confirm-close]");
    const gatilhos = document.querySelectorAll("form[data-confirm-action]");

    if (!modal || !titulo || !mensagem || !botaoConfirmar || gatilhos.length === 0) {
        return;
    }

    let formAtual = null;

    function abrirModal(formulario) {
        formAtual = formulario;
        titulo.textContent = formulario.dataset.confirmTitle || "Confirmar ação";
        mensagem.textContent = formulario.dataset.confirmMessage || "Deseja continuar com esta ação?";

        const icone = formulario.dataset.confirmSubmitIcon || '<span class="icone-botao" aria-hidden="true">🗑</span>';
        const label = formulario.dataset.confirmSubmitLabel || "Confirmar";

        botaoConfirmar.innerHTML = `${icone} ${label}`;

        modal.classList.add("ativo");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-aberto");
    }

    function fecharModal() {
        modal.classList.remove("ativo");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-aberto");
        formAtual = null;
    }

    gatilhos.forEach(function (formulario) {
        formulario.addEventListener("submit", function (event) {
            event.preventDefault();
            event.stopPropagation();
            abrirModal(formulario);
        });
    });

    botoesFechar.forEach(function (botao) {
        botao.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            fecharModal();
            esconderLoading();
        });
    });

    botaoConfirmar.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();

        if (!formAtual) {
            return;
        }

        const formularioParaEnviar = formAtual;

        fecharModal();
        exibirLoading(formularioParaEnviar);
        formularioParaEnviar.submit();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && modal.classList.contains("ativo")) {
            event.preventDefault();
            fecharModal();
            esconderLoading();
        }
    });
}

function inicializarTemplatesJuridicos() {
    const painel = document.querySelector("[data-template-panel]");
    const seletorTipo = document.querySelector("[data-template-document-type]");
    const botaoAplicar = document.querySelector("[data-template-apply]");
    const scriptTemplates = document.getElementById("templates-juridicos-data");

    if (!painel || !seletorTipo || !botaoAplicar || !scriptTemplates) {
        return;
    }

    let templates = {};

    try {
        templates = JSON.parse(scriptTemplates.textContent || "{}");
    } catch (error) {
        console.error("Não foi possível carregar os templates jurídicos.", error);
        return;
    }

    const campoAssunto = document.getElementById("case_subject");
    const campoFatos = document.getElementById("facts");
    const campoPedidos = document.getElementById("requests");
    const campoFundamentacao = document.getElementById("legal_basis");

    const titulo = painel.querySelector("[data-template-title]");
    const descricao = painel.querySelector("[data-template-description]");
    const assuntoPreview = painel.querySelector("[data-template-case-subject]");
    const fatosPreview = painel.querySelector("[data-template-facts]");
    const pedidosPreview = painel.querySelector("[data-template-requests]");
    const fundamentacaoPreview = painel.querySelector("[data-template-legal-basis]");

    function resumirTexto(texto, limite) {
        const textoLimpo = String(texto || "").trim();

        if (!textoLimpo) {
            return "—";
        }

        if (textoLimpo.length <= limite) {
            return textoLimpo;
        }

        return `${textoLimpo.slice(0, limite).trimEnd()}...`;
    }

    function atualizarPreview() {
        const tipoSelecionado = seletorTipo.value;
        const template = templates[tipoSelecionado];

        if (!template) {
            titulo.textContent = "Selecione um tipo para visualizar o modelo base";
            descricao.textContent = "Ao escolher um tipo de documento, você poderá aplicar um preenchimento inicial pronto e depois ajustar livremente.";
            assuntoPreview.textContent = "—";
            fatosPreview.textContent = "Selecione um tipo acima para visualizar um exemplo inicial.";
            pedidosPreview.textContent = "—";
            fundamentacaoPreview.textContent = "—";
            botaoAplicar.disabled = true;
            return;
        }

        titulo.textContent = template.titulo || "Template pronto";
        descricao.textContent = template.descricao || "";
        assuntoPreview.textContent = template.case_subject || "—";
        fatosPreview.textContent = resumirTexto(template.facts, 280);
        pedidosPreview.textContent = resumirTexto(template.requests, 240);
        fundamentacaoPreview.textContent = resumirTexto(template.legal_basis, 240);
        botaoAplicar.disabled = false;
    }

    function formularioTemConteudo() {
        return [campoAssunto, campoFatos, campoPedidos, campoFundamentacao].some(function (campo) {
            return campo && String(campo.value || "").trim() !== "";
        });
    }

    botaoAplicar.addEventListener("click", function () {
        const tipoSelecionado = seletorTipo.value;
        const template = templates[tipoSelecionado];

        if (!template) {
            return;
        }

        if (formularioTemConteudo()) {
            const confirmar = window.confirm("Os campos de assunto, fatos, pedidos e fundamentação serão substituídos pelo template selecionado. Deseja continuar?");
            if (!confirmar) {
                return;
            }
        }

        if (campoAssunto) {
            campoAssunto.value = template.case_subject || "";
        }

        if (campoFatos) {
            campoFatos.value = template.facts || "";
        }

        if (campoPedidos) {
            campoPedidos.value = template.requests || "";
        }

        if (campoFundamentacao) {
            campoFundamentacao.value = template.legal_basis || "";
        }
    });

    seletorTipo.addEventListener("change", atualizarPreview);
    atualizarPreview();
}