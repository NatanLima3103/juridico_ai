document.addEventListener("DOMContentLoaded", function () {
    inicializarSeletorDocumentos();
    inicializarAlertas();
    inicializarLoading();
    inicializarConfirmacoes();
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

    const mensagem = form.dataset.loadingMessage || "Aguarde um instante...";
    const botao = form.querySelector('[type="submit"]');
    const botaoTextoLoading = form.dataset.loadingButtonText || "Processando...";

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
    texto.textContent = "Aguarde um instante...";
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