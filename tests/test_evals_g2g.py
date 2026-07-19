"""First real eval: the Glo2Go homepage fixture -> expected brief fields.

The regression guard for the brief extractor: a frozen snapshot of the LIVE site
(mimik-knowledge/evals/fixtures/, captured 2026-07-19) must keep producing the fields we
verified by hand during the G2 dogfood. Runs the PURE core (no network, no LLM) — the
vision enrichment is covered separately in test_brief_vision.py.

Evidence-bound means evidence-bound: the checks assert what the page really contains AND
that nothing was fabricated (no logo notes without vision, no invented fonts).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.services.brief_extraction import extract_brief_sections_from_html
from mimik_knowledge.evals import EvalCase, all_passed, run_evals

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "mimik-knowledge"
    / "evals"
    / "fixtures"
    / "glo2go_home_2026-07-19.html"
)

pytestmark = pytest.mark.skipif(not _FIXTURE.exists(), reason="G2G fixture not present")


def _check(sections) -> tuple[bool, str]:
    failures: list[str] = []
    snapshot = (sections.snapshot or "").lower()
    if "glo2go" not in snapshot.replace(" ", ""):
        failures.append(f"snapshot lost the brand name: {sections.snapshot!r}")
    hexes = {c.hex.lower() for c in sections.tokens.colors}
    # The house purple family must be visible in the site CSS (dogfood observed #7a4d7b).
    if not any(h.startswith("#7") or h.startswith("#8") for h in hexes):
        failures.append(f"no purple-family hex extracted: {sorted(hexes)}")
    # No fabrication: the pure core has no vision, so §2 must stay None.
    if sections.logo_notes is not None:
        failures.append("logo_notes fabricated without vision")
    if sections.voice_tone is None:
        failures.append("voice_tone note missing")
    return (not failures, "; ".join(failures) or "ok")


def test_g2g_brief_extraction_eval() -> None:
    html = _FIXTURE.read_text(encoding="utf-8")
    cases = [EvalCase(name="glo2go-home-2026-07-19", input={"html": html})]
    results = run_evals(
        cases,
        run=lambda inp: extract_brief_sections_from_html(inp["html"]),
        check=_check,
    )
    assert all_passed(results), [r.model_dump() for r in results]
