"""Pydantic response models for the digest JSON shape."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SectionErrorOut(BaseModel):
    status: Literal["unavailable"] = "unavailable"
    error: str


class ShippedItemOut(BaseModel):
    model_config = ConfigDict(extra="allow")


class AwaitingDecisionItemOut(BaseModel):
    model_config = ConfigDict(extra="allow")


class MvpStatusOut(BaseModel):
    model_config = ConfigDict(extra="allow")


class BlockerItemOut(BaseModel):
    model_config = ConfigDict(extra="allow")


class DigestOut(BaseModel):
    shipped: list[ShippedItemOut] | SectionErrorOut
    awaiting_decision: list[AwaitingDecisionItemOut] | SectionErrorOut
    mvp_status: MvpStatusOut | SectionErrorOut
    blockers: list[BlockerItemOut] | SectionErrorOut