"""Ollama HTTP client using urllib.request (no external dependencies)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama communication fails."""


class OllamaClient:
    """Minimal Ollama API client."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self, model: str) -> bool:
        """Check if Ollama is running and the model exists.

        Args:
            model: Model name to check for.

        Returns:
            True if the model is available.

        Raises:
            OllamaError: If Ollama is unreachable.
        """
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as e:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}: {e}")

        models = [m.get("name", "") for m in data.get("models", [])]
        # Match both "gemma3" and "gemma3:latest"
        for m in models:
            if m == model or m.startswith(f"{model}:"):
                return True

        available = ", ".join(models) if models else "(none)"
        raise OllamaError(
            f"Model '{model}' not found. Available: {available}"
        )

    def chat(self, model: str, system: str, user: str) -> str:
        """Send a chat completion request.

        Args:
            model: Ollama model name.
            system: System prompt.
            user: User message.

        Returns:
            The assistant's response text.

        Raises:
            OllamaError: On any communication or parsing failure.
        """
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise OllamaError(f"Ollama HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise OllamaError(f"Cannot connect to Ollama: {e}")
        except json.JSONDecodeError as e:
            raise OllamaError(f"Invalid JSON response from Ollama: {e}")
        except OSError as e:
            raise OllamaError(f"Ollama request failed: {e}")

        message = data.get("message", {})
        content = message.get("content", "")
        if not content:
            raise OllamaError("Empty response from Ollama")

        logger.debug("Ollama response length: %d chars", len(content))
        return content
