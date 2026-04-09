import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import ai_generation_service
from app.services.generation_service import gerar_rascunho_juridico


class GenerationServiceStyleTests(unittest.TestCase):
    def test_local_draft_applies_opening_phrase_from_writing_profile(self):
        profile = SimpleNamespace(
            qualification_style="{cliente}, ja qualificado nos autos",
            opening_phrase="vem, respeitosamente, a presenca de Vossa Excelencia, apresentar a presente demanda:",
            request_intro="Diante do exposto, requer:",
            closing_phrase="Termos em que,\nPede deferimento.",
            lawyer_name="Maria Silva",
            office_name="Silva Advogados",
        )

        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            texto = gerar_rascunho_juridico(
                client_name="Cliente Teste",
                document_type="Peticao inicial",
                case_subject="Cobranca indevida",
                facts="O cliente sofreu cobranca indevida reiterada.",
                requests="Cancelamento da cobranca.\nCondenacao em danos morais.",
                legal_basis="Codigo Civil e Codigo de Defesa do Consumidor.",
                context_used="[RESUMO DO CASO]\nTeste",
                writing_profile=profile,
                documentos_selecionados=[],
            )

        self.assertIn(
            "Cliente Teste, ja qualificado nos autos, vem, respeitosamente, a presenca de Vossa Excelencia, apresentar a presente demanda:",
            texto,
        )
        self.assertIn("Diante do exposto, requer:", texto)
        self.assertIn("Maria Silva", texto)


if __name__ == "__main__":
    unittest.main()
