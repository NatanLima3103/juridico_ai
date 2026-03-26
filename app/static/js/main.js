document.addEventListener("DOMContentLoaded", function () {
    const selector = document.querySelector("[data-document-selector]");

    if (!selector) {
        return;
    }

    const checkboxes = selector.querySelectorAll("[data-document-checkbox]");
    const countElement = selector.querySelector("[data-selected-count]");
    const countLabelElement = selector.querySelector("[data-selected-count-label]");
    const labelElement = selector.querySelector("[data-selected-label]");

    function obterTextoSelecionados(totalSelecionados) {
        if (totalSelecionados === 1) {
            return "selecionado";
        }

        return "selecionados";
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
});