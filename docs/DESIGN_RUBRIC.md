# Living Design-Critique Rubric — the self-improving design brain

> The point: the operator is not a designer, so the SYSTEM must accumulate design taste over time.
> Every creative is judged (by Claude + operator) → each accept/decline reason becomes a **rule** here →
> the art-director, templates, and brand-QA READ this file and apply it → creatives get better with every
> round. This is the human-curated seed of the M5 flywheel; later, preference signals auto-promote rules in.
>
> Format per rule: `ID · rule · why · applies-to · source`. When a render is judged, ADD or SHARPEN a rule.
> Never delete a rule silently — supersede it and note why (anti-context, like patterns.md).

_Seeded 2026-07-22 from the first correct-approach render (Glo2Go hero)._

## Composition
- **C1 · Never place the text panel over the photo's focal subject (face / product).** Put it over the
  calmest negative space. *Why:* covering the face reads as amateur; a designer works around the subject.
  *Applies:* all photo templates. *Source:* Glo2Go hero covered the model's face.
  → Mechanism: run the vision pass to locate the subject + return a text-safe region; else smart-crop.
  → **C1′ (sharpened, v2 2026-07-22):** region-anchoring ALONE is insufficient — the panel overflowed the
    small `bottom_right` region back onto the face. The panel MUST FIT WITHIN the safe region (constrain
    width/height to it), OR the photo is **smart-cropped/scaled so the subject is pushed opposite the panel**
    (reserve ~40% of the frame as clean space for text). Prefer crop-to-compose over shrinking text.
- **C2 · Balance mass.** Offset a large text block with the subject/negative space; avoid dead-center collisions.
  *Applies:* all. *Source:* general.

## Text & CTA
- **T1 · The CTA must STAND OUT from body copy** — a filled button/pill in a brand color with its own weight,
  never the same style as the description. *Why:* the CTA is the action; it can't blend into the paragraph.
  *Applies:* all. *Source:* operator (Glo2Go CTA blended with the body text).
- **T2 · Less text, larger impact.** Prefer a short headline + a tight sub; reduce body size/word count so the
  panel breathes. Don't overfill. *Applies:* all. *Source:* operator + house "8-words-max" taste.

## Brand assets
- **B1 · Use the actual brand LOGO image where available, not the brand name as text.** Fall back to a wordmark
  badge only when no logo file exists. *Applies:* all. *Source:* operator (Glo2Go used the word, not the mark).
- **B2 · Load the brand font.** No generic system-sans fallback in a finished creative. *Applies:* all.
  *Source:* Claude (Glo2Go rendered in a system font).

## Panel & effects
- **P1 · The text panel must blend with the poster, not sit on it as a pasted box** — a touch more opacity,
  soft feathered edge / subtle shadow, so it reads as part of the design. *Applies:* photo templates.
  *Source:* operator (Glo2Go panel looked flat/pasted).

## Medium & guardrails (from the style profiles)
- **G1 · Illustration-guardrail brands (Simply Nikah) never use real people / photos.** Faceless illustration
  only; enforced by QA. *Applies:* simply-nikah. *Source:* profile.
- **G2 · Product brands (Island Cart) use the client's real product cutout**, not stock substitutes.
  *Applies:* island-cart. *Source:* live-judged (stock returned wrong products).

## How this grows (the loop)
1. Render → Claude/operator judges → each reason becomes/【sharpens a rule above (with source + date).
2. The art-director prompt and the templates ingest this rubric so the next render already respects it.
3. As real approvals/rejections accumulate (M5 `PreferenceSignal`), rules get promoted/weighted automatically —
   client-scoped taste above the Mimik house floor encoded here.
