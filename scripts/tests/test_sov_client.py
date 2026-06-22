"""Unit tests for services/sov_client.py — all SOV HTTP is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from services import sov_client


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.request = httpx.Request("GET", "http://localhost:8765/test")
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("not json")
    return response


@pytest.fixture
def mock_client():
    with patch("services.sov_client.httpx.Client") as client_cls:
        instance = MagicMock()
        client_cls.return_value.__enter__.return_value = instance
        client_cls.return_value.__exit__.return_value = False
        yield instance


class TestSovGet:
    def test_retries_on_timeout_then_raises(self, mock_client):
        mock_client.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(httpx.TimeoutException):
            sov_client._sov_get("/coding/programs/EFN")

        assert mock_client.get.call_count == sov_client.MAX_ATTEMPTS

    def test_retries_on_500_then_raises(self, mock_client):
        mock_client.get.return_value = _mock_response(500)

        with pytest.raises(httpx.HTTPStatusError):
            sov_client._sov_get("/coding/programs/EFN")

        assert mock_client.get.call_count == sov_client.MAX_ATTEMPTS

    def test_succeeds_after_transient_500(self, mock_client):
        mock_client.get.side_effect = [
            _mock_response(500),
            _mock_response(200, {"ok": True}),
        ]

        response = sov_client._sov_get("/coding/programs/EFN")

        assert response.status_code == 200
        assert mock_client.get.call_count == 2

    def test_success_on_first_attempt(self, mock_client):
        mock_client.get.return_value = _mock_response(200, {"ok": True})

        response = sov_client._sov_get("/coding/programs/EFN")

        assert response.status_code == 200
        assert mock_client.get.call_count == 1

    def test_sends_api_key_header(self, mock_client):
        mock_client.get.return_value = _mock_response(200)

        with patch.object(sov_client.settings, "sov_api_key", "test-key"):
            sov_client._sov_get("/coding/programs/EFN")

        _, kwargs = mock_client.get.call_args
        assert kwargs["headers"]["X-API-Key"] == "test-key"


class TestExistenceCheck:
    def test_returns_true_on_200(self, mock_client):
        mock_client.get.return_value = _mock_response(200, {"code": "EFN"})

        assert sov_client.existence_check("efn") is True

    def test_returns_false_on_404(self, mock_client):
        mock_client.get.return_value = _mock_response(404)

        assert sov_client.existence_check("EFN") is False

    def test_normalizes_program_code(self, mock_client):
        mock_client.get.return_value = _mock_response(200)

        sov_client.existence_check("efn")

        url = mock_client.get.call_args[0][0]
        assert "/coding/programs/EFN" in url


SECTION_FETCHERS = [
    ("fetch_shipped_since_last_sync", "/digest/shipped-since-last-sync"),
    ("fetch_awaiting_po_decision", "/digest/awaiting-po-decision"),
    ("fetch_mvp_sprint_status", "/digest/mvp-sprint-status"),
    ("fetch_blockers", "/digest/blockers"),
]


class TestSectionFetchers:
    @pytest.mark.parametrize("fetcher_name,section_path", SECTION_FETCHERS)
    def test_returns_parsed_data_on_success(self, mock_client, fetcher_name, section_path):
        payload = {"items": [{"id": 1}]}
        mock_client.get.return_value = _mock_response(200, payload)
        fetcher = getattr(sov_client, fetcher_name)

        result = fetcher("EFN")

        assert result == payload
        url = mock_client.get.call_args[0][0]
        assert section_path in url

    @pytest.mark.parametrize("fetcher_name,section_path", SECTION_FETCHERS)
    def test_returns_error_marker_on_timeout(self, mock_client, fetcher_name, section_path):
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        fetcher = getattr(sov_client, fetcher_name)

        result = fetcher("EFN")

        assert result["status"] == "unavailable"
        assert "timed out" in result["error"]

    @pytest.mark.parametrize("fetcher_name,section_path", SECTION_FETCHERS)
    def test_returns_error_marker_on_500(self, mock_client, fetcher_name, section_path):
        mock_client.get.return_value = _mock_response(500)
        fetcher = getattr(sov_client, fetcher_name)

        result = fetcher("EFN")

        assert result["status"] == "unavailable"
        assert "error" in result