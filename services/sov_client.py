"""Isolated read-only SOV HTTP client — sole module that performs outbound SOV I/O."""

from __future__ import annotations

import httpx

from app.config import settings

TIMEOUT_SECONDS = 8.0
MAX_ATTEMPTS = 3


def _headers() -> dict[str, str]:
    return {"X-API-Key": settings.sov_api_key}


def _normalize_program_code(program_code: str) -> str:
    return program_code.upper()


def _error_marker(message: str) -> dict:
    return {"status": "unavailable", "error": message}


def _sov_get(path: str) -> httpx.Response:
    """Read-only GET with 8s timeout and bounded retry on timeout or 5xx."""
    base = settings.sov_url.rstrip("/")
    url = f"{base}{path}"
    last_error: Exception | None = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                response = client.get(url, headers=_headers())
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS - 1:
                continue
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS - 1:
                continue
            raise

        if response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                f"Server error {response.status_code}",
                request=response.request,
                response=response,
            )
            if attempt < MAX_ATTEMPTS - 1:
                continue
            raise last_error

        return response

    if last_error is not None:
        raise last_error
    raise RuntimeError("unreachable: _sov_get exhausted attempts without response")


def existence_check(program_code: str) -> bool:
    """Return True when the program exists (200), False when absent (404)."""
    code = _normalize_program_code(program_code)
    response = _sov_get(f"/coding/programs/{code}")
    if response.status_code == 404:
        return False
    if response.status_code == 200:
        return True
    response.raise_for_status()
    return False


def _fetch_section(program_code: str, section_path: str) -> dict:
    code = _normalize_program_code(program_code)
    try:
        response = _sov_get(f"/coding/programs/{code}{section_path}")
        if response.status_code != 200:
            return _error_marker(f"HTTP {response.status_code}")
        return response.json()
    except httpx.HTTPError as exc:
        return _error_marker(str(exc))
    except ValueError as exc:
        return _error_marker(f"invalid JSON: {exc}")


def fetch_shipped_since_last_sync(program_code: str) -> dict:
    return _fetch_section(program_code, "/digest/shipped-since-last-sync")


def fetch_awaiting_po_decision(program_code: str) -> dict:
    return _fetch_section(program_code, "/digest/awaiting-po-decision")


def fetch_mvp_sprint_status(program_code: str) -> dict:
    return _fetch_section(program_code, "/digest/mvp-sprint-status")


def fetch_blockers(program_code: str) -> dict:
    return _fetch_section(program_code, "/digest/blockers")