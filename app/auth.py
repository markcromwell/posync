"""X-API-Key verification for inbound digest requests."""

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Depends(api_key_header)) -> str:
    if not api_key or api_key != settings.digest_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key