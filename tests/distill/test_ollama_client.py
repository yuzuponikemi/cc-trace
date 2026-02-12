"""Tests for Ollama HTTP client."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from cc_trace.distill.ollama_client import OllamaClient, OllamaError


def _mock_urlopen(response_data: dict):
    """Create a mock for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestIsAvailable:
    def test_model_found(self) -> None:
        client = OllamaClient()
        resp = _mock_urlopen({"models": [{"name": "gemma3:latest"}]})
        with patch("urllib.request.urlopen", return_value=resp):
            assert client.is_available("gemma3") is True

    def test_model_exact_match(self) -> None:
        client = OllamaClient()
        resp = _mock_urlopen({"models": [{"name": "gemma3"}]})
        with patch("urllib.request.urlopen", return_value=resp):
            assert client.is_available("gemma3") is True

    def test_model_not_found(self) -> None:
        client = OllamaClient()
        resp = _mock_urlopen({"models": [{"name": "llama3:latest"}]})
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(OllamaError, match="not found"):
                client.is_available("gemma3")

    def test_connection_refused(self) -> None:
        client = OllamaClient()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(OllamaError, match="Cannot connect"):
                client.is_available("gemma3")

    def test_empty_models(self) -> None:
        client = OllamaClient()
        resp = _mock_urlopen({"models": []})
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(OllamaError, match="not found"):
                client.is_available("gemma3")


class TestChat:
    def test_successful_response(self) -> None:
        client = OllamaClient()
        resp = _mock_urlopen({
            "message": {"role": "assistant", "content": '{"core_topics": ["test"]}'},
        })
        with patch("urllib.request.urlopen", return_value=resp) as mock_open:
            result = client.chat("gemma3", "system prompt", "user message")
            assert result == '{"core_topics": ["test"]}'

            # Verify request payload
            call_args = mock_open.call_args
            req = call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            assert body["model"] == "gemma3"
            assert body["stream"] is False
            assert len(body["messages"]) == 2
            assert body["messages"][0]["role"] == "system"
            assert body["messages"][1]["role"] == "user"

    def test_empty_response(self) -> None:
        client = OllamaClient()
        resp = _mock_urlopen({"message": {"role": "assistant", "content": ""}})
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(OllamaError, match="Empty response"):
                client.chat("gemma3", "sys", "usr")

    def test_http_error(self) -> None:
        client = OllamaClient()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "url", 500, "Internal Server Error", {}, None
            ),
        ):
            with pytest.raises(OllamaError, match="HTTP error 500"):
                client.chat("gemma3", "sys", "usr")

    def test_connection_error(self) -> None:
        client = OllamaClient()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(OllamaError, match="Cannot connect"):
                client.chat("gemma3", "sys", "usr")

    def test_custom_url_and_timeout(self) -> None:
        client = OllamaClient(base_url="http://remote:1234/", timeout=60)
        assert client.base_url == "http://remote:1234"
        assert client.timeout == 60
