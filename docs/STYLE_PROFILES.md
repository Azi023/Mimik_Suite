# Style Profiles

## Purpose

A Style Profile is the per-client creative contract that makes the shared Mimik Suite engine render in that client's design language. It defines what imagery the engine may use, how it composes a piece, which effects belong to the brand, which assets it must create or source, and which rules QA must enforce.

This specification is intentionally source-bound. It does not assign font families or brand facts that were not supplied. Every supplied hex value is marked **(approx — confirm at onboarding)**. When the source names a color but provides no hex, the profile records that gap instead of guessing.

## Shared schema

Every Style Profile must fill every field below. The fields form one complete creative-direction contract:

- `id`: Stable, machine-readable client slug.
- `client`: Client or brand display name.
- `one_line`: The design language reduced to one directive sentence.
- `medium`: The primary visual medium. This controls which kinds of imagery and composition are native to the profile.
- `image_sources`: Ranked preference order using only `AI-illustration`, `AI-realistic (Leonardo/API)`, `licensed-stock (Unsplash/Pexels free tier first)`, `client-product-photos→cutout`, and `engine-generated-vector-assets`. The engine should attempt the first valid source before moving down the list.
- `palette`: Named color roles for `primary`, `ink`, `ground`, and `accent`, plus any brand-specific roles. Supplied hexes remain provisional until onboarding confirmation; missing source hexes must not be invented.
- `typography`: Heading and body character, including weight, case, and intended feel. A typeface family must remain unassigned when the source does not name one.
- `layout_archetypes`: Three to six named composition patterns, each with a one-line “use when” rule.
- `composition_principles`: The design principles that should dominate composition and QA judgment for the brand.
- `effect_vocabulary`: The brand-approved manipulations selected from `gradient/fade`, `soft/long/inner shadow`, `shading`, `blur`, `color-grade/duotone`, `grain`, `cutout`, `color-block`, `text-panel-over-photo`, and `badges/pills`.
- `motif_and_asset_needs`: Recurring motifs plus an explicit list of assets the engine must generate or source. This field must state when no ready-made vector library exists and the engine has to create the assets.
- `copy_voice`: Tone and typical message structure.
- `hard_guardrails`: Non-negotiable visual, content, and sourcing rules enforced by QA.

---

## Profile 1: Simply Nikah

### `id`

`simply-nikah`

### `client`

Simply Nikah

### `one_line`

Warm, Shariah-compliant matrimonial communication expressed through faceless flat-vector scenes, protective Islamic motifs, soft pink space, and decisive deep-plum emphasis.

### `medium`

**Flat vector illustration.** Any depicted person must be faceless or a silhouette. Real photography of people is outside this profile.

### `image_sources`

1. `engine-generated-vector-assets` — primary source for the brand's recurring Islamic frames, symbols, devices, avatars, and modular scenes.
2. `AI-illustration` — secondary source for one-off flat-vector compositions, constrained to the same faceless, modest visual language.

`AI-realistic (Leonardo/API)`, `licensed-stock (Unsplash/Pexels free tier first)`, and `client-product-photos→cutout` are not approved sources for this profile.

### `palette`

| Role | Color |
|---|---|
| `primary` | Simply Pink `#FD62AD` **(approx — confirm at onboarding)** |
| `accent` | Soft Blush `#F9C6DE` **(approx — confirm at onboarding)** |
| `ink` | Deep Plum `#2B0A2E` **(approx — confirm at onboarding)** |
| `cta_fill` | Deep Plum `#2B0A2E` **(approx — confirm at onboarding)** |
| `secondary` | Muted Lilac `#9B7BA6` **(approx — confirm at onboarding)** |
| `ground` | Cloud White `#FAF7FB` **(approx — confirm at onboarding)** |

### `typography`

- **Heading character:** Bold, high-emphasis display treatment in Deep Plum. The principal headline may isolate one decisive word in uppercase inside a solid plum box, such as “PROTECTED” or “RIGHT INTENTION.” The highlighted word is the visual entry point.
- **Body character:** Regular or lighter-weight supporting text in Deep Plum, calm and highly legible, with enough breathing room to preserve the gentle tone.
- **Special use:** An elegant script character may appear for greetings such as Eid content. It is an accent, not the default heading or body style.
- **Wordmark:** The “simply nikāh” wordmark sits top-center.
- **Typeface status:** No font family is supplied; confirm the approved heading, body, and greeting-script families at onboarding.

### `layout_archetypes`

