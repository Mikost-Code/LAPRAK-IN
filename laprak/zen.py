"""Direct Zen Chat Completions models."""
import httpx

from .ai import AIError, validate_provider_endpoint, provider_problem

# Protocols verified against the official Zen endpoint table on 2026-10-11.
# The catalog does not expose protocol metadata: never guess a new model's route.
CHAT_MODELS = frozenset("""qwen3.8-max deepseek-v4.1-flash deepseek-v4-pro
deepseek-v4-flash deepseek-v4-flash-vision-exp minimax-m3 minimax-m2.7 minimax-m2.5
glm-5.3-flash glm-5.3 glm-5.2 glm-5.1 glm-5 kimi-k2.5 kimi-k2.6 kimi-k2.7-code
kimi-k3 mistral-large-4 big-pickle space-bunny-free longcat-2.5-preview-free
step-5-preview-free exo-free mimo-v2.6-flash-free mimo-v2.5-free ling-3.1-flash-free
ling-3.0-flash-fin-free nemotron-3-ultra-free nemotron-3.5-lightning-free""".split())


def validate_model(model):
    if model not in CHAT_MODELS:
        raise AIError("Pilih ID model Zen dari tombol Pilih model. 'free' bukan ID model.")
    if is_free_model(model):
        raise AIError("Model gratis Zen tidak tersedia untuk API langsung Laprak (FreeTierError). Pilih model API berbayar, atau gunakan provider lain (Codex, Ollama, API kompatibel OpenAI).")


def is_free_model(model):
    return model == "big-pickle" or model.endswith("-free")


class Zen:
    def __init__(self, settings, secret="", transport=None):
        self.endpoint = validate_provider_endpoint(settings)
        self.settings = settings
        self.secret = secret
        self.transport = transport

    def models(self):
        try:
            with httpx.Client(timeout=self.settings.get("timeout", 90), transport=self.transport, follow_redirects=False) as client:
                response = client.get(self.endpoint + "/models",
                                      headers={"Authorization": f"Bearer {self.secret}"} if self.secret else {})
            if response.status_code != 200:
                message, auth = provider_problem(response.status_code, response.text)
                raise AIError(message, auth=auth)
            models = {item["id"] for item in response.json()["data"]}
            return sorted(model for model in models & CHAT_MODELS if not is_free_model(model))
        except httpx.RequestError:
            raise AIError("Tidak dapat mengambil model Zen. Periksa koneksi internet.") from None
        except (ValueError, TypeError, KeyError):
            raise AIError("Daftar model Zen tidak valid.") from None
