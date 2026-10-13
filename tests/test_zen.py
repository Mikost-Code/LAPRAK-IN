import json
import unittest

import httpx

from laprak.ai import Adapter, AIError, validate_provider_endpoint, provider_problem
from laprak.zen import Zen


class ZenTests(unittest.TestCase):
    def config(self):
        return dict(provider="OpenCode Zen (API)", endpoint="https://opencode.ai/zen/v1",
                    model="glm-5", structured="Prompt JSON", vision=False)

    def test_zen_api_requires_zen_endpoint(self):
        with self.assertRaises(ValueError):
            validate_provider_endpoint(dict(provider="OpenCode Zen (API)", endpoint="http://127.0.0.1:4096"))

    def test_catalog_excludes_free_models_and_unsupported_protocols(self):
        catalog = {"data": [{"id": model} for model in ("gpt-5", "glm-5", "big-pickle", "space-bunny-free", "claude-opus-5", "jev-1.13-free")]}
        def handler(request):
            self.assertEqual(request.url.path, "/zen/v1/models")
            return httpx.Response(200, json=catalog)
        self.assertEqual(Zen(self.config(), transport=httpx.MockTransport(handler)).models(), ["glm-5"])

    def test_zen_posts_chat_format_and_bearer_key(self):
        def handler(request):
            self.assertEqual(request.url.path, "/zen/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer private-key")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "glm-5")
            self.assertNotIn("response_format", payload)
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"narrative":"ok"}'}}]})
        self.assertEqual(Adapter(self.config(), "private-key", httpx.MockTransport(handler)).run("test")["narrative"], "ok")

    def test_missing_key_and_free_placeholder_do_not_send_inference(self):
        def handler(request):
            self.fail("Invalid configuration must not make an inference request")
        config = self.config()
        with self.assertRaises(AIError):
            Adapter(config, transport=httpx.MockTransport(handler)).run("test")
        config["model"] = "free"
        with self.assertRaises(AIError):
            Adapter(config, "private-key", httpx.MockTransport(handler)).run("test")

    def test_free_tier_is_not_misclassified_as_bad_key_and_is_blocked_before_request(self):
        message, auth = provider_problem(403, '{"error":{"type":"FreeTierError","message":"private-key"}}')
        self.assertIn("FreeTierError", message)
        self.assertFalse(auth)
        self.assertNotIn("private-key", message)
        config = self.config()
        config["model"] = "space-bunny-free"
        def handler(request):
            self.fail("Do not send known-restricted direct API inference")
        with self.assertRaises(AIError):
            Adapter(config, "private-key", httpx.MockTransport(handler)).run("test")

    def test_403_distinguishes_network_unknown_access_and_invalid_key(self):
        self.assertIn("proteksi jaringan", provider_problem(403, "<html>cloudflare</html>")[0])
        self.assertFalse(provider_problem(403, '{"model":"x"}')[1])
        self.assertTrue(provider_problem(403, '{"error":{"code":"invalid_api_key"}}')[1])
