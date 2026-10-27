const ICONE_LIXEIRA = '<svg class="icone icone-sm" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';
const ICONE_CHECK = '<svg class="icone icone-sm" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"/></svg>';
const SELETOR_FOCAVEL = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

document.addEventListener("DOMContentLoaded", function () {
    inicializarTema();
    inicializarMenuUsuario();
    inicializarGaveta();
    inicializarRevelar();
    inicializarCampoArquivo();
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
                }, 200);
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
    let focoAnterior = null;

    function abrirModal(formulario) {
        focoAnterior = document.activeElement;
        formAtual = formulario;
        titulo.textContent = formulario.dataset.confirmTitle || "Confirmar ação";
        mensagem.textContent = formulario.dataset.confirmMessage || "Deseja continuar com esta ação?";

        const icone = formulario.dataset.confirmSubmitIcon || ICONE_LIXEIRA;
        const label = formulario.dataset.confirmSubmitLabel || "Confirmar";

        botaoConfirmar.innerHTML = `${icone} ${label}`;

        modal.classList.add("ativo");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-aberto");

        const botaoCancelar = modal.querySelector(".modal-confirmacao-acoes [data-confirm-close]");
        (botaoCancelar || botaoConfirmar).focus();
    }

    function fecharModal() {
        modal.classList.remove("ativo");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-aberto");
        formAtual = null;

        if (focoAnterior && typeof focoAnterior.focus === "function") {
            focoAnterior.focus();
        }
        focoAnterior = null;
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
        if (!modal.classList.contains("ativo")) {
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();
            fecharModal();
            esconderLoading();
        } else if (event.key === "Tab") {
            prenderFoco(modal.querySelector(".modal-confirmacao-card"), event);
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
            botaoCopiar.innerHTML = `${ICONE_CHECK} Copiado`;

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

/* Mantem o foco do teclado dentro de um container (modal, gaveta). */
function prenderFoco(container, event) {
    if (!container) {
        return;
    }

    const focaveis = Array.prototype.filter.call(
        container.querySelectorAll(SELETOR_FOCAVEL),
        function (elemento) {
            return elemento.offsetParent !== null;
        }
    );

    if (focaveis.length === 0) {
        event.preventDefault();
        return;
    }

    const primeiro = focaveis[0];
    const ultimo = focaveis[focaveis.length - 1];

    if (event.shiftKey && document.activeElement === primeiro) {
        event.preventDefault();
        ultimo.focus();
    } else if (!event.shiftKey && document.activeElement === ultimo) {
        event.preventDefault();
        primeiro.focus();
    }
}

/* Alterna o tema: automatico (sistema) -> claro -> escuro. */
function inicializarTema() {
    const botao = document.querySelector("[data-tema-alternar]");
    const raiz = document.documentElement;
    const CHAVE = "juridico-tema";
    const ORDEM = ["system", "light", "dark"];
    const ROTULOS = {
        system: "Tema: automático",
        light: "Tema: claro",
        dark: "Tema: escuro",
    };

    if (!botao) {
        return;
    }

    function temaAtual() {
        const tema = raiz.getAttribute("data-theme");
        return tema === "light" || tema === "dark" ? tema : "system";
    }

    function aplicar(tema, salvar) {
        if (tema === "system") {
            raiz.removeAttribute("data-theme");
        } else {
            raiz.setAttribute("data-theme", tema);
        }

        botao.dataset.estado = tema;
        botao.setAttribute("aria-label", `${ROTULOS[tema]}. Clique para alterar.`);
        botao.setAttribute("title", ROTULOS[tema]);

        if (!salvar) {
            return;
        }

        try {
            if (tema === "system") {
                window.localStorage.removeItem(CHAVE);
            } else {
                window.localStorage.setItem(CHAVE, tema);
            }
        } catch (erro) {
            /* Armazenamento indisponivel (modo privado): o tema vale so nesta pagina. */
        }
    }

    botao.hidden = false;
    aplicar(temaAtual(), false);

    botao.addEventListener("click", function () {
        const proximo = ORDEM[(ORDEM.indexOf(temaAtual()) + 1) % ORDEM.length];
        aplicar(proximo, true);
    });
}

/* Menu do usuario em <details>: fecha ao clicar fora e com Esc. */
function inicializarMenuUsuario() {
    const menus = document.querySelectorAll("[data-menu-usuario]");

    if (menus.length === 0) {
        return;
    }

    document.addEventListener("click", function (event) {
        menus.forEach(function (menu) {
            if (menu.open && !menu.contains(event.target)) {
                menu.open = false;
            }
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }

        menus.forEach(function (menu) {
            if (menu.open) {
                menu.open = false;
                menu.querySelector("summary").focus();
            }
        });
    });
}

/* Gaveta de navegacao no celular. */
function inicializarGaveta() {
    const gaveta = document.querySelector("[data-gaveta]");
    const botaoAbrir = document.querySelector("[data-gaveta-abrir]");

    if (!gaveta || !botaoAbrir) {
        return;
    }

    const painel = gaveta.querySelector(".gaveta-painel");
    const botoesFechar = gaveta.querySelectorAll("[data-gaveta-fechar]");
    let temporizador = null;

    botaoAbrir.hidden = false;

    function abrir() {
        window.clearTimeout(temporizador);
        gaveta.hidden = false;
        document.body.classList.add("modal-aberto");
        botaoAbrir.setAttribute("aria-expanded", "true");

        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                gaveta.classList.add("aberta");
            });
        });

        const primeiro = painel.querySelector(SELETOR_FOCAVEL);
        if (primeiro) {
            primeiro.focus();
        }
    }

    function fechar(devolverFoco) {
        gaveta.classList.remove("aberta");
        botaoAbrir.setAttribute("aria-expanded", "false");
        document.body.classList.remove("modal-aberto");

        temporizador = window.setTimeout(function () {
            gaveta.hidden = true;
        }, 250);

        if (devolverFoco) {
            botaoAbrir.focus();
        }
    }

    botaoAbrir.addEventListener("click", abrir);

    botoesFechar.forEach(function (botao) {
        botao.addEventListener("click", function () {
            fechar(true);
        });
    });

    gaveta.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            event.preventDefault();
            fechar(true);
        } else if (event.key === "Tab") {
            prenderFoco(painel, event);
        }
    });

    /* Ao voltar para a largura de desktop, a gaveta deixa de fazer sentido. */
    window.matchMedia("(min-width: 901px)").addEventListener("change", function (consulta) {
        if (consulta.matches && !gaveta.hidden) {
            fechar(false);
        }
    });
}