1. **Highlighted-Word Hero** — use when a single trust, intention, or protection message must land first; stack the headline and support line above a central vector hero, with one key word reversed out in a plum box.
2. **Phone-and-Hijabi Product Story** — use when showing the app experience; pair a phone mockup with a faceless illustrated hijabi while keeping the device and modest figure as one central focal group.
3. **Connected Match Cards** — use when explaining matching or compatibility; arrange faceless avatar cards as a balanced system joined by connector lines.
4. **Mihrab or Lattice Frame** — use when creating faith-led announcements and reflective content; place the message or hero inside a mihrab-arch or Islamic-lattice framing motif.
5. **Protection or Intention Symbol Hero** — use when addressing trust, safety, or sincerity themes; center a shield-and-crescent or hands-forming-heart symbol beneath a concise headline.
6. **Ayah and Translation Panel** — use when the content leads with a Quran ayah; pair the Arabic calligraphy panel with its translation and a gentle supporting CTA.

Across archetypes, the CTA may be a pill or rounded message box. A header or footer band is optional, not a fixed part of every composition.

### `composition_principles`

- **Hierarchy and emphasis:** The highlighted word, central symbol, or calligraphy panel must establish the first read immediately.
- **Contrast:** Deep Plum against Soft Blush, Simply Pink, or Cloud White supplies clear text and CTA separation without making the composition harsh.
- **Balance:** Central and near-symmetrical arrangements reinforce calm, care, and trust; connector-card layouts should remain visually balanced even when the cards differ.
- **Whitespace:** Generous soft-pink or cloud-white negative space protects the modest, gentle tone and prevents ornamental assets from competing with the message.
- **Pattern and repetition:** Lattice geometry, arch forms, cards, and connector lines create unity through controlled repetition.
- **Rhythm:** Alternate compact headline or CTA groups with broad quiet areas; do not distribute ornament evenly across the whole canvas.

### `effect_vocabulary`

- `gradient/fade` — soft pink, blush, or lilac transitions that preserve an airy ground.
- `soft/long/inner shadow` — use only the subtle long-shadow variant beneath vector elements; never make it heavy or theatrical.
- `blur` — restrained pink glow behind a hero symbol, device, or illustration.
- `color-block` — Deep Plum boxes for highlighted headline words.
- `badges/pills` — rounded CTAs and message containers.

### `motif_and_asset_needs`

**Motifs:** Islamic geometric lattice or mashrabiya, mihrab arches, lanterns, shields, crescents, hearts, hands-forming-heart symbols, faceless avatar cards, connector paths, and calligraphy panels.

**Asset needs:** The operator has no vector library for this brand. The engine must **create** a reusable, style-consistent vector set containing Islamic geometric lattice or mashrabiya patterns, mihrab arches, lanterns, phone mockups, faceless avatar and match-card variants, connector lines, shields, crescents, hearts, hands-forming-heart symbols, and calligraphy-panel frames. It must also be able to compose new flat-vector, faceless hero scenes from those parts rather than relying on people photography.

### `copy_voice`

Warm, respectful, gentle, and faith-led. A typical piece uses a concise values-led headline, a short support line, and a soft invitation rather than a hard sell. Faith content may lead with a Quran ayah in Arabic calligraphy followed by its translation, then a gentle CTA.

### `hard_guardrails`

- **Never use real photographs of people.**
- Every human figure must be faceless or a silhouette.
- Nothing immodest may be generated, sourced, or retained; modesty and haya are mandatory QA checks.
- Keep the “simply nikāh” wordmark top-center.
- Do not force a permanent header or footer band; the profile requires layout variety.
- Do not let glow, shadows, or geometric pattern fills overwhelm the faith-led message or the generous whitespace.

---

## Profile 2: Glo2Go Aesthetics

### `id`

`glo2go-aesthetics`

### `client`

Glo2Go Aesthetics

### `one_line`

Clean, medical-premium education built from credible real photography, restrained plum typography, generous white space, and polished information panels.

### `medium`

**Real photography.** Use licensed stock photography and Leonardo/API-generated realistic models or clinic scenes. Illustration is not part of this profile, and the owner must not appear.

### `image_sources`

1. `licensed-stock (Unsplash/Pexels free tier first)` — first choice for credible models, skin, treatment, and clinic-context photography.
2. `AI-realistic (Leonardo/API)` — use when the required model or clinic scene cannot be sourced suitably from stock.

`AI-illustration`, `client-product-photos→cutout`, and `engine-generated-vector-assets` are not primary imagery sources for this profile.

### `palette`

| Role | Color |
|---|---|
| `primary` | Deep Plum/Purple `#5A2A6B` **(approx — confirm at onboarding)** |
| `ink` | Deep Plum/Purple `#5A2A6B` **(approx — confirm at onboarding)** |
| `ground` | White `#FFFFFF` **(approx — confirm at onboarding)** |
| `accent` | Soft Lilac — source hex not supplied; confirm at onboarding |

