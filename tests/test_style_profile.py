import pytest

from creative.style_profile import ImageSource, PROFILES, StyleProfile, get_style_profile


EXPECTED_IMAGE_SOURCES: dict[str, list[ImageSource]] = {
    "simply-nikah": [ImageSource.GENERATED_VECTOR, ImageSource.AI_ILLUSTRATION],
    "glo2go-aesthetics": [ImageSource.LICENSED_STOCK, ImageSource.AI_REALISTIC],
    "island-cart": [
        ImageSource.PRODUCT_CUTOUT,
        ImageSource.LICENSED_STOCK,
        ImageSource.GENERATED_VECTOR,
    ],
}


def test_all_style_profiles_load_with_ranked_sources_and_guardrails() -> None:
    assert set(PROFILES) == {
        "simply-nikah",
        "glo2go-aesthetics",
        "island-cart",
    }

    for profile_id, expected_sources in EXPECTED_IMAGE_SOURCES.items():
        profile = get_style_profile(profile_id)

        assert isinstance(profile, StyleProfile)
        assert profile.id == profile_id
        assert profile.image_sources == expected_sources
        assert profile.image_sources
        assert profile.hard_guardrails


def test_simply_nikah_guardrails_require_no_real_people_photos_and_modesty() -> None:
    guardrails = get_style_profile("simply-nikah").hard_guardrails

    assert "Never use real photographs of people." in guardrails
    assert (
        "Nothing immodest may be generated, sourced, or retained; modesty and haya are "
        "mandatory QA checks."
    ) in guardrails


def test_missing_palette_hex_remains_unset_and_approximate() -> None:
    accent = next(
        color for color in get_style_profile("glo2go-aesthetics").palette if color.role == "accent"
    )

    assert accent.hex is None
    assert accent.approx is True


def test_unknown_profile_id_raises_clear_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown style profile 'not-a-profile'"):
        get_style_profile("not-a-profile")
