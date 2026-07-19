"""Auto brand-QA critic — the code half of the rubric (mimik-knowledge/rubrics/brand_qa.md).

Hard checks are deterministic code: exact dims, safe zones, logo presence, WCAG contrast.
The scrim is conditional — raised via QAReport.needs_scrim only when a text zone over
imagery fails contrast, never applied blanket.
"""

from creative.qa.checks import QAReport, run_brand_qa

__all__ = ["QAReport", "run_brand_qa"]