### `typography`

- **Heading character:** Bold sans serif in Deep Plum/Purple, clean and direct rather than expressive. Educational labels such as “Myth vs Fact” should be immediately scannable.
- **Body character:** Lighter-weight sans serif with a calm, clinical-premium feel. Supporting copy should remain compact and readable over white or translucent panels.
- **Case:** Natural title or sentence case; avoid the all-caps, condensed meme treatment used by a retail profile.
- **Logo treatment:** “G2G Aesthetics” appears in a rounded plum pill badge at the top-right.
- **Typeface status:** No font family is supplied; confirm the approved heading and body families at onboarding.

### `layout_archetypes`

1. **Myth-vs-Fact Stacked Split** — use when directly correcting a misconception; stack two photos, give each a clear Myth or Fact label, and pair each image with its own restrained text panel.
2. **Single-Photo Education Hero** — use when communicating one key treatment or skin insight; combine one strong hero photo with a concise headline and a semi-transparent white text panel over the image where legibility requires it.
3. **Educational Carousel System** — use when a topic needs several steps or claims; keep a repeated slide grid, stable logo position, consistent plum hierarchy, and ample white space across the series.

### `composition_principles`

- **Hierarchy:** Headline, education label, explanation, and CTA should read in that order without decorative competition.
- **Whitespace:** White ground and open margins are load-bearing; they create the restrained, premium clinic character.
- **Contrast and legibility:** Plum type and semi-transparent white or plum panels must separate copy from photographic detail.
- **Balance:** Photography and information panels should share the frame without either side feeling crowded or visually underweighted.
- **Proximity:** Keep each Myth or Fact label physically close to the photo and explanation it qualifies.
- **Unity and rhythm:** Carousel slides repeat the badge, type scale, panel treatment, and spacing so the series reads as one clinical education system.

### `effect_vocabulary`

- `text-panel-over-photo` — semi-transparent white or plum panels used only where the photo would reduce copy legibility.
- `badges/pills` — the rounded top-right logo badge and compact Myth or Fact labels.
- `soft/long/inner shadow` — use only the soft-shadow variant for subtle panel or brand-badge separation; keep it barely perceptible.

### `motif_and_asset_needs`

**Motifs:** Rounded plum brand badge, clean Myth and Fact labels, translucent information panels, real skin or clinic imagery, and consistent plum educational typography.

**Asset needs:** The engine must **source** suitable licensed stock photography, checking Unsplash and Pexels free tiers first, and must **create** realistic model or clinic scenes through Leonardo/API when stock is insufficient. The operator has no prepared vector asset library for this profile, so the engine must also create reusable text-panel overlays and the rounded “G2G Aesthetics” plum pill badge, then apply the consistent plum heading, label, and body hierarchy. No owner portrait asset should be requested or generated.

### `copy_voice`

Educational, science-led, professional, and reassuring. A typical structure is a clear myth or question, a concise factual correction or explanation, then the CTA: “DM to book your free consultation.” Avoid sensational framing and keep claims medically credible.

### `hard_guardrails`

- The owner must never be shown; use licensed stock or generated realistic models and clinic scenes instead.
- Use real-photography treatment, not illustration.
- Imagery must remain tasteful and medically credible.
- Reject wild, sensational, or unsupported treatment claims.
- Keep the “G2G Aesthetics” rounded plum pill badge at the top-right.
- Preserve generous white space and restrained effects; decorative treatments must not make the clinic feel loud or gimmicky.

---

## Profile 3: Island Cart

### `id`

`island-cart`

### `client`

Island Cart

### `one_line`

High-energy Sri Lankan product advertising that combines actual product cutouts, hard orange-and-white geometry, huge witty type, and instantly scannable price and benefit cues.

### `medium`

**Product photography plus lifestyle photography and meme-style display type.** The actual product is the commercial focal point; lifestyle imagery provides the relatable setup or use context.

### `image_sources`

1. `client-product-photos→cutout` — required source for the actual product; remove the background and composite the cutout as the focal asset.
2. `licensed-stock (Unsplash/Pexels free tier first)` — supporting source for lifestyle situations used around the product or witty hook.
3. `engine-generated-vector-assets` — supporting source for the reusable diagonal blocks and price-tag shapes; never a substitute for the actual product photo.

`AI-illustration` and `AI-realistic (Leonardo/API)` are not approved imagery sources for this profile.

### `palette`

