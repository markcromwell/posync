"""Unit tests for GET /digest/{program_code} — mocked sov_client."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import create_app

DIGEST_KEY = "test-digest-key"
AUTH_HEADERS = {"X-API-Key": DIGEST_KEY}

SHIPPED = {"items": [{"id": 1, "title": "Shipped feature"}]}
AWAITING = {"items": [{"id": 2, "summary": "Needs PO call"}]}
MVP = {"sprint": "Sprint 2", "percent_complete": 50}
BLOCKERS = {"items": [{"id": 3, "description": "CI blocked"}]}
ERROR_MARKER = {"status": "unavailable", "error": "timeout"}


@pytest.fixture
def client():
    with patch("app.config.settings.digest_api_key", DIGEST_KEY):
        yield TestClient(create_app())


def _mock_all_sections(
    shipped=SHIPPED,
    awaiting=AWAITING,
    mvp=MVP,
    blockers=BLOCKERS,
):
    return (
        patch("services.sov_client.existence_check", return_value=True),
        patch("services.sov_client.fetch_shipped_since_last_sync", return_value=shipped),
        patch("services.sov_client.fetch_awaiting_po_decision", return_value=awaiting),
        patch("services.sov_client.fetch_mvp_sprint_status", return_value=mvp),
        patch("services.sov_client.fetch_blockers", return_value=blockers),
    )


class TestDigestHappyPath:
    def test_returns_200_with_all_four_keys(self, client):
        patches = _mock_all_sections()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            response = client.get("/digest/PROJ", headers=AUTH_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"shipped", "awaiting_decision", "mvp_status", "blockers"}
        assert data["shipped"] == SHIPPED["items"]
        assert data["awaiting_decision"] == AWAITING["items"]
        assert data["mvp_status"] == MVP
        assert data["blockers"] == BLOCKERS["items"]


class TestDigestDegradation:
    @pytest.mark.parametrize(
        "section_key,fetcher_name,return_value",
        [
            ("shipped", "fetch_shipped_since_last_sync", ERROR_MARKER),
            ("awaiting_decision", "fetch_awaiting_po_decision", ERROR_MARKER),
            ("mvp_status", "fetch_mvp_sprint_status", ERROR_MARKER),
            ("blockers", "fetch_blockers", ERROR_MARKER),
        ],
    )
    def test_single_section_failure_returns_200_with_marker(
        self, client, section_key, fetcher_name, return_value
    ):
        kwargs = {
            "shipped": SHIPPED,
            "awaiting": AWAITING,
            "mvp": MVP,
            "blockers": BLOCKERS,
        }
        key_map = {
            "fetch_shipped_since_last_sync": "shipped",
            "fetch_awaiting_po_decision": "awaiting",
            "fetch_mvp_sprint_status": "mvp",
            "fetch_blockers": "blockers",
        }
        kwargs[key_map[fetcher_name]] = return_value

        patches = _mock_all_sections(**kwargs)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            response = client.get("/digest/PROJ", headers=AUTH_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data[section_key] == ERROR_MARKER
        for other_key in ("shipped", "awaiting_decision", "mvp_status", "blockers"):
            if other_key != section_key:
                assert data[other_key] != ERROR_MARKER


class TestDigestExistenceCheck:
    def test_unknown_program_returns_404(self, client):
        with patch("services.sov_client.existence_check", return_value=False):
            response = client.get("/digest/PROJ", headers=AUTH_HEADERS)

        assert response.status_code == 404

    def test_sov_unreachable_on_existence_returns_503(self, client):
        with patch(
            "services.sov_client.existence_check",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            response = client.get("/digest/PROJ", headers=AUTH_HEADERS)

        assert response.status_code == 503


class TestDigestValidation:
    @pytest.mark.parametrize("program_code", ["proj", "1BAD", "A" * 21])
    def test_invalid_program_code_returns_422_without_sov_call(self, client, program_code):
        with patch("services.sov_client.existence_check") as mock_exists:
            response = client.get(f"/digest/{program_code}", headers=AUTH_HEADERS)

        assert response.status_code == 422
        mock_exists.assert_not_called()


class TestDigestAuth:
    def test_missing_api_key_returns_401(self, client):
        with patch("services.sov_client.existence_check") as mock_exists:
            response = client.get("/digest/PROJ")

        assert response.status_code == 401
        mock_exists.assert_not_called()

    def test_wrong_api_key_returns_401(self, client):
        with patch("services.sov_client.existence_check") as mock_exists:
            response = client.get("/digest/PROJ", headers={"X-API-Key": "bad-key"})

        assert response.status_code == 401
        mock_exists.assert_not_called()