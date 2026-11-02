"""Intégration réelle de LiteLLM (sans réseau externe) : un faux serveur compatible OpenAI en local.

Ce test vérifie que la bibliothèque s'importe et que notre LiteLLMProvider traduit correctement
la réponse (texte + tokens réels). Il a été ajouté après la découverte d'une version de LiteLLM
dont l'import échouait : les autres tests remplacent le fournisseur et ne pouvaient pas le voir.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.models import LlmModel
from app.providers.base import ProviderError
from app.providers.litellm_provider import LiteLLMProvider


class _FakeOpenAI(BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):  # noqa: N802
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        _FakeOpenAI.last_request = {"body": body, "auth": self.headers.get("Authorization"), "path": self.path}
        if self.path.startswith("/api/"):  # format Ollama
            return self._send({"model": body.get("model"), "response": "Réponse Ollama.", "done": True,
                               "prompt_eval_count": 20, "eval_count": 7, "message": {"role": "assistant",
                                                                                      "content": "Réponse Ollama."}})
        payload = {
            "id": "chatcmpl-test", "object": "chat.completion", "created": 0, "model": body["model"],
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "Réponse du faux serveur."}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        }
        self._send(payload)

    def _send(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(_FakeOpenAI.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), _FakeOpenAI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _FakeOpenAI.status = 200
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def _model() -> LlmModel:
    return LlmModel(litellm_name="openai/modele-test", display_name="Test")


def test_litellm_real_call_returns_text_and_real_tokens(fake_server):
    result = LiteLLMProvider(api_key="cle-test", api_base=fake_server).complete(
        _model(), [{"role": "user", "content": "Bonjour"}])
    assert result.text == "Réponse du faux serveur."
    assert (result.input_tokens, result.output_tokens) == (12, 5)
    assert result.tokens_estimated is False and result.simulated is False
    assert _FakeOpenAI.last_request["auth"] == "Bearer cle-test"
    assert _FakeOpenAI.last_request["body"]["messages"] == [{"role": "user", "content": "Bonjour"}]


def test_litellm_provider_error_exposes_only_error_type(fake_server):
    _FakeOpenAI.status = 500
    with pytest.raises(ProviderError) as exc:
        LiteLLMProvider(api_key="cle-test", api_base=fake_server).complete(
            _model(), [{"role": "user", "content": "contenu à ne pas divulguer"}])
    assert "contenu" not in str(exc.value)  # seul le type d'erreur remonte


def test_litellm_ollama_call(fake_server):
    """Chemin des modèles privés : LiteLLM vers une API au format Ollama."""
    base = fake_server.removesuffix("/v1")
    model = LlmModel(litellm_name="ollama/llama3.1:8b", display_name="Llama")
    result = LiteLLMProvider(api_base=base, backend="ollama").complete(model, [{"role": "user", "content": "Bonjour"}])
    assert result.text == "Réponse Ollama." and result.backend == "ollama"
    assert _FakeOpenAI.last_request["path"].startswith("/api/")
