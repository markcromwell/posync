"""GET /digest/{program_code} — per-program weekly-sync digest."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path

from app.auth import verify_api_key
from app.schemas.digest import (
    AwaitingDecisionItemOut,
    BlockerItemOut,
    DigestOut,
    MvpStatusOut,
    SectionErrorOut,
    ShippedItemOut,
)
from services import sov_client

router = APIRouter(prefix="/digest", tags=["digest"])

PROGRAM_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{0,19}$"


def _is_error_marker(raw: dict) -> bool:
    return raw.get("status") == "unavailable"


def _parse_list_section(raw: dict, item_model: type) -> list | SectionErrorOut:
    if _is_error_marker(raw):
        return SectionErrorOut.model_validate(raw)
    items = raw.get("items", [])
    return [item_model.model_validate(item) for item in items]


def _parse_object_section(raw: dict, model: type[MvpStatusOut]) -> MvpStatusOut | SectionErrorOut:
    if _is_error_marker(raw):
        return SectionErrorOut.model_validate(raw)
    return model.model_validate(raw)


@router.get("/{program_code}", response_model=DigestOut)
def get_digest(
    program_code: str = Path(..., pattern=PROGRAM_CODE_PATTERN),
    _: str = Depends(verify_api_key),
) -> DigestOut:
    try:
        exists = sov_client.existence_check(program_code)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"SOV unreachable: {exc}") from exc

    if not exists:
        raise HTTPException(status_code=404, detail="Program not found")

    shipped_raw = sov_client.fetch_shipped_since_last_sync(program_code)
    awaiting_raw = sov_client.fetch_awaiting_po_decision(program_code)
    mvp_raw = sov_client.fetch_mvp_sprint_status(program_code)
    blockers_raw = sov_client.fetch_blockers(program_code)

    return DigestOut(
        shipped=_parse_list_section(shipped_raw, ShippedItemOut),
        awaiting_decision=_parse_list_section(awaiting_raw, AwaitingDecisionItemOut),
        mvp_status=_parse_object_section(mvp_raw, MvpStatusOut),
        blockers=_parse_list_section(blockers_raw, BlockerItemOut),
    )