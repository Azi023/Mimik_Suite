"""A5 — Iconography integrity & recognizability (VISION, advisory).

Catches the operator's two loudest named failures (DESIGN_CRITIC_SPEC.md §0):
  F2 — a composed symbol that reads as a rendering glitch (shield+crescent).
  F3 — a shape that cannot be named by a stranger in ~1 second (the hands-heart blob).

Reuses the existing free-tier vision seam (`creative.vision.gemini_vision.generate_vision`,
constraint #7 — no paid APIs) rather than inventing a new client, and the shared strict-JSON
reply parser (`creative.prompting.parse_json_reply`). The vision call runs in a low-privilege
context: fixed prompt + our own rendered pixels, no client freeform text, no tools.

Degradation contract: a missing/broken vision backend degrades A5 to `score=None` (unknown,
advisory) — it NEVER crashes the critic. Advisory-only in Slice 1.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from creative.prompting import parse_json_reply
from creative.vision.gemini_vision import generate_vision

from .report import AxisScore

logger = logging.getLogger(__name__)

# The literal naming test. The model writes observations (name each symbol) BEFORE any verdict
# — spec §3.1 "findings before scores" — and the prompt carries no threshold to steer toward.
_A5_PROMPT = """You are a strict brand-iconography reviewer looking at ONE social-ad creative.

Your ONLY job: the SYMBOL NAMING TEST. For every distinct icon, symbol, mark, or graphic
device on the canvas (ignore plain text/letters, ignore the background wash), do this:

1. Look at the symbol in isolation.
2. Name what it literally is, as a stranger seeing it for ~1 second would (e.g. "a crescent
   moon", "a heart", "two people cards joined by a line", "a shield").
3. Give it exactly ONE verdict. Apply the naming test literally — the verdict is about whether
   a stranger names ONE real-world object with confidence, not whether YOU can describe the
   pixels. Describing loose parts ("a pink shape with two ovals", "an X and a Y floating") is
   NOT naming an object — it is a failure of the naming test.
   - "instant"        = a stranger confidently names it as ONE real-world object in ~1 second;
                        if it is a COMPOSED mark (one shape containing/combining another), the
                        parts resolve into ONE coherent, intentional-looking icon.
   - "generic"        = you CAN confidently name it as one clear real-world object, but it is
                        clip-art-grade / bland. Use this ONLY when the single object is obvious;
                        never for a mark whose parts don't integrate.
   - "unrecognizable" = you CANNOT confidently name it as one real-world object in ~1 second.
                        This INCLUDES a composed mark whose parts read as separate floating
                        shapes that do not fuse into one coherent object — if your best answer
                        is "some shapes" or "an X and a Y" rather than a single confident name,
                        it is "unrecognizable". "I can't tell" belongs here, never "instant".
   - "glitch"         = it reads as a rendering error / broken composite / artifact — outlines
                        cut through each other, layers are misaligned, it looks machine-broken.

Do not be generous. A composed symbol whose pieces float apart, overlap wrongly, or fight each
other is "unrecognizable" (parts don't fuse) or "glitch" (reads as broken) — it is NOT
"generic". A vague blob is "unrecognizable", never "instant".

Reply with ONLY this JSON object (no prose, no code fence):
{
  "symbols": [
    {"name": "<what it literally is, or 'unnameable blob'>",
     "verdict": "instant|generic|unrecognizable|glitch",
     "reason": "<one short clause>"}
  ],
  "overall": "<one sentence>"
}"""

# verdict -> (caps the score at, is a hard-fail?)
_INSTANT = "instant"
_GENERIC = "generic"
_UNRECOGNIZABLE = "unrecognizable"
_GLITCH = "glitch"
_VALID_VERDICTS = {_INSTANT, _GENERIC, _UNRECOGNIZABLE, _GLITCH}


def _score_symbols(symbols: list[dict]) -> AxisScore:
    findings: list[str] = []
    observations: list[str] = []
    verdicts: list[str] = []
    rejection_element: str | None = None
    for sym in symbols:
        name = str(sym.get("name", "unnamed")).strip() or "unnamed"
        verdict = str(sym.get("verdict", "")).strip().lower()
        reason = str(sym.get("reason", "")).strip()
        if verdict not in _VALID_VERDICTS:
            verdict = _UNRECOGNIZABLE  # an un-parseable verdict is a failure to name, not a pass
        verdicts.append(verdict)
        observations.append(
            f"Symbol '{name}' was observed as {verdict}"
            + (f" because {reason}." if reason else ".")
        )
        if verdict != _INSTANT:
            rejection_element = rejection_element or f"symbol '{name}'"
            findings.append(f"symbol '{name}' → {verdict}" + (f": {reason}" if reason else ""))

    if not verdicts:
        return AxisScore(
            axis="A5",
            name="Iconography recognizability",
            objective=False,
            score=5,
            findings=["A5: no distinct symbols detected on the canvas — nothing to fail."],
            observations=["No distinct iconographic element was observed."],
            anchor="every motif instantly reads (no iconography present)",
        )

    has_glitch = _GLITCH in verdicts
    has_unrecognizable = _UNRECOGNIZABLE in verdicts
    has_generic = _GENERIC in verdicts

    if has_glitch:
        score, anchor = 1, "◆ a symbol reads as a glitch/artifact (F2 showstopper)"
    elif has_unrecognizable:
        score, anchor = 1, "a symbol fails the naming test (F3 blob)"
    elif has_generic:
        score, anchor = 3, "all symbols nameable but one is generic/clip-art-grade"
    else:
        score, anchor = 5, "every motif instantly reads; composites resolve into one mark"

    return AxisScore(
        axis="A5",
        name="Iconography recognizability",
        objective=False,
        score=score,
        findings=findings or ["every symbol named instantly."],
        observations=observations,
        rejection_element=rejection_element if score <= 2 else None,
        anchor=anchor,
        hard_fail=has_glitch,  # ◆ F2-class glitch is a showstopper regardless of the mean
    )


def _degraded(reason: str) -> AxisScore:
    return AxisScore(
        axis="A5",
        name="Iconography recognizability",
        objective=False,
        score=None,
        findings=[f"A5 vision backend unavailable ({reason}) — degraded to unknown (advisory)."],
    )


def critique_a5(
    png_bytes: bytes,
    *,
    generate: Callable[[str], str] | None = None,
) -> AxisScore:
    """Score A5 (iconography recognizability) via the free vision seam.

    `generate` is injectable for tests (a prompt->reply callable); the default calls the
    free Gemini vision client on `png_bytes`. Any backend/parse failure degrades to unknown.
    """
    if generate is None:

        def generate(prompt: str) -> str:
            return generate_vision(prompt, png_bytes, "image/png")

    try:
        reply = generate(_A5_PROMPT)
    except Exception as exc:  # noqa: BLE001 — advisory axis must never crash the critic
        logger.warning("A5 vision call failed: %s", exc)
        return _degraded(str(exc) or exc.__class__.__name__)

    try:
        data = parse_json_reply(reply)
        symbols = data.get("symbols")
        if not isinstance(symbols, list):
            raise ValueError("reply missing a 'symbols' list")
    except ValueError as exc:
        logger.warning("A5 vision reply not parseable: %s", exc)
        return _degraded(f"unparseable vision reply: {exc}")

    return _score_symbols([s for s in symbols if isinstance(s, dict)])