/* Entrada suave (fade + leve subida) de secoes marcadas com data-revelar. */
function inicializarRevelar() {
    const elementos = document.querySelectorAll("[data-revelar]");

    if (elementos.length === 0) {
        return;
    }

    const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduzirMovimento || !("IntersectionObserver" in window)) {
        elementos.forEach(function (elemento) {
            elemento.classList.add("revelado");
        });
        return;
    }

    const observador = new IntersectionObserver(function (entradas) {
        entradas.forEach(function (entrada) {
            if (entrada.isIntersecting) {
                entrada.target.classList.add("revelado");
                observador.unobserve(entrada.target);
            }
        });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });

    elementos.forEach(function (elemento) {
        observador.observe(elemento);
    });
}

/* Area de arrastar e soltar: o input[type=file] real continua fazendo o envio. */
function inicializarCampoArquivo() {
    const campos = document.querySelectorAll(".campo-arquivo");

    campos.forEach(function (campo) {
        const input = campo.querySelector('input[type="file"]');
        const nome = campo.querySelector("[data-arquivo-nome]");

        if (!input) {
            return;
        }

        function atualizarNome() {
            if (!nome) {
                return;
            }

            const arquivos = Array.prototype.map.call(input.files || [], function (arquivo) {
                return arquivo.name;
            });

            nome.textContent = arquivos.join(", ");
            nome.hidden = arquivos.length === 0;
        }

        ["dragenter", "dragover"].forEach(function (tipo) {
            campo.addEventListener(tipo, function () {
                campo.classList.add("arrastando");
            });
        });

        ["dragleave", "drop"].forEach(function (tipo) {
            campo.addEventListener(tipo, function () {
                campo.classList.remove("arrastando");
            });
        });

        input.addEventListener("change", atualizarNome);
        atualizarNome();
    });
}
