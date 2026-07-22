"""Machine-readable creative direction for the three documented style profiles."""

from enum import Enum

from pydantic import BaseModel


class ImageSource(str, Enum):
    """Imagery sources supported by the creative engine."""

    AI_ILLUSTRATION = "ai_illustration"
    AI_REALISTIC = "ai_realistic"
    LICENSED_STOCK = "licensed_stock"
    PRODUCT_CUTOUT = "product_cutout"
    GENERATED_VECTOR = "generated_vector"


class Effect(str, Enum):
    """Visual effects that a style profile may permit."""

    GRADIENT_FADE = "gradient_fade"
    SOFT_SHADOW = "soft_shadow"
    LONG_SHADOW = "long_shadow"
    INNER_SHADOW = "inner_shadow"
    SHADING = "shading"
    BLUR = "blur"
    COLOR_GRADE = "color_grade"
    DUOTONE = "duotone"
    GRAIN = "grain"
    CUTOUT = "cutout"
    COLOR_BLOCK = "color_block"
    TEXT_PANEL_OVER_PHOTO = "text_panel_over_photo"
    BADGE_PILL = "badge_pill"


class LayoutArchetype(BaseModel):
    """A named composition pattern and the situation where it applies."""

    name: str
    use_when: str


class ColorRoleValue(BaseModel):
    """A named color assigned to a role in a client palette."""

    role: str
    name: str
    hex: str | None
    approx: bool = True


class StyleProfile(BaseModel):
    """The complete per-client creative direction contract."""

    id: str
    client: str
    one_line: str
    medium: str
    image_sources: list[ImageSource]
    palette: list[ColorRoleValue]
    typography: str
    layout_archetypes: list[LayoutArchetype]
    composition_principles: list[str]
    effect_vocabulary: list[Effect]
    motif_and_asset_needs: str
    copy_voice: str
    hard_guardrails: list[str]


PROFILES: dict[str, StyleProfile] = {
    "simply-nikah": StyleProfile(
        id="simply-nikah",
        client="Simply Nikah",
        one_line=(
            "Warm, Shariah-compliant matrimonial communication expressed through faceless "
            "flat-vector scenes, protective Islamic motifs, soft pink space, and decisive "
            "deep-plum emphasis."
        ),
        medium=(
            "Flat vector illustration. Any depicted person must be faceless or a silhouette. "
            "Real photography of people is outside this profile."
        ),
        image_sources=[
            ImageSource.GENERATED_VECTOR,
            ImageSource.AI_ILLUSTRATION,
        ],
        palette=[
            ColorRoleValue(role="primary", name="Simply Pink", hex="#FD62AD"),
            ColorRoleValue(role="accent", name="Soft Blush", hex="#F9C6DE"),
            ColorRoleValue(role="ink", name="Deep Plum", hex="#2B0A2E"),
            ColorRoleValue(role="cta_fill", name="Deep Plum", hex="#2B0A2E"),
            ColorRoleValue(role="secondary", name="Muted Lilac", hex="#9B7BA6"),
            ColorRoleValue(role="ground", name="Cloud White", hex="#FAF7FB"),
        ],
        typography=(
            "Heading character: Bold, high-emphasis display treatment in Deep Plum. The "
            "principal headline may isolate one decisive word in uppercase inside a solid plum "
            "box, such as ‘PROTECTED’ or ‘RIGHT INTENTION.’ The highlighted word is the visual "
            "entry point. Body character: Regular or lighter-weight supporting text in Deep "
            "Plum, calm and highly legible, with enough breathing room to preserve the gentle "
            "tone. Special use: An elegant script character may appear for greetings such as "
            "Eid content. It is an accent, not the default heading or body style. Wordmark: The "
            "‘simply nikāh’ wordmark sits top-center. Typeface status: No font family is "
            "supplied; confirm the approved heading, body, and greeting-script families at "
            "onboarding."
        ),
        layout_archetypes=[
            LayoutArchetype(
                name="Highlighted-Word Hero",
                use_when=(
                    "A single trust, intention, or protection message must land first; stack the "
                    "headline and support line above a central vector hero, with one key word "
                    "reversed out in a plum box."
                ),
            ),
            LayoutArchetype(
                name="Phone-and-Hijabi Product Story",
                use_when=(
                    "Showing the app experience; pair a phone mockup with a faceless illustrated "
                    "hijabi while keeping the device and modest figure as one central focal group."
                ),
            ),
            LayoutArchetype(
                name="Connected Match Cards",
                use_when=(
                    "Explaining matching or compatibility; arrange faceless avatar cards as a "
                    "balanced system joined by connector lines."
                ),
            ),
            LayoutArchetype(
                name="Mihrab or Lattice Frame",
                use_when=(
                    "Creating faith-led announcements and reflective content; place the message "
                    "or hero inside a mihrab-arch or Islamic-lattice framing motif."
                ),
            ),
            LayoutArchetype(
                name="Protection or Intention Symbol Hero",
                use_when=(
                    "Addressing trust, safety, or sincerity themes; center a shield-and-crescent or "
                    "hands-forming-heart symbol beneath a concise headline."
                ),
            ),
            LayoutArchetype(
                name="Ayah and Translation Panel",
                use_when=(
                    "The content leads with a Quran ayah; pair the Arabic calligraphy panel with "
                    "its translation and a gentle supporting CTA."
                ),
            ),
        ],
        composition_principles=[
            (
                "Hierarchy and emphasis: The highlighted word, central symbol, or calligraphy "
                "panel must establish the first read immediately."
            ),
            (
                "Contrast: Deep Plum against Soft Blush, Simply Pink, or Cloud White supplies "
                "clear text and CTA separation without making the composition harsh."
            ),
            (
                "Balance: Central and near-symmetrical arrangements reinforce calm, care, and "
                "trust; connector-card layouts should remain visually balanced even when the "
                "cards differ."
            ),
            (
                "Whitespace: Generous soft-pink or cloud-white negative space protects the modest, "
                "gentle tone and prevents ornamental assets from competing with the message."
            ),
            (
                "Pattern and repetition: Lattice geometry, arch forms, cards, and connector lines "
                "create unity through controlled repetition."
            ),
            (
                "Rhythm: Alternate compact headline or CTA groups with broad quiet areas; do not "
                "distribute ornament evenly across the whole canvas."
            ),
        ],
        effect_vocabulary=[
            Effect.GRADIENT_FADE,
            Effect.LONG_SHADOW,
            Effect.BLUR,
            Effect.COLOR_BLOCK,
            Effect.BADGE_PILL,
        ],
        motif_and_asset_needs=(
            "Motifs: Islamic geometric lattice or mashrabiya, mihrab arches, lanterns, shields, "
            "crescents, hearts, hands-forming-heart symbols, faceless avatar cards, connector "
            "paths, and calligraphy panels. Asset needs: The operator has no vector library for "
            "this brand. The engine must create a reusable, style-consistent vector set "
            "containing Islamic geometric lattice or mashrabiya patterns, mihrab arches, "
            "lanterns, phone mockups, faceless avatar and match-card variants, connector lines, "
            "shields, crescents, hearts, hands-forming-heart symbols, and calligraphy-panel "
            "frames. It must also be able to compose new flat-vector, faceless hero scenes from "
            "those parts rather than relying on people photography."
        ),
        copy_voice=(
            "Warm, respectful, gentle, and faith-led. A typical piece uses a concise values-led "
            "headline, a short support line, and a soft invitation rather than a hard sell. Faith "
            "content may lead with a Quran ayah in Arabic calligraphy followed by its translation, "
            "then a gentle CTA."
        ),
        hard_guardrails=[
            "Never use real photographs of people.",
            "Every human figure must be faceless or a silhouette.",
            (
                "Nothing immodest may be generated, sourced, or retained; modesty and haya are "
                "mandatory QA checks."
            ),
            "Keep the ‘simply nikāh’ wordmark top-center.",
            "Do not force a permanent header or footer band; the profile requires layout variety.",
            (
                "Do not let glow, shadows, or geometric pattern fills overwhelm the faith-led "
                "message or the generous whitespace."
            ),
        ],
    ),
    "glo2go-aesthetics": StyleProfile(
        id="glo2go-aesthetics",
        client="Glo2Go Aesthetics",
        one_line=(
            "Clean, medical-premium education built from credible real photography, restrained "
            "plum typography, generous white space, and polished information panels."
        ),
        medium=(
            "Real photography. Use licensed stock photography and Leonardo/API-generated realistic "
            "models or clinic scenes. Illustration is not part of this profile, and the owner must "
            "not appear."
        ),
        image_sources=[
            ImageSource.LICENSED_STOCK,
            ImageSource.AI_REALISTIC,
        ],
        palette=[
            ColorRoleValue(role="primary", name="Deep Plum/Purple", hex="#5A2A6B"),
            ColorRoleValue(role="ink", name="Deep Plum/Purple", hex="#5A2A6B"),
            ColorRoleValue(role="ground", name="White", hex="#FFFFFF"),
            ColorRoleValue(role="accent", name="Soft Lilac", hex=None),
        ],
        typography=(
            "Heading character: Bold sans serif in Deep Plum/Purple, clean and direct rather than "
            "expressive. Educational labels such as ‘Myth vs Fact’ should be immediately "
            "scannable. Body character: Lighter-weight sans serif with a calm, clinical-premium "
            "feel. Supporting copy should remain compact and readable over white or translucent "
            "panels. Case: Natural title or sentence case; avoid the all-caps, condensed meme "
            "treatment used by a retail profile. Logo treatment: ‘G2G Aesthetics’ appears in a "
            "rounded plum pill badge at the top-right. Typeface status: No font family is supplied; "
            "confirm the approved heading and body families at onboarding."
        ),
        layout_archetypes=[
            LayoutArchetype(
                name="Myth-vs-Fact Stacked Split",
                use_when=(
                    "Directly correcting a misconception; stack two photos, give each a clear Myth "
                    "or Fact label, and pair each image with its own restrained text panel."
                ),
            ),
            LayoutArchetype(
                name="Single-Photo Education Hero",
                use_when=(
                    "Communicating one key treatment or skin insight; combine one strong hero photo "
                    "with a concise headline and a semi-transparent white text panel over the image "
                    "where legibility requires it."
                ),
            ),
            LayoutArchetype(
                name="Educational Carousel System",
                use_when=(
                    "A topic needs several steps or claims; keep a repeated slide grid, stable logo "
                    "position, consistent plum hierarchy, and ample white space across the series."
                ),
            ),
        ],
        composition_principles=[
            (
                "Hierarchy: Headline, education label, explanation, and CTA should read in that "
                "order without decorative competition."
            ),
            (
                "Whitespace: White ground and open margins are load-bearing; they create the "
                "restrained, premium clinic character."
            ),
            (
                "Contrast and legibility: Plum type and semi-transparent white or plum panels must "
                "separate copy from photographic detail."
            ),
            (
                "Balance: Photography and information panels should share the frame without either "
                "side feeling crowded or visually underweighted."
            ),
            (
                "Proximity: Keep each Myth or Fact label physically close to the photo and "
                "explanation it qualifies."
            ),
            (
                "Unity and rhythm: Carousel slides repeat the badge, type scale, panel treatment, "
                "and spacing so the series reads as one clinical education system."
            ),
        ],
        effect_vocabulary=[
            Effect.TEXT_PANEL_OVER_PHOTO,
            Effect.BADGE_PILL,
            Effect.SOFT_SHADOW,
        ],
        motif_and_asset_needs=(
            "Motifs: Rounded plum brand badge, clean Myth and Fact labels, translucent information "
            "panels, real skin or clinic imagery, and consistent plum educational typography. "
            "Asset needs: The engine must source suitable licensed stock photography, checking "
            "Unsplash and Pexels free tiers first, and must create realistic model or clinic scenes "
            "through Leonardo/API when stock is insufficient. The operator has no prepared vector "
            "asset library for this profile, so the engine must also create reusable text-panel "
            "overlays and the rounded ‘G2G Aesthetics’ plum pill badge, then apply the consistent "
            "plum heading, label, and body hierarchy. No owner portrait asset should be requested "
            "or generated."
        ),
        copy_voice=(
            "Educational, science-led, professional, and reassuring. A typical structure is a clear "
            "myth or question, a concise factual correction or explanation, then the CTA: ‘DM to "
            "book your free consultation.’ Avoid sensational framing and keep claims medically "
            "credible."
        ),
        hard_guardrails=[
            (
                "The owner must never be shown; use licensed stock or generated realistic models "
                "and clinic scenes instead."
            ),
            "Use real-photography treatment, not illustration.",
            "Imagery must remain tasteful and medically credible.",
            "Reject wild, sensational, or unsupported treatment claims.",
            "Keep the ‘G2G Aesthetics’ rounded plum pill badge at the top-right.",
            (
                "Preserve generous white space and restrained effects; decorative treatments must "
                "not make the clinic feel loud or gimmicky."
            ),
        ],
    ),
    "island-cart": StyleProfile(
        id="island-cart",
        client="Island Cart",
        one_line=(
            "High-energy Sri Lankan product advertising that combines actual product cutouts, hard "
            "orange-and-white geometry, huge witty type, and instantly scannable price and benefit "
            "cues."
        ),
        medium=(
            "Product photography plus lifestyle photography and meme-style display type. The actual "
            "product is the commercial focal point; lifestyle imagery provides the relatable setup "
            "or use context."
        ),
        image_sources=[
            ImageSource.PRODUCT_CUTOUT,
            ImageSource.LICENSED_STOCK,
            ImageSource.GENERATED_VECTOR,
        ],
        palette=[
            ColorRoleValue(role="primary", name="Bold Orange", hex="#F26522"),
            ColorRoleValue(role="accent", name="Bold Orange", hex="#F26522"),
            ColorRoleValue(role="ink", name="Black", hex="#000000"),
            ColorRoleValue(role="ground", name="White", hex="#FFFFFF"),
        ],
        typography=(
            "Heading character: Huge, bold, condensed sans serif in caps. The hook behaves like a "
            "meme caption: fast, witty, and dominant, as in ‘SITTING ALL DAY IS SLOWLY TURNING "
            "EVERYONE INTO A CROISSANT’ or ‘WAS MADE FOR PEOPLE WHO…’ Body character: Bold, clean "
            "sans serif for the benefit line, product name, price, and CTA. It must remain legible "
            "at a glance and subordinate to the joke or hook. Case: All caps for the principal gag "
            "or hook; product details may use the clearest case for fast retail scanning. Logo "
            "treatment: The ‘IslandCart’ logo sits top-left. Typeface status: No font family is "
            "supplied; confirm the approved condensed display and supporting sans-serif families at "
            "onboarding."
        ),
        layout_archetypes=[
            LayoutArchetype(
                name="Diagonal Lifestyle Split",
                use_when=(
                    "A relatable lifestyle problem sets up the product; divide the canvas with a "
                    "hard orange-and-white diagonal, pair the lifestyle photo with a huge-type gag, "
                    "and keep the logo top-left."
                ),
            ),
            LayoutArchetype(
                name="Cutout Product Offer",
                use_when=(
                    "Creating a direct sales post; place the background-removed product on a clean "
                    "ground with a drop shadow, price-tag pill, product name, and one clear benefit "
                    "line."
                ),
            ),
            LayoutArchetype(
                name="Dark-Photo Type Slam",
                use_when=(
                    "The lifestyle photo can carry high-impact contrast; place the bold hook over a "
                    "dark photographic area and keep product, price, or CTA easy to find."
                ),
            ),
        ],
        composition_principles=[
            (
                "Emphasis: The gag or product must dominate immediately; secondary details cannot "
                "compete for the first read."
            ),
            (
                "Contrast: Orange, white, and black should create hard separation between hook, "
                "product, price, and CTA."
            ),
            (
                "Movement: Diagonal color blocks drive the eye through the composition and supply "
                "the brand's visual energy."
            ),
            (
                "Asymmetrical balance: Offset a large text mass with the lifestyle image or product "
                "cutout so the composition remains punchy without becoming unstable."
            ),
            "Hierarchy: Hook first, product or benefit second, price third, CTA last.",
            (
                "Rhythm and proximity: Keep product name, benefit, and price close enough to scan as "
                "one retail unit; use shifts in scale rather than extra decoration to create rhythm."
            ),
        ],
        effect_vocabulary=[
            Effect.COLOR_BLOCK,
            Effect.CUTOUT,
            Effect.SOFT_SHADOW,
            Effect.BADGE_PILL,
        ],
        motif_and_asset_needs=(
            "Motifs: Hard diagonal blocks, oversized condensed captions, isolated product cutouts, "
            "price-tag pills, benefit lines, and high-contrast lifestyle-photo fields. Asset needs: "
            "The engine must accept the client's actual product photos, remove their backgrounds, "
            "produce clean cutouts, and composite them with a controlled drop shadow. The operator "
            "has no ready-made vector library for the campaign system, so the engine must create "
            "reusable diagonal color-block shapes and price-tag badge or pill assets. It must also "
            "source suitable lifestyle photos when required and establish an approved bold "
            "condensed display type treatment for the hooks."
        ),
        copy_voice=(
            "Witty, relatable, meme-like, and commercial. The typical structure is a large hook or "
            "everyday observation, a direct product benefit, the accurate product name and price, "
            "then a simple CTA. The joke earns attention; the product information closes the sale."
        ),
        hard_guardrails=[
            "Product identity and price must be accurate in every creative.",
            (
                "Use the client's actual product photography for the product focal asset; do not "
                "replace it with a different or invented product."
            ),
            "Bold Orange is load-bearing and must remain a dominant brand signal.",
            "Keep the ‘IslandCart’ logo top-left.",
            (
                "Maintain high-contrast, fast-scanning hierarchy even when the headline is "
                "intentionally oversized."
            ),
            (
                "Keep the tone fun and commercial without letting the gag obscure the product, "
                "benefit, price, or CTA."
            ),
        ],
    ),
}


def get_style_profile(profile_id: str) -> StyleProfile:
    """Return a style profile by ID, or raise a clear error for an unknown ID."""

    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        available_profiles = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Unknown style profile {profile_id!r}. Available profiles: {available_profiles}."
        ) from exc
