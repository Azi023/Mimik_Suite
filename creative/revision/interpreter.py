"""Revision interpreter for bounded, safe instruction parsing."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from creative.knowledge.feedback import rules_as_prompt_block
from creative.prompting import (
    default_generate,
    fill_slots,
    parse_json_reply,
    slot,
    tag_stripper,
)
from mimik_contracts import RegionAsk, RevisionZone

logger = logging.getLogger(__name__)

@dataclass
class InterpretedAsk:
    params: dict[str, object] = field(default_factory=dict)
    text_edits: dict[str, str] = field(default_factory=dict)
    wants_new_image: bool = False


_SYSTEM_TEMPLATE = """You are an expert art director revising a creative.
The user wants to revise a region of the creative.
{rules}

User Instruction:
<instruction>{instruction}</instruction>

Output JSON exactly in this format, selecting only applicable fields to change. Do not output anything else.
{
  "params": {
    "panel_anchor": "left" | "right" | "top" | "bottom",
    "text_alignment": "left" | "center" | "right",
    "subject_zoom": float,
    "badge_background_luminance": float,
    "text_region": string,
    "cta_emphasis": "high" | "low"
  },
  "text_edits": {
    "headline": string,
    "subhead": string,
    "cta": string
  },
  "wants_new_image": boolean
}
"""


def _deterministic_keyword_table(ask: RegionAsk) -> InterpretedAsk:
    params: dict[str, object] = {}
    text_lower = ask.instruction.lower()

    for keyword in ("left", "right", "top", "bottom"):
        if keyword in text_lower:
            params["panel_anchor"] = keyword
            break

    if "smaller" in text_lower:
        params["subject_zoom"] = 0.8
    elif "larger" in text_lower:
        params["subject_zoom"] = 1.2

    if "lighter" in text_lower:
        params["badge_background_luminance"] = 0.0
    elif "darker" in text_lower:
        params["badge_background_luminance"] = 1.0

    wants_new_image = False
    if ask.zone in (RevisionZone.BACKGROUND, RevisionZone.IMAGERY):
        if any(
            kw in text_lower for kw in ("swap", "change", "different photo", "new image")
        ):
            wants_new_image = True

    if ask.zone == RevisionZone.CTA:
        if "bigger" in text_lower:
            params["cta_emphasis"] = "high"
        elif "smaller" in text_lower:
            params["cta_emphasis"] = "low"

    return InterpretedAsk(
        params=params,
        text_edits={},
        wants_new_image=wants_new_image,
    )


def interpret_ask(
    ask: RegionAsk,
    *,
    profile_id: str | None,
    current_params: Mapping[str, object],
) -> InterpretedAsk:
    default_result = _deterministic_keyword_table(ask)

    if os.environ.get("REVISE_LLM") != "1":
        return default_result

    try:
        generate, _ = default_generate()
        rules_block = rules_as_prompt_block(profile_id)

        sanitized_instruction = tag_stripper("instruction").sub("", ask.instruction)
        prompt = fill_slots(
            _SYSTEM_TEMPLATE,
            {
                "rules": rules_block,
                "instruction": slot(sanitized_instruction),
            },
        )

        reply = generate(prompt)
        parsed = parse_json_reply(reply)

        llm_params = {}
        if "params" in parsed and isinstance(parsed["params"], dict):
            p = parsed["params"]
            if p.get("panel_anchor") in {"left", "right", "top", "bottom"}:
                llm_params["panel_anchor"] = p["panel_anchor"]
            if p.get("text_alignment") in {"left", "center", "right"}:
                llm_params["text_alignment"] = p["text_alignment"]
            if isinstance(p.get("subject_zoom"), (int, float)):
                llm_params["subject_zoom"] = float(p["subject_zoom"])
            if isinstance(p.get("badge_background_luminance"), (int, float)):
                llm_params["badge_background_luminance"] = float(p["badge_background_luminance"])
            if isinstance(p.get("text_region"), str):
                llm_params["text_region"] = p["text_region"]
            if p.get("cta_emphasis") in {"high", "low"}:
                llm_params["cta_emphasis"] = p["cta_emphasis"]

        llm_text_edits = {}
        if "text_edits" in parsed and isinstance(parsed["text_edits"], dict):
            te = parsed["text_edits"]
            if isinstance(te.get("headline"), str):
                llm_text_edits["headline"] = te["headline"]
            if isinstance(te.get("subhead"), str):
                llm_text_edits["subhead"] = te["subhead"]
            if isinstance(te.get("cta"), str):
                llm_text_edits["cta"] = te["cta"]

        llm_wants_new_image = False
        if "wants_new_image" in parsed and isinstance(parsed["wants_new_image"], bool):
            llm_wants_new_image = parsed["wants_new_image"]

        return InterpretedAsk(
            params=llm_params,
            text_edits=llm_text_edits,
            wants_new_image=llm_wants_new_image,
        )
    except Exception as exc:
        logger.warning("interpret_ask: LLM path failed (%s), falling back to keywords", exc)
        return default_result
