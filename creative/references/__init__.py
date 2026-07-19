"""References — vetted aesthetic references distilled into style descriptors for L2.

References guide STYLE, the brief guides BRAND, copy + layout guide STRUCTURE; a reference
is never reproduced. The fit critic scores each candidate and states its reasoning; a
human approves the final set.
"""

from creative.references.fit_critic import (
    PROMPT_REF,
    FitVerdict,
    ReferenceCriticError,
    StyleDescriptor,
    assess_reference,
    to_contract_reference,
    vet_references,
)

__all__ = [
    "PROMPT_REF",
    "FitVerdict",
    "ReferenceCriticError",
    "StyleDescriptor",
    "assess_reference",
    "to_contract_reference",
    "vet_references",
]
