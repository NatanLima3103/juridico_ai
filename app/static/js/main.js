document.addEventListener("DOMContentLoaded", function () {
    inicializarSeletorDocumentos();
    inicializarAlertas();
    inicializarLoading();
    inicializarConfirmacoes();
    inicializarTemplatesJuridicos();
    inicializarCopiaTextoJuridico();
});

function inicializarSeletorDocumentos() {
    const checkboxes = document.querySelectorAll("[data-document-checkbox]");
    const countElement = document.querySelector("[data-document-counter]");

    if (checkboxes.length === 0 || !countElement) {
        return;
    }

    function atualizarEstadoDocumentos() {
        let totalSelecionados = 0;

        checkboxes.forEach(function (checkbox) {
            const card = checkbox.closest("[data-document-card]");

            if (checkbox.checked) {
                totalSelecionados += 1;

                if (card) {
                    card.classList.add("selecionado");
                }
            } else {
                if (card) {
                    card.classList.remove("selecionado");
                }
            }
        });

        countElement.textContent = `${totalSelecionados} selecionado(s)`;
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

function inicializarCopiaTextoJuridico() {
    const botaoCopiar = document.getElementById("botao-copiar-texto");
    const campoTexto = document.getElementById("texto-juridico");
    const mensagemCopia = document.getElementById("mensagem-copia");

    if (!botaoCopiar || !campoTexto) {
        return;
    }

    botaoCopiar.addEventListener("click", async function () {
        const texto = String(campoTexto.value || "").trim();

        if (!texto) {
            if (mensagemCopia) {
                mensagemCopia.textContent = "Não há texto para copiar.";
            }
            return;
        }

        try {
            await navigator.clipboard.writeText(texto);

            if (mensagemCopia) {
                mensagemCopia.textContent = "Texto copiado com sucesso.";
            }

            const textoOriginalBotao = botaoCopiar.innerHTML;
            botaoCopiar.innerHTML = '<span class="icone-botao" aria-hidden="true">✓</span> Copiado';

            window.setTimeout(function () {
                botaoCopiar.innerHTML = textoOriginalBotao;
            }, 1600);

            if (mensagemCopia) {
                window.setTimeout(function () {
                    mensagemCopia.textContent = "";
                }, 2200);
            }
        } catch (error) {
            console.error("Erro ao copiar o texto jurídico:", error);

            campoTexto.focus();
            campoTexto.select();

            try {
                const copiou = document.execCommand("copy");

                if (copiou) {
                    if (mensagemCopia) {
                        mensagemCopia.textContent = "Texto copiado com sucesso.";
                    }
                    return;
                }
            } catch (erroFallback) {
                console.error("Erro no fallback de cópia:", erroFallback);
            }

            if (mensagemCopia) {
                mensagemCopia.textContent = "Não foi possível copiar o texto automaticamente.";
            }
        }
    });
}