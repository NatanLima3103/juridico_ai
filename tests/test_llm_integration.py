import sys
import types
import unittest
from unittest.mock import patch

from app.services import ai_generation_service


class FakeResponsesClient:
    def __init__(self, *, text: str = "", response_id: str = "resp_123", error: Exception | None = None):
        self._text = text
        self._response_id = response_id
        self._error = error

    def create(self, **kwargs):
        if self._error:
            raise self._error
        return types.SimpleNamespace(output_text=self._text, id=self._response_id)


class FakeOpenAIClient:
    def __init__(self, *, text: str = "", response_id: str = "resp_123", error: Exception | None = None):
        self.responses = FakeResponsesClient(text=text, response_id=response_id, error=error)


class LLMIntegrationTests(unittest.TestCase):
    def test_returns_rule_based_result_when_openai_key_is_missing(self):
        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            result = ai_generation_service.gerar_resultado_juridico_com_fallback(
                prompt_payload={"system_prompt": "s", "user_prompt": "u"},
                fallback_generator=lambda: "Texto local",
            )

        self.assertEqual(result.text, "Texto local")
        self.assertEqual(result.generation_strategy, "rule_based")
        self.assertIsNone(result.llm_provider)
        self.assertIn("OPENAI_API_KEY", result.llm_error)

    def test_returns_openai_result_when_client_responds(self):
        fake_module = types.SimpleNamespace(OpenAI=lambda api_key=None: FakeOpenAIClient(text="Texto IA", response_id="resp_ok"))

        with patch.object(ai_generation_service, "OPENAI_API_KEY", "test-key"):
            with patch.dict(sys.modules, {"openai": fake_module}):
                result = ai_generation_service.gerar_resultado_juridico_com_fallback(
                    prompt_payload={"system_prompt": "sistema", "user_prompt": "usuario"},
                    fallback_generator=lambda: "Texto local",
                )

        self.assertEqual(result.text, "Texto IA")
        self.assertEqual(result.generation_strategy, "ai_openai")
        self.assertEqual(result.llm_provider, "openai")
        self.assertEqual(result.llm_response_id, "resp_ok")

    def test_falls_back_when_openai_call_fails(self):
        fake_module = types.SimpleNamespace(
            OpenAI=lambda api_key=None: FakeOpenAIClient(error=RuntimeError("falha externa"))
        )

        with patch.object(ai_generation_service, "OPENAI_API_KEY", "test-key"):
            with patch.dict(sys.modules, {"openai": fake_module}):
                result = ai_generation_service.gerar_resultado_juridico_com_fallback(
                    prompt_payload={"system_prompt": "sistema", "user_prompt": "usuario"},
                    fallback_generator=lambda: "Texto local",
                )

        self.assertEqual(result.text, "Texto local")
        self.assertEqual(result.generation_strategy, "rule_based")
        self.assertEqual(result.llm_provider, "openai")
        self.assertIn("Falha ao chamar a API da OpenAI", result.llm_error)


if __name__ == "__main__":
    unittest.main()
