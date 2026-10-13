"""Official Codex app-server transport. OAuth credentials stay owned by Codex."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse

from .ai import AIError, SYSTEM

PROVIDER = "GPT (login Codex)"


def strict_schema(schema):
    schema = json.loads(json.dumps(schema))
    def visit(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(schema)
    return schema


def command():
    executable = shutil.which("codex")
    if executable:
        path = Path(executable)
        if path.suffix.lower() in (".cmd", ".ps1"):
            package = path.parent / "node_modules/@openai/codex"
            binaries = list(package.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
            if binaries:
                return [str(binaries[0])]
            script = path.parent / "node_modules/@openai/codex/bin/codex.js"
            node = shutil.which("node")
            if script.is_file() and node:
                return [node, str(script)]
        elif path.suffix.lower() == ".exe" or os.name != "nt":
            return [executable]
    raise AIError("Codex belum terpasang. Pasang Codex CLI terlebih dahulu, lalu buka ulang Laprak.")


def safe_auth_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ("auth.openai.com", "chatgpt.com") or parsed.username or parsed.password:
        raise AIError("Alamat login bukan halaman resmi OpenAI.")
    return url


class Server:
    def __init__(self, cancel=None, timeout=90):
        launch_command = command()
        self.cancel = cancel or threading.Event()
        self.deadline = time.monotonic() + timeout
        self.messages = queue.Queue()
        self.pending = []
        self.serial = 0
        self.folder = tempfile.TemporaryDirectory(prefix="laprak-codex-")
        env = dict(os.environ)
        # Isolate account/config from the user's coding agent and its plugins.
        home = Path.cwd() / ".local" / "codex"
        home.mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(home.resolve())
        env.pop("OPENAI_API_KEY", None)
        try:
            self.process = subprocess.Popen(launch_command + ["app-server", "--listen", "stdio://",
                "-c", 'model_provider="openai"', "-c", 'features.shell_tool=false',
                "-c", 'web_search="disabled"', "-c", 'apps._default.enabled=false',
                "-c", 'cli_auth_credentials_store="keyring"'],
                cwd=self.folder.name, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except Exception:
            self.folder.cleanup()
            raise AIError("Tidak dapat menjalankan Codex. Periksa instalasi Codex CLI.") from None
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.request("initialize", {"clientInfo": {"name": "laprak", "title": "Laprak", "version": "0.1.0"}})
            self.send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    pass
        finally:
            self.messages.put(None)

    def send(self, value):
        try:
            self.process.stdin.write(json.dumps(value) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise AIError("Koneksi Codex terputus. Coba hubungkan kembali.") from None

    def receive(self):
        while True:
            if self.cancel.is_set():
                raise AIError("Dibatalkan; respons tidak diterapkan.")
            if time.monotonic() >= self.deadline:
                raise AIError("Waktu tunggu Codex habis. Periksa browser, koneksi, atau kuota akun.")
            try:
                value = self.messages.get(timeout=.2)
            except queue.Empty:
                continue
            if value is None:
                raise AIError("Codex berhenti. Periksa instalasi dan koneksi.")
            if "method" in value and "id" in value:
                # No shell, file edits or external tools are authorized by Laprak.
                self.send({"id": value["id"], "error": {"code": -32601, "message": "Tools are disabled in Laprak"}})
                continue
            return value

    def request(self, method, params=None):
        self.serial += 1
        identifier = self.serial
        self.send({"id": identifier, "method": method, "params": params or {}})
        while True:
            value = self.receive()
            if value.get("id") == identifier:
                if "error" in value:
                    raise AIError("Codex menolak permintaan. Periksa login, versi Codex, izin model, dan kuota akun.")
                return value.get("result", {})
            self.pending.append(value)

    def event(self):
        return self.pending.pop(0) if self.pending else self.receive()

    def account(self):
        account = self.request("account/read", {"refreshToken": False}).get("account")
        if not account or account.get("type") != "chatgpt":
            raise AIError("Belum terhubung. Klik Connect GPT dan login di browser.", auth=True)
        return account

    def models(self):
        result, cursor = [], None
        while True:
            page = self.request("model/list", {"cursor": cursor, "limit": 100})
            result.extend(page.get("data", []))
            cursor = page.get("nextCursor")
            if not cursor:
                return result

    def close(self):
        if getattr(self, "active_turn", None) and self.process.poll() is None:
            self.cancel = threading.Event()
            self.deadline = time.monotonic() + 2
            try:
                self.request("turn/interrupt", {"threadId": self.active_turn[0], "turnId": self.active_turn[1]})
            except AIError:
                pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.process.stdin.close()
        self.process.stdout.close()
        self.folder.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def login(open_browser, cancel):
    with Server(cancel, timeout=300) as server:
        login = server.request("account/login/start", {"type": "chatgpt", "useHostedLoginSuccessPage": True, "appBrand": "codex"})
        open_browser(safe_auth_url(login["authUrl"]))
        while True:
            event = server.event()
            params = event.get("params", {})
            if event.get("method") == "account/login/completed" and params.get("loginId") == login["loginId"]:
                if not params.get("success"):
                    raise AIError("Login belum berhasil. Coba Connect GPT kembali.")
                server.account()
                models = server.models()
                model = next((m for m in models if m.get("isDefault")), models[0] if models else None)
                if not model:
                    raise AIError("Login berhasil, tetapi belum ada model tersedia untuk akun ini.")
                return model["model"]


class Codex:
    def __init__(self, settings, *_):
        self.settings = settings

    def models(self):
        with Server(timeout=self.settings.get("timeout", 90)) as server:
            server.account()
            return [m["model"] for m in server.models()]

    def run(self, prompt, schema, pictures, cancel):
        with Server(cancel, self.settings.get("timeout", 90)) as server:
            server.account()
            thread = server.request("thread/start", {"model": self.settings["model"], "modelProvider": "openai",
                "cwd": server.folder.name, "ephemeral": True, "approvalPolicy": "never", "sandbox": "read-only",
                "baseInstructions": SYSTEM + " Jangan gunakan tool, shell, berkas, atau web. Jawab hanya JSON."})["thread"]["id"]
            inputs = [{"type": "text", "text": prompt}] + [
                {"type": "image", "url": "data:image/jpeg;base64," + p} for p in pictures]
            turn = server.request("turn/start", {"threadId": thread, "input": inputs,
                "outputSchema": strict_schema(schema)})["turn"]["id"]
            server.active_turn = (thread, turn)
            text = ""
            while True:
                event = server.event()
                params = event.get("params", {})
                if params.get("threadId") != thread:
                    continue
                if event.get("method") == "item/agentMessage/delta" and params.get("turnId") == turn:
                    text += params.get("delta", "")
                if event.get("method") == "turn/completed" and params.get("turn", {}).get("id") == turn:
                    server.active_turn = None
                    if params["turn"].get("status") != "completed":
                        raise AIError("Codex belum menyelesaikan analisis. Periksa kuota, login, dan izin model.")
                    try:
                        return json.loads(text)
                    except ValueError:
                        raise AIError("Respons Codex belum sesuai JSON. Coba ulang analisis.") from None
