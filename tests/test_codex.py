import json
import queue
import threading
import time
import unittest
from unittest.mock import patch

from laprak.ai import Adapter, Analysis, AIError
from laprak.codex import Codex, Server, login, safe_auth_url, strict_schema


class FakeServer:
    def __init__(self, *args, **kwargs):
        self.folder = type("Folder", (), {"name": "C:/empty"})()
        self.calls = []
        self.events = [
            {"method": "account/login/completed", "params": {"loginId": "other", "success": True}},
            {"method": "account/login/completed", "params": {"loginId": "mine", "success": True}},
            {"method": "item/agentMessage/delta", "params": {"threadId": "other", "turnId": "turn", "delta": "bad"}},
            {"method": "item/agentMessage/delta", "params": {"threadId": "thread", "turnId": "turn", "delta": json.dumps({"narrative": "berhasil"})}},
            {"method": "turn/completed", "params": {"threadId": "thread", "turn": {"id": "turn", "status": "completed"}}},
        ]
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def account(self): return {"type": "chatgpt"}
    def models(self): return [{"model": "first"}, {"model": "default", "isDefault": True}]
    def event(self): return self.events.pop(0)
    def request(self, method, params):
        self.calls.append((method, params))
        return {"account/login/start": {"loginId": "mine", "authUrl": "https://auth.openai.com/oauth/authorize"},
                "thread/start": {"thread": {"id": "thread"}}, "turn/start": {"turn": {"id": "turn"}}}[method]


class CodexTests(unittest.TestCase):
    def test_browser_login_waits_for_own_completion_and_selects_default(self):
        browser = []
        with patch("laprak.codex.Server", FakeServer):
            self.assertEqual(login(browser.append, threading.Event()), "default")
        self.assertEqual(browser, ["https://auth.openai.com/oauth/authorize"])

    def test_rejects_fake_login_urls(self):
        for url in ("https://auth.openai.com.evil.org/login", "http://auth.openai.com/login", "https://user@chatgpt.com/login"):
            with self.assertRaises(AIError): safe_auth_url(url)

    def test_failed_login_cannot_mark_connected(self):
        fake = FakeServer()
        fake.events = [{"method": "account/login/completed", "params": {"loginId": "mine", "success": False, "error": "secret"}}]
        with patch("laprak.codex.Server", return_value=fake), self.assertRaises(AIError) as caught:
            login(lambda url: None, threading.Event())
        self.assertNotIn("secret", str(caught.exception))

    def test_adapter_routes_to_codex_and_validates_draft(self):
        fake = FakeServer()
        config = {"provider": "GPT (login Codex)", "model": "default", "endpoint": "codex://local", "vision": True}
        with patch("laprak.codex.Server", return_value=fake):
            result = Adapter(config).run("contoh")
        self.assertEqual(result["narrative"], "berhasil")
        thread = fake.calls[0][1]
        self.assertTrue(thread["ephemeral"])
        self.assertEqual(thread["sandbox"], "read-only")
        self.assertEqual(thread["approvalPolicy"], "never")
        self.assertFalse(fake.calls[1][1]["outputSchema"]["additionalProperties"])

    def test_cancel_and_timeout_do_not_wait_for_stdout(self):
        server = Server.__new__(Server)
        server.messages = queue.Queue()
        server.cancel = threading.Event()
        server.deadline = time.monotonic() + 10
        server.cancel.set()
        with self.assertRaises(AIError): server.receive()
        server.cancel.clear()
        server.deadline = 0
        with self.assertRaises(AIError): server.receive()

    def test_schema_is_strict_without_mutating_pydantic(self):
        original = Analysis.model_json_schema()
        result = strict_schema(original)
        self.assertEqual(set(result["required"]), set(result["properties"]))
        self.assertNotIn("default", result["properties"]["narrative"])
        self.assertIn("default", original["properties"]["narrative"])

    def test_connected_requires_real_chatgpt_account(self):
        server = Server.__new__(Server)
        server.request = lambda *_: {"account": {"type": "apiKey"}}
        with self.assertRaises(AIError): server.account()
