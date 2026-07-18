"""The adapter registry resolves both build-phase backends; generation is deferred to P2."""

from __future__ import annotations

import pytest

from creative.adapters import available_backends, get_adapter
from mimik_contracts import ImageBackend


def test_registry_resolves_build_phase_backends() -> None:
    backends = available_backends()
    assert ImageBackend.CHATGPT_BROWSER in backends
    assert ImageBackend.GEMINI_FREE in backends


def test_get_adapter_returns_matching_backend() -> None:
    adapter = get_adapter(ImageBackend.GEMINI_FREE)
    assert adapter.backend == ImageBackend.GEMINI_FREE


def test_unregistered_backend_raises() -> None:
    with pytest.raises(KeyError):
        get_adapter(ImageBackend.IDEOGRAM)  # paid API, not registered until there's budget