| Role | Color |
|---|---|
| `primary` | Bold Orange `#F26522` **(approx — confirm at onboarding)** |
| `accent` | Bold Orange `#F26522` **(approx — confirm at onboarding)**; no separate accent color was supplied |
| `ink` | Black `#000000` **(approx — confirm at onboarding)** |
| `ground` | White `#FFFFFF` **(approx — confirm at onboarding)** |

### `typography`

- **Heading character:** Huge, bold, condensed sans serif in caps. The hook behaves like a meme caption: fast, witty, and dominant, as in “SITTING ALL DAY IS SLOWLY TURNING EVERYONE INTO A CROISSANT” or “WAS MADE FOR PEOPLE WHO…”
- **Body character:** Bold, clean sans serif for the benefit line, product name, price, and CTA. It must remain legible at a glance and subordinate to the joke or hook.
- **Case:** All caps for the principal gag or hook; product details may use the clearest case for fast retail scanning.
- **Logo treatment:** The “IslandCart” logo sits top-left.
- **Typeface status:** No font family is supplied; confirm the approved condensed display and supporting sans-serif families at onboarding.

### `layout_archetypes`

1. **Diagonal Lifestyle Split** — use when a relatable lifestyle problem sets up the product; divide the canvas with a hard orange-and-white diagonal, pair the lifestyle photo with a huge-type gag, and keep the logo top-left.
2. **Cutout Product Offer** — use when creating a direct sales post; place the background-removed product on a clean ground with a drop shadow, price-tag pill, product name, and one clear benefit line.
3. **Dark-Photo Type Slam** — use when the lifestyle photo can carry high-impact contrast; place the bold hook over a dark photographic area and keep product, price, or CTA easy to find.

### `composition_principles`

- **Emphasis:** The gag or product must dominate immediately; secondary details cannot compete for the first read.
- **Contrast:** Orange, white, and black should create hard separation between hook, product, price, and CTA.
- **Movement:** Diagonal color blocks drive the eye through the composition and supply the brand's visual energy.
- **Asymmetrical balance:** Offset a large text mass with the lifestyle image or product cutout so the composition remains punchy without becoming unstable.
- **Hierarchy:** Hook first, product or benefit second, price third, CTA last.
- **Rhythm and proximity:** Keep product name, benefit, and price close enough to scan as one retail unit; use shifts in scale rather than extra decoration to create rhythm.

### `effect_vocabulary`

- `color-block` — hard diagonal orange-and-white fields with crisp edges.
- `cutout` — background removal for the actual client product photo.
- `soft/long/inner shadow` — use the soft-shadow variant as the product drop-shadow treatment that lifts the cutout from the ground.
- `badges/pills` — high-visibility price tags such as “Rs. 700/-”.

### `motif_and_asset_needs`

**Motifs:** Hard diagonal blocks, oversized condensed captions, isolated product cutouts, price-tag pills, benefit lines, and high-contrast lifestyle-photo fields.

**Asset needs:** The engine must accept the client's actual product photos, remove their backgrounds, produce clean cutouts, and composite them with a controlled drop shadow. The operator has no ready-made vector library for the campaign system, so the engine must **create** reusable diagonal color-block shapes and price-tag badge or pill assets. It must also source suitable lifestyle photos when required and establish an approved bold condensed display type treatment for the hooks.

### `copy_voice`

Witty, relatable, meme-like, and commercial. The typical structure is a large hook or everyday observation, a direct product benefit, the accurate product name and price, then a simple CTA. The joke earns attention; the product information closes the sale.

### `hard_guardrails`

- Product identity and price must be accurate in every creative.
- Use the client's actual product photography for the product focal asset; do not replace it with a different or invented product.
- Bold Orange is load-bearing and must remain a dominant brand signal.
- Keep the “IslandCart” logo top-left.
- Maintain high-contrast, fast-scanning hierarchy even when the headline is intentionally oversized.
- Keep the tone fun and commercial without letting the gag obscure the product, benefit, price, or CTA.

---

### What the engine must therefore support

- Multi-source imagery routing across licensed stock, realistic AI generation, client product photography, background removal, and cutout compositing.
- Engine-generated vector assets for clients without ready-made motif libraries, including reusable frames, symbols, geometric patterns, badges, and block shapes.
- A varied layout engine that can switch among central illustration heroes, device compositions, connected-card systems, framed faith motifs, photo-and-panel education, carousel systems, diagonal retail splits, product offers, and type-over-photo layouts.
- A rich, profile-controlled effect vocabulary covering gradients and fades, soft or long shadows, blur or glow, color blocks, cutouts, photo text panels, and badges or pills.
- Per-brand asset-source restrictions and QA guardrail enforcement, including modesty, owner-exclusion, medical credibility, accurate product and price data, mandatory logo placement, and load-bearing brand colors.
