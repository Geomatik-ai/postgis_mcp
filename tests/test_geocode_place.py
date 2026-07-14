import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import geocode_place

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def make_mock_response(data: list):
    """Build a fake httpx response that returns preset JSON data."""
    mock_response = MagicMock()
    mock_response.json.return_value = data
    return mock_response


LUDHIANA_API_RESPONSE = [
    {
        "lat": "30.9081",
        "lon": "75.8530",
        "display_name": "Ludhiana, Ludhiana District, Punjab, India",
    }
]


# ─────────────────────────────────────────────
# Unit tests (monkeypatched — no real network)
# ─────────────────────────────────────────────


def test_valid_place_returns_dict(monkeypatch):
    monkeypatch.setattr(
        "server.httpx.get", lambda *_a, **_kw: make_mock_response(LUDHIANA_API_RESPONSE)
    )

    result = geocode_place("Ludhiana")

    assert isinstance(result, dict)
    assert "lat" in result
    assert "lon" in result
    assert "display_name" in result


def test_lat_lon_are_floats(monkeypatch):
    """Nominatim returns strings — the function must cast them to float."""
    monkeypatch.setattr(
        "server.httpx.get", lambda *_a, **_kw: make_mock_response(LUDHIANA_API_RESPONSE)
    )

    result = geocode_place("Ludhiana")

    assert isinstance(result["lat"], float)
    assert isinstance(result["lon"], float)


def test_correct_values_returned(monkeypatch):
    monkeypatch.setattr(
        "server.httpx.get", lambda *_a, **_kw: make_mock_response(LUDHIANA_API_RESPONSE)
    )

    result = geocode_place("Ludhiana")

    assert result["lat"] == 30.9081
    assert result["lon"] == 75.8530
    assert result["display_name"] == "Ludhiana, Ludhiana District, Punjab, India"


def test_empty_response_raises_valueerror(monkeypatch):
    """API returning [] means place not found — must raise ValueError."""
    monkeypatch.setattr("server.httpx.get", lambda *a, **kw: make_mock_response([]))

    with pytest.raises(ValueError):
        geocode_place("xyznonexistentplace123")


def test_user_agent_header_is_sent(monkeypatch):
    """Nominatim ToS requires a User-Agent header — verify it is always sent."""
    captured = {}

    def mock_get(*_args, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        return make_mock_response(LUDHIANA_API_RESPONSE)

    monkeypatch.setattr("server.httpx.get", mock_get)
    geocode_place("Ludhiana")

    assert "User-Agent" in captured["headers"]


def test_timeout_is_set(monkeypatch):
    """Network calls without a timeout hang forever — verify timeout is passed."""
    captured = {}

    def mock_get(*_args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return make_mock_response(LUDHIANA_API_RESPONSE)

    monkeypatch.setattr("server.httpx.get", mock_get)
    geocode_place("Ludhiana")

    assert captured["timeout"] is not None


def test_http_error_propagates(monkeypatch):
    """HTTP errors (429, 500) must propagate — not silently return empty data."""
    import httpx

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=MagicMock(),
    )

    monkeypatch.setattr("server.httpx.get", lambda *_a, **_kw: mock_response)

    with pytest.raises(httpx.HTTPStatusError):
        geocode_place("Ludhiana")


# ─────────────────────────────────────────────
# Integration tests (real Nominatim network call)
# ─────────────────────────────────────────────


@pytest.mark.integration
def test_ludhiana_returns_correct_coordinates():
    result = geocode_place("Ludhiana")

    assert isinstance(result, dict)
    assert abs(result["lat"] - 30.9) < 0.5
    assert abs(result["lon"] - 75.8) < 0.5
    assert "display_name" in result


@pytest.mark.integration
def test_nonexistent_place_raises_valueerror():
    with pytest.raises(ValueError):
        geocode_place("xyznonexistentplace123")
