"""Unit tests for app/schemas/digest.py — DigestOut serialization."""

from __future__ import annotations

from app.schemas.digest import (
    AwaitingDecisionItemOut,
    BlockerItemOut,
    DigestOut,
    MvpStatusOut,
    SectionErrorOut,
    ShippedItemOut,
)


class TestDigestOutPopulated:
    def test_serializes_fully_populated_digest(self):
        digest = DigestOut(
            shipped=[ShippedItemOut(id=1, title="Feature A")],
            awaiting_decision=[AwaitingDecisionItemOut(id=2, summary="Decision needed")],
            mvp_status=MvpStatusOut(sprint="Sprint 3", percent_complete=75),
            blockers=[BlockerItemOut(id=3, description="Blocked on review")],
        )

        data = digest.model_dump()

        assert set(data.keys()) == {"shipped", "awaiting_decision", "mvp_status", "blockers"}
        assert data["shipped"] == [{"id": 1, "title": "Feature A"}]
        assert data["awaiting_decision"] == [{"id": 2, "summary": "Decision needed"}]
        assert data["mvp_status"] == {"sprint": "Sprint 3", "percent_complete": 75}
        assert data["blockers"] == [{"id": 3, "description": "Blocked on review"}]


class TestDigestOutDegraded:
    def test_serializes_degraded_sections_with_error_markers(self):
        error = SectionErrorOut(error="timeout")
        digest = DigestOut(
            shipped=[ShippedItemOut(id=1)],
            awaiting_decision=error,
            mvp_status=error,
            blockers=error,
        )

        data = digest.model_dump()

        assert data["shipped"] == [{"id": 1}]
        assert data["awaiting_decision"] == {"status": "unavailable", "error": "timeout"}
        assert data["mvp_status"] == {"status": "unavailable", "error": "timeout"}
        assert data["blockers"] == {"status": "unavailable", "error": "timeout"}

    def test_serializes_all_sections_degraded(self):
        digest = DigestOut(
            shipped=SectionErrorOut(error="shipped failed"),
            awaiting_decision=SectionErrorOut(error="awaiting failed"),
            mvp_status=SectionErrorOut(error="mvp failed"),
            blockers=SectionErrorOut(error="blockers failed"),
        )

        data = digest.model_dump()

        for key in ("shipped", "awaiting_decision", "mvp_status", "blockers"):
            assert data[key]["status"] == "unavailable"
            assert "failed" in data[key]["error"]