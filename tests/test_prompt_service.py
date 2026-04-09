import unittest

from app.services.prompt_service import build_advanced_prompt


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


if __name__ == "__main__":
    unittest.main()
