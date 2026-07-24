"""Bundled Simply Nikah vector loading and validation."""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

from creative.render import nikah_vectors


def test_list_vectors_exposes_the_six_bundled_assets() -> None:
    expected = (
        "crescent",
        "dua_hands",
        "figure_silhouette",
        "lantern",
        "mihrab_arch",
        "star_tile",
    )
    assert nikah_vectors.list_vectors() == expected
    for name in expected:
        assert ElementTree.fromstring(nikah_vectors.get_vector(name)).tag.endswith("g")


def test_get_vector_composes_a_normalized_svg_fragment() -> None:
    fragment = nikah_vectors.get_vector(
        "crescent",
        x=12.5,
        y=24.0,
        scale=2.0,
        fill="#FD62AD",
    )

    root = ElementTree.fromstring(fragment)
    assert root.tag.endswith("g")
    assert root.attrib["data-vector"] == "crescent"
    assert root.attrib["transform"] == "translate(12.5 24) scale(2)"
    assert root.attrib["fill"] == "#FD62AD"
    assert any(child.tag.endswith("path") for child in root)


@pytest.mark.parametrize(
    ("name", "body", "message"),
    (
        (
            "unsafe",
            '<script type="application/ecmascript">alert(1)</script>',
            "unsafe SVG element",
        ),
        (
            "faceful",
            '<g data-figure="true" data-faceless="true" data-facial-feature="eyes">'
            '<path d="M0 0h1v1z"/></g>',
            "facial-feature marker",
        ),
        (
            "unmarked_figure",
            '<g data-figure="true"><path d="M0 0h1v1z"/></g>',
            "data-faceless",
        ),
    ),
)
def test_get_vector_rejects_unsafe_or_faceful_assets(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    body: str,
    message: str,
) -> None:
    vector_dir = tmp_path / "vectors"
    vector_dir.mkdir()
    (vector_dir / f"{name}.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        "<!-- Hand-authored placeholder — REPLACE with a curated CC0 asset at this path. -->"
        f"{body}</svg>",
        encoding="utf-8",
    )
    monkeypatch.setattr(nikah_vectors, "_VECTOR_DIR", vector_dir)

    with pytest.raises(ValueError, match=message):
        nikah_vectors.get_vector(name)
