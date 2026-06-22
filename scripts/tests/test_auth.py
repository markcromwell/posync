"""Unit tests for app/auth.py — X-API-Key verification."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import create_app
from app.auth import verify_api_key


@pytest.fixture
def client():
    with patch("app.config.settings.digest_api_key", "test-digest-key"):
        yield TestClient(create_app())


class TestVerifyApiKeyDependency:
    def test_passes_when_header_matches(self):
        with patch("app.config.settings.digest_api_key", "test-digest-key"):
            assert verify_api_key("test-digest-key") == "test-digest-key"

    def test_raises_401_when_header_missing(self):
        with patch("app.config.settings.digest_api_key", "test-digest-key"):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(None)
            assert exc_info.value.status_code == 401

    def test_raises_401_when_header_mismatched(self):
        with patch("app.config.settings.digest_api_key", "test-digest-key"):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key("wrong-key")
            assert exc_info.value.status_code == 401


class TestVerifyApiKeyViaDigestRoute:
    def test_missing_api_key_returns_401(self, client):
        with patch("services.sov_client.existence_check") as mock_exists:
            response = client.get("/digest/PROJ")
            assert response.status_code == 401
            mock_exists.assert_not_called()

    def test_wrong_api_key_returns_401(self, client):
        with patch("services.sov_client.existence_check") as mock_exists:
            response = client.get("/digest/PROJ", headers={"X-API-Key": "wrong-key"})
            assert response.status_code == 401
            mock_exists.assert_not_called()

    def test_valid_api_key_passes_auth(self, client):
        with (
            patch("services.sov_client.existence_check", return_value=True),
            patch(
                "services.sov_client.fetch_shipped_since_last_sync",
                return_value={"items": []},
            ),
            patch(
                "services.sov_client.fetch_awaiting_po_decision",
                return_value={"items": []},
            ),
            patch(
                "services.sov_client.fetch_mvp_sprint_status",
                return_value={"phase": "mvp"},
            ),
            patch("services.sov_client.fetch_blockers", return_value={"items": []}),
        ):
            response = client.get("/digest/PROJ", headers={"X-API-Key": "test-digest-key"})
            assert response.status_code == 200