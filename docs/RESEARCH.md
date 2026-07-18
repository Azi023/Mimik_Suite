# Research Log (R&D that informed the build)

Distilled findings from the market + technical R&D. Kept because they justify non-obvious
decisions and will matter again as the product scales.

## Market / competitive
- **The moat is owning the whole loop, human-gated** (intake → brand brief → content → creative → internal review → client approval → delivery). "Better AI images" is not defensible; the loop + human gate is.
- **Pencil (trypencil.com)** is the closest full-loop product, but it's an *enterprise self-serve tool for paid ads* (SOC 2, ROAS prediction, book-a-demo pricing). Mimik's buyer is the SMB who wants *done-for-you*. Different buyer = the opening. Don't fight Pencil/Canva on tooling.
- **Human "unlimited design" incumbents** (Design Pickle ~$1,918/mo, Kimp ~$599–995) are bounded by human throughput + revision cycles. The undercut is real *if quality holds* — hence the human-gated quality bar, not full automation.
- **Chat-native approval** (WhatsApp) beats portal logins for SMB clients on the critical "yes" (studied Planable/Ziflow). Deferred to magic-link + in-portal for cost; WhatsApp Business API later.

## Technical (make-or-break)
- **Text-in-image fails across all 2025–26 models past ~200 chars**; legibility/logo-placement/exact-hex are unreliable. → **hybrid**: AI imagery + programmatic text/logo compositing (Playwright HTML/SVG→PNG). Confirmed working — the compositor renders pixel-sharp branded PNGs.
- **Brand consistency across a series** is a top failure mode → reference-conditioning + per-client brand-memory corpus + prompt-DNA (recipe) storage.
- **The taste/QA gap** ("90% there" is worse than useless in client work) → the internal review loop + brand-QA critic IS the product, not polish.
- **Image-gen cost reality**: static images via *paid* API are ~$0.03–0.09 each (cheap), but the build runs **no-paid**, so images come from **browser automation of PRO ChatGPT/AI-Studio** (fragile but free). Google AI Studio **free tier does NOT reliably include image gen** (needs billing) — so the free Gemini API key is used for **text/copy only**. Route by job; upgrade to paid tiers behind the adapter as revenue comes.
- **Multilingual/RTL (Arabic)**: Playwright HTML/CSS renders RTL natively; just need Arabic fonts + a per-brand language flag. Relevant to UAE/Maldives clients.
- **SSRF**: the brand-brief URL fetcher takes tenant-supplied URLs → guarded (`_assert_public_http_url`: resolves host, rejects loopback/RFC1918/link-local/metadata). Tested.

## Model / tooling notes
- **Image models by strength** (for when paid): Ideogram 3.0 (best text ~90%), Gemini/Nano-Banana (brand-consistent series + editing), Recraft V3 (vector), Flux (cheap backgrounds), GPT-Image (general).
- **Brand-brief extraction**: scrape via Playwright (reuse ProofKit collector) + Brandfetch/Firecrawl for structured colors/logo/fonts; vision pass on the free tier deferred (P2 seam).
- **Approval proofing** references: Ziflow/Filestage (annotation), Planable (WhatsApp preview→approve UX).
