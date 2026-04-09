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

    def test_local_draft_uses_more_natural_intro_for_manifestacao(self):
        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            texto = gerar_rascunho_juridico(
                client_name="Cliente Teste",
                document_type="Manifestação",
                case_subject="juntada de comprovante de pagamento",
                facts="A parte apresenta o comprovante para demonstrar o adimplemento.",
                requests="Seja recebida a presente manifestação.",
                legal_basis="CPC e princípios da cooperação processual.",
                context_used="[RESUMO DO CASO]\nTeste",
                writing_profile=None,
                documentos_selecionados=[],
            )

        self.assertIn(
            "A manifestação a seguir trata de juntada de comprovante de pagamento, em atenção ao contexto processual apresentado.",
            texto,
        )
        self.assertNotIn(
            "A presente demanda decorre de juntada de comprovante de pagamento",
            texto,
        )

    def test_local_draft_uses_piece_specific_opening_for_contestacao(self):
        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            texto = gerar_rascunho_juridico(
                client_name="Cliente Teste",
                document_type="Contestação",
                case_subject="cobrança indevida",
                facts="A parte ré impugna a narrativa apresentada na inicial.",
                requests="Improcedência dos pedidos.",
                legal_basis="CPC e Código Civil.",
                context_used="[RESUMO DO CASO]\nTeste",
                writing_profile=None,
                documentos_selecionados=[],
            )

        self.assertIn("apresentar contestação", texto)
        self.assertNotIn("propor a presente", texto)

    def test_local_draft_refines_peticao_inicial_opening_and_intro(self):
        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            texto = gerar_rascunho_juridico(
                client_name="Cliente Teste",
                document_type="Petição inicial",
                case_subject="obrigação de fazer cumulada com indenização",
                facts="A parte autora relata descumprimento contratual.",
                requests="Procedência dos pedidos.",
                legal_basis="Código Civil e CDC.",
                context_used="[RESUMO DO CASO]\nTeste",
                writing_profile=None,
                documentos_selecionados=[],
            )

        self.assertIn("ajuizar a presente ação", texto)
        self.assertIn(
            "Trata-se de demanda relacionada a obrigação de fazer cumulada com indenização, conforme se passa a expor.",
            texto,
        )
        self.assertNotIn("propor a presente petição inicial", texto)
        self.assertNotIn("A demanda decorre de", texto)

    def test_local_draft_ignores_irrelevant_document_heading_excerpt(self):
        documento = SimpleNamespace(
            original_filename="PETICAO INICIAL - GERAL - contra PESSOA FISICA.docx",
            summary="PETICAO INICIAL -AUTOATENDIMENTO- AO JUIZADO ESPECIAL CIVEL DE (a) <DIGITE O NOME DA CIDADE (FORUM)>- DF.",
            extracted_text="",
        )

        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            texto = gerar_rascunho_juridico(
                client_name="Cliente Teste",
                document_type="Petição inicial",
                case_subject="cobrança indevida",
                facts="O cliente relata cobranças indevidas reiteradas.",
                requests="Cancelamento da cobrança.",
                legal_basis="CDC.",
                context_used="[RESUMO DO CASO]\nTeste",
                writing_profile=None,
                documentos_selecionados=[documento],
            )

        self.assertNotIn("AUTOATENDIMENTO", texto)
        self.assertNotIn("JUÍZADO ESPECIAL", texto)

    def test_local_draft_ignores_placeholder_profile_phrases(self):
        profile = SimpleNamespace(
            qualification_style="Ja qualificado nos autos, vem, respeitosamente, a presença de vossa...",
            opening_phrase="ajuizar a presente demanda...",
            request_intro="diante do exposto, requer-se...",
            closing_phrase="Termos, em que, pede deferimento...",
            lawyer_name="Natan Jonatan de Lima",
            office_name="Santos e Silveiro",
        )

        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            texto = gerar_rascunho_juridico(
                client_name="Natan Lima",
                document_type="Petição inicial",
                case_subject="obrigação de fazer c/c indenização por danos morais",
                facts="A parte autora relata falha na prestação do serviço.",
                requests="Concessão da tutela provisória.\nCitação da parte ré.",
                legal_basis="Código Civil e CDC.",
                context_used="[RESUMO DO CASO]\nTeste",
                writing_profile=profile,
                documentos_selecionados=[],
            )

        self.assertIn("ajuizar a presente ação", texto)
        self.assertIn("Diante do exposto, requer:", texto)
        self.assertIn("Nesses termos,\nPede deferimento.", texto)
        self.assertNotIn("vossa...", texto)
        self.assertNotIn("requer-se...", texto)
        self.assertNotIn("pede deferimento...", texto)


if __name__ == "__main__":
    unittest.main()
