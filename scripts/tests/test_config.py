"""Unit tests for app/config.py — Settings singleton and env mapping."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.config import Settings


def test_settings_load_defaults():
    with patch.dict(os.environ, {}, clear=True):
        s = Settings(_env_file=None)
    assert s.digest_api_key == ""
    assert s.sov_url == "http://localhost:8765"
    assert s.sov_api_key == ""


def test_settings_picks_up_overridden_digest_api_key():
    with patch.dict(os.environ, {"DIGEST_API_KEY": "override-secret"}, clear=True):
        s = Settings(_env_file=None)
    assert s.digest_api_key == "override-secret"