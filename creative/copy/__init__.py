"""Copy (L0) — the words that feed L4. AI-drafts on the free Gemini TEXT API, human-approved."""

from creative.copy.gemini_text import generate_text
from creative.copy.l0 import PROMPT_REF, CopyDraftError, draft_copy

__all__ = ["PROMPT_REF", "CopyDraftError", "draft_copy", "generate_text"]
