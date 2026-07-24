"""Generation-loop safety tests for the design-critic gate flag."""

from __future__ import annotations

from pathlib import Path

import pytest
from mimik_contracts import Brand, BrandTokens, ColorRole, CopyBlock

from api.services import creative_generation as cg
from creative.critique.gate import RetryDirective
from creative.critique.report import AxisScore, CritiqueReport
from creative.qa.checks import QAReport


def _brand() -> Brand:
    return Brand(
        tenant_id="tenant-1",
        client_id="client-1",
        name="Test brand",
        slug="test-brand",
        tokens=BrandTokens(colors=[ColorRole(name="ink", hex="#112233")]),
    )


def _failure_report() -> CritiqueReport:
    return CritiqueReport(
        axes=[
            AxisScore(
                axis="A2",
                name="Visual hierarchy",
                objective=False,
                score=1,
                findings=["headline competes with ornament"],
                rejection_element="headline",
                anchor="A2 anchor 1: attention scatters",
            )
        ],
        craft_score=1.0,
        verdict="FAIL",
        dominant_failing_axis="A2",
    )


def _render_result(artifact_dir: Path, params: dict) -> tuple:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    svg_path = artifact_dir / "creative.svg"
    preview_path = artifact_dir / "preview.png"
    svg_path.write_text("<svg/>", encoding="utf-8")
    preview_path.write_bytes(b"png")
    qa_report = QAReport(passed=True, failures=[])
    return (svg_path, preview_path, None, qa_report, params), []


def test_critic_gate_defaults_off() -> None:
    assert cg.CRITIC_GATING_ENABLED is False


async def test_gate_off_is_advisory_and_renders_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = 0

    async def fake_render_variants(**kwargs: object) -> tuple:
        nonlocal calls
        calls += 1
        return _render_result(kwargs["artifact_dir"], kwargs["base_params"])

    monkeypatch.setattr(cg, "_render_variants", fake_render_variants)
    monkeypatch.setattr(cg, "run_critique", lambda *_args, **_kwargs: _failure_report())
    monkeypatch.setattr(cg, "CRITIC_GATING_ENABLED", False)

    outcome = await cg._render_with_critic_gate(
        brand=_brand(),
        profile_id="generic",
        copy_block=CopyBlock(headline="Headline"),
        format_key="ig_post",
        image_path=tmp_path / "source.png",
        artifact_dir=tmp_path / "creative",
        base_params={},
        source_kind="stub",
        levers=[cg._VariantLever(label="natural", key="natural", value="default")],
    )

    assert calls == 1
    assert outcome.regenerations == 0
    assert outcome.parked is False
    assert outcome.report.advisory is True


async def test_gate_on_regenerates_three_times_then_parks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = 0

    async def fake_render_variants(**kwargs: object) -> tuple:
        nonlocal calls
        calls += 1
        return _render_result(kwargs["artifact_dir"], kwargs["base_params"])

    monkeypatch.setattr(cg, "_render_variants", fake_render_variants)
    monkeypatch.setattr(cg, "run_critique", lambda *_args, **_kwargs: _failure_report())
    monkeypatch.setattr(cg, "CRITIC_GATING_ENABLED", True)

    outcome = await cg._render_with_critic_gate(
        brand=_brand(),
        profile_id="generic",
        copy_block=CopyBlock(headline="Headline"),
        format_key="ig_post",
        image_path=tmp_path / "source.png",
        artifact_dir=tmp_path / "creative",
        base_params={},
        source_kind="stub",
        levers=[cg._VariantLever(label="natural", key="natural", value="default")],
    )

    assert calls == 4  # initial render + hard cap of 3 regenerations
    assert outcome.regenerations == 3
    assert outcome.parked is True
    assert outcome.decision.retry_directive is RetryDirective.NEEDS_ART_DIRECTION
    assert len(outcome.history) == 4
