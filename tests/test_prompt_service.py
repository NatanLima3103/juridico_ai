import unittest
from types import SimpleNamespace

from app.services.prompt_service import build_advanced_prompt, build_smart_context


class PromptServiceTests(unittest.TestCase):
    def _build_prompt(self, document_type: str) -> dict[str, str]:
        return build_advanced_prompt(
            client_name="Cliente Teste",
            document_type=document_type,
            case_subject="Cobranca indevida",
            facts="O cliente relata cobrancas sucessivas e tentativa previa de solucao.",
            requests="Cancelamento da cobranca e indenizacao.",
            legal_basis="Codigo Civil e Codigo de Defesa do Consumidor.",
            smart_context="[RESUMO DO CASO]\nTeste",
            writing_profile=None,
            documentos_selecionados=[],
        )

    def test_build_advanced_prompt_includes_specific_guidance_for_contestacao(self):
        prompt = self._build_prompt("Contestacao")

        self.assertIn("[DIRETRIZES ESPECIFICAS DO TIPO DE PECA]", prompt["user_prompt"])
        self.assertIn("impugnacao especifica dos fatos", prompt["user_prompt"])
        self.assertIn("merito defensivo", prompt["user_prompt"])

    def test_build_advanced_prompt_includes_specific_guidance_for_contrato(self):
        prompt = self._build_prompt("Contrato")

        self.assertIn("formato contratual", prompt["user_prompt"])
        self.assertIn("Nao use linguagem de peticao ao juizo", prompt["user_prompt"])

    def test_build_advanced_prompt_uses_generic_guidance_for_unknown_piece_type(self):
        prompt = self._build_prompt("Memorial descritivo juridico")

        self.assertIn("Adapte a estrutura a natureza da peca informada", prompt["user_prompt"])
        self.assertIn("Evite reproduzir modelos estanques", prompt["user_prompt"])

    def test_build_advanced_prompt_prioritizes_documental_context(self):
        prompt = self._build_prompt("Peticao inicial")

        self.assertIn(
            "Use os documentos base como contexto factual prioritario",
            prompt["user_prompt"],
        )
        self.assertIn(
            "prefira os excertos literais e dados concretos extraidos deles",
            prompt["user_prompt"],
        )

    def test_build_advanced_prompt_includes_legal_coherence_matrix_for_contestacao(self):
        prompt = self._build_prompt("Contestacao")

        self.assertIn("[MATRIZ DE COERENCIA JURIDICA]", prompt["user_prompt"])
        self.assertIn("tese central do caso", prompt["user_prompt"])
        self.assertIn("preserve a logica defensiva de rejeicao ou improcedencia", prompt["user_prompt"])

    def test_build_advanced_prompt_includes_consultive_coherence_for_parecer(self):
        prompt = self._build_prompt("Parecer juridico")

        self.assertIn("Converta os pedidos em conclusoes, riscos, alternativas ou recomendacoes praticas", prompt["user_prompt"])
        self.assertIn("A conclusao consultiva deve decorrer da analise dos fatos", prompt["user_prompt"])

    def test_build_advanced_prompt_includes_naturalness_guidance(self):
        prompt = self._build_prompt("Peticao inicial")

        self.assertIn("Escreva com naturalidade", prompt["system_prompt"])
        self.assertIn("evitando tom roboticamente padronizado", prompt["system_prompt"])
        self.assertIn("evitando repeticoes mecanicas", prompt["user_prompt"])
        self.assertIn("Evite expressoes excessivamente formularias", prompt["user_prompt"])
        self.assertIn("Priorize transicoes naturais entre paragrafos e secoes", prompt["user_prompt"])

    def test_build_advanced_prompt_uses_writing_profile_as_output_style(self):
        profile = SimpleNamespace(
            profile_name="Contencioso estrategico",
            tone="Objetivo",
            qualification_style="{cliente}, ja qualificado nos autos",
            opening_phrase="vem, com o devido respeito, apresentar a presente manifestacao",
            request_intro="Diante desse contexto, requer:",
            closing_phrase="Nesses termos, pede deferimento.",
            legal_style_notes="Priorizar linguagem tecnica e assertiva.",
            recurring_expressions="data venia; conforme se observa",
        )

        prompt = build_advanced_prompt(
            client_name="Cliente Teste",
            document_type="Manifestacao",
            case_subject="Cobranca indevida",
            facts="O cliente relata cobrancas sucessivas e tentativa previa de solucao.",
            requests="Cancelamento da cobranca e indenizacao.",
            legal_basis="Codigo Civil e Codigo de Defesa do Consumidor.",
            smart_context="[RESUMO DO CASO]\nTeste",
            writing_profile=profile,
            documentos_selecionados=[],
        )

        self.assertIn("[ESTILO DE SAIDA]", prompt["user_prompt"])
        self.assertIn("Use o perfil de escrita como estilo principal da saida final", prompt["user_prompt"])
        self.assertIn("frase de abertura preferida", prompt["user_prompt"])
        self.assertIn("Diante desse contexto, requer:", prompt["user_prompt"])
        self.assertIn("Nesses termos, pede deferimento.", prompt["user_prompt"])

    def test_build_smart_context_includes_real_document_excerpt(self):
        documento = SimpleNamespace(
            original_filename="contrato-base.pdf",
            file_type=".pdf",
            extracted_text=(
                "Contrato de prestacao de servicos firmado em 10/01/2026 entre as partes.\n\n"
                "A contratada assumiu a obrigacao de entregar relatorios mensais e suporte tecnico continuo, "
                "com prazo maximo de resposta de 24 horas para incidentes criticos.\n\n"
                "Em caso de inadimplemento, incide multa de 10 por cento sobre o valor mensal contratado."
            ),
        )

        context = build_smart_context(
            client_name="Cliente Teste",
            document_type="Contrato",
            case_subject="Prestacao de servicos com suporte tecnico",
            facts="Houve descumprimento contratual.",
            requests="Aplicacao de multa e rescisao.",
            legal_basis="Codigo Civil.",
            writing_profile=None,
            documentos_selecionados=[documento],
        )

        self.assertIn("Contexto documental prioritario:", context)
        self.assertIn("Excerto literal 1:", context)
        self.assertIn("prazo maximo de resposta de 24 horas", context)
        self.assertIn("multa de 10 por cento", context)


if __name__ == "__main__":
    unittest.main()
