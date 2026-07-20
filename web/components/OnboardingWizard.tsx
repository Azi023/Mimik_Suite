"use client";

import { useRef, useState, type JSX } from "react";
import { useRouter } from "next/navigation";
import { createOnboarding, type OnboardingPayload } from "@/app/onboarding/actions";
import type { ApiPillarPreset } from "@/lib/api";
import { useUnsavedGuard } from "@/lib/hooks";
import { ChipsInput } from "./ChipsInput";
import { CheckIcon } from "./icons";

interface OnboardingWizardProps {
  presets: ApiPillarPreset[];
}

interface ColorRow {
  name: string;
  hex: string;
  usage: string;
}
interface CustomPillar {
  name: string;
  description: string;
}
interface RefLink {
  url: string;
  source: string;
  note: string;
}

const STEPS = ["Brand", "Brand kit", "Content pillars", "Style reference", "Review"] as const;

const HANDLE_PLATFORMS = [
  { key: "instagram", label: "Instagram" },
  { key: "tiktok", label: "TikTok" },
  { key: "facebook", label: "Facebook" },
  { key: "youtube", label: "YouTube" },
  { key: "website", label: "Website" },
] as const;

const REF_SOURCES = [
  { value: "pinterest", label: "Pinterest" },
  { value: "existing_design", label: "Existing design" },
  { value: "social", label: "Social post" },
  { value: "website", label: "Website" },
  { value: "other", label: "Other" },
] as const;

export function OnboardingWizard({ presets }: OnboardingWizardProps): JSX.Element {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ briefId: string; warnings: string[] } | null>(null);

  // Step 1 — Brand + client.
  const [clientName, setClientName] = useState("");
  const [industry, setIndustry] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [brandName, setBrandName] = useState("");
  const [niche, setNiche] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [brandVoice, setBrandVoice] = useState("");
  const [imageryStyle, setImageryStyle] = useState("");
  const [toneKeywords, setToneKeywords] = useState<string[]>([]);
  const [dos, setDos] = useState<string[]>([]);
  const [donts, setDonts] = useState<string[]>([]);
  const [handles, setHandles] = useState<Record<string, string>>({});

  // Step 2 — Brand kit.
  const [colors, setColors] = useState<ColorRow[]>([{ name: "", hex: "#4b5563", usage: "" }]);
  const [headingFont, setHeadingFont] = useState("");
  const [bodyFont, setBodyFont] = useState("");
  const [logoNotes, setLogoNotes] = useState("");
  const [logoMinSize, setLogoMinSize] = useState("");

  // Step 3 — Content pillars.
  const [selectedPresets, setSelectedPresets] = useState<string[]>([]);
  const [customPillars, setCustomPillars] = useState<CustomPillar[]>([]);

  // Step 4 — Style reference.
  const [refLinks, setRefLinks] = useState<RefLink[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canAdvance = step > 0 || (clientName.trim() !== "" && brandName.trim() !== "");
  const isLast = step === STEPS.length - 1;

  // Resilience (FRONTEND_ROADMAP §2): the wizard only persists at the end, so guard against losing a
  // half-filled onboarding to an accidental tab-close. Dirty once the operator has started + not done.
  useUnsavedGuard(done === null && (step > 0 || clientName.trim() !== "" || brandName.trim() !== ""));

  function setHandle(key: string, value: string): void {
    setHandles((h) => ({ ...h, [key]: value }));
  }

  function togglePreset(key: string): void {
    setSelectedPresets((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));
  }

  function updateColor(i: number, patch: Partial<ColorRow>): void {
    setColors((cs) => cs.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }

  function addFiles(list: FileList | null): void {
    if (list === null) return;
    const picked = Array.from(list).filter((f) => f.type.startsWith("image/"));
    setFiles((prev) => [...prev, ...picked]);
  }

  function buildPayload(): OnboardingPayload {
    const cleanHandles: Record<string, string> = {};
    for (const [k, v] of Object.entries(handles)) {
      if (v.trim() !== "") cleanHandles[k] = v.trim();
    }
    return {
      client: { name: clientName, industry, contactEmail },
      brand: {
        name: brandName,
        slug: "",
        niche,
        targetAudience,
        brandVoice,
        imageryStyle,
        toneKeywords,
        dos,
        donts,
        handles: cleanHandles,
      },
      kit: { colors, headingFont, bodyFont, logoNotes, logoMinSize },
      pillars: { presets: selectedPresets, custom: customPillars },
      references: refLinks,
    };
  }

  async function onFinish(): Promise<void> {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("payload", JSON.stringify(buildPayload()));
    for (const f of files) form.append("refFiles", f);

    const res = await createOnboarding(form);
    if (res.ok && res.briefId !== undefined) {
      if (res.warnings !== undefined && res.warnings.length > 0) {
        setDone({ briefId: res.briefId, warnings: res.warnings });
        setBusy(false);
      } else {
        router.push(`/briefs/${res.briefId}`);
      }
    } else {
      setError(res.error ?? "Could not complete onboarding.");
      setBusy(false);
    }
  }

  if (done !== null) {
    return (
      <div className="wiz">
        <div className="wiz__panel wiz__panel--done">
          <div className="wiz-done__icon">
            <CheckIcon size={18} />
          </div>
          <h1 className="wiz__title">Client onboarded</h1>
          <p className="wiz__sub">
            The brand is set up and a brief has been drafted. A couple of extras didn&apos;t take:
          </p>
          <ul className="wiz-done__warnings">
            {done.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <button
            type="button"
            className="btn-primary"
            onClick={() => router.push(`/briefs/${done.briefId}`)}
          >
            Open the brief
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="wiz">
      <header className="wiz__head">
        <h1 className="wiz__title">Onboard a client</h1>
        <p className="wiz__sub">
          Set up the brand, its kit, content pillars, and the references the client shared. On
          finish, a brief is auto-drafted for sign-off.
        </p>
      </header>

      <ol className="wiz__steps" aria-label="Onboarding steps">
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={`wiz-step${i === step ? " wiz-step--active" : ""}${i < step ? " wiz-step--done" : ""}`}
          >
            <span className="wiz-step__n">{i < step ? <CheckIcon size={11} /> : i + 1}</span>
            <span className="wiz-step__label">{label}</span>
          </li>
        ))}
      </ol>

      <div className="wiz__panel">
        {step === 0 && (
          <StepBody>
            <SectionTitle>Client</SectionTitle>
            <div className="wiz-grid">
              <Field label="Client name" required>
                <input className="input" value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder="Glow Aesthetics" />
              </Field>
              <Field label="Industry">
                <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Skincare & aesthetics" />
              </Field>
              <Field label="Contact email">
                <input className="input" type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} placeholder="hello@client.com" />
              </Field>
            </div>

            <SectionTitle>Brand basics</SectionTitle>
            <div className="wiz-grid">
              <Field label="Brand name" required>
                <input className="input" value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder="Glow" />
              </Field>
              <Field label="Niche">
                <input className="input" value={niche} onChange={(e) => setNiche(e.target.value)} placeholder="Boutique aesthetics clinic" />
              </Field>
            </div>
            <Field label="Target audience">
              <textarea className="input brief-textarea" rows={2} value={targetAudience} onChange={(e) => setTargetAudience(e.target.value)} placeholder="Professional women 28-45 who research before they book." />
            </Field>
            <Field label="Brand voice">
              <textarea className="input brief-textarea" rows={2} value={brandVoice} onChange={(e) => setBrandVoice(e.target.value)} placeholder="Warm, precise, quietly confident." />
            </Field>
            <Field label="Imagery style">
              <textarea className="input brief-textarea" rows={2} value={imageryStyle} onChange={(e) => setImageryStyle(e.target.value)} placeholder="Natural-light photography on paper grounds; avoid stock gradients." />
            </Field>
            <Field label="Tone keywords" hint="A few adjectives that describe the brand.">
              <ChipsInput items={toneKeywords} onChange={setToneKeywords} placeholder="e.g. warm" />
            </Field>

            <SectionTitle>Guardrails</SectionTitle>
            <div className="wiz-grid">
              <Field label="Do's">
                <ChipsInput items={dos} onChange={setDos} placeholder="Add a do…" tone="do" />
              </Field>
              <Field label="Don'ts">
                <ChipsInput items={donts} onChange={setDonts} placeholder="Add a don't…" tone="dont" />
              </Field>
            </div>

            <SectionTitle>Social handles</SectionTitle>
            <div className="wiz-grid">
              {HANDLE_PLATFORMS.map((p) => (
                <Field key={p.key} label={p.label}>
                  <input
                    className="input"
                    value={handles[p.key] ?? ""}
                    onChange={(e) => setHandle(p.key, e.target.value)}
                    placeholder={p.key === "website" ? "https://…" : "@handle"}
                  />
                </Field>
              ))}
            </div>
          </StepBody>
        )}

        {step === 1 && (
          <StepBody>
            <SectionTitle>Palette</SectionTitle>
            <p className="wiz__hint">The brand colours every creative composes from.</p>
            <div className="wiz-colors">
              {colors.map((c, i) => (
                <div className="wiz-color-row" key={i}>
                  <input
                    type="color"
                    className="wiz-color__swatch"
                    value={c.hex}
                    onChange={(e) => updateColor(i, { hex: e.target.value })}
                    aria-label="Colour"
                  />
                  <input className="input" value={c.name} onChange={(e) => updateColor(i, { name: e.target.value })} placeholder="Name (e.g. Rose)" />
                  <input className="input" value={c.usage} onChange={(e) => updateColor(i, { usage: e.target.value })} placeholder="Usage (e.g. CTA)" />
                  <button type="button" className="btn-ghost" onClick={() => setColors((cs) => cs.filter((_, idx) => idx !== i))} aria-label="Remove colour">
                    ×
                  </button>
                </div>
              ))}
            </div>
            <button type="button" className="btn-ghost" onClick={() => setColors((cs) => [...cs, { name: "", hex: "#4b5563", usage: "" }])}>
              + Add colour
            </button>

            <SectionTitle>Typography</SectionTitle>
            <div className="wiz-grid">
              <Field label="Heading font">
                <input className="input" value={headingFont} onChange={(e) => setHeadingFont(e.target.value)} placeholder="Fraunces" />
              </Field>
              <Field label="Body font">
                <input className="input" value={bodyFont} onChange={(e) => setBodyFont(e.target.value)} placeholder="Inter" />
              </Field>
            </div>

            <SectionTitle>Logo</SectionTitle>
            <Field label="Logo notes" hint="Usable as-is, or needs a redesign — and why.">
              <textarea className="input brief-textarea" rows={2} value={logoNotes} onChange={(e) => setLogoNotes(e.target.value)} placeholder="Wordmark is clean and legible — usable as-is." />
            </Field>
            <Field label="Minimum size (px)">
              <input className="input wiz-narrow" type="number" min={0} value={logoMinSize} onChange={(e) => setLogoMinSize(e.target.value)} placeholder="24" />
            </Field>
            <p className="wiz__hint">The logo file itself is uploaded later from the brand&apos;s asset library.</p>
          </StepBody>
        )}

        {step === 2 && (
          <StepBody>
            <SectionTitle>Starter pillars</SectionTitle>
            <p className="wiz__hint">Pick the recurring content themes this brand will run.</p>
            {presets.length === 0 ? (
              <p className="wiz__hint">No presets available — add custom pillars below.</p>
            ) : (
              <div className="wiz-preset-grid">
                {presets.map((p) => {
                  const on = selectedPresets.includes(p.key);
                  return (
                    <button
                      type="button"
                      key={p.key}
                      className={`wiz-preset${on ? " wiz-preset--on" : ""}`}
                      aria-pressed={on}
                      onClick={() => togglePreset(p.key)}
                    >
                      <span className="wiz-preset__check">{on && <CheckIcon size={11} />}</span>
                      <span className="wiz-preset__name">{p.name}</span>
                      <span className="wiz-preset__desc">{p.description}</span>
                    </button>
                  );
                })}
              </div>
            )}

            <SectionTitle>Custom pillars</SectionTitle>
            {customPillars.map((cp, i) => (
              <div className="wiz-ref-row" key={i}>
                <input className="input" value={cp.name} onChange={(e) => setCustomPillars((ps) => ps.map((p, idx) => (idx === i ? { ...p, name: e.target.value } : p)))} placeholder="Pillar name" />
                <input className="input" value={cp.description} onChange={(e) => setCustomPillars((ps) => ps.map((p, idx) => (idx === i ? { ...p, description: e.target.value } : p)))} placeholder="Short description" />
                <button type="button" className="btn-ghost" onClick={() => setCustomPillars((ps) => ps.filter((_, idx) => idx !== i))} aria-label="Remove pillar">
                  ×
                </button>
              </div>
            ))}
            <button type="button" className="btn-ghost" onClick={() => setCustomPillars((ps) => [...ps, { name: "", description: "" }])}>
              + Add custom pillar
            </button>
          </StepBody>
        )}

        {step === 3 && (
          <StepBody>
            <SectionTitle>Reference links</SectionTitle>
            <p className="wiz__hint">
              Anything the client shared — Pinterest boards, their existing designs, social posts,
              websites they like — with an optional note.
            </p>
            {refLinks.map((r, i) => (
              <div className="wiz-ref-row wiz-ref-row--link" key={i}>
                <input className="input" value={r.url} onChange={(e) => setRefLinks((rs) => rs.map((x, idx) => (idx === i ? { ...x, url: e.target.value } : x)))} placeholder="https://pinterest.com/…" />
                <select className="input select" value={r.source} onChange={(e) => setRefLinks((rs) => rs.map((x, idx) => (idx === i ? { ...x, source: e.target.value } : x)))} aria-label="Reference type">
                  {REF_SOURCES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
                <input className="input" value={r.note} onChange={(e) => setRefLinks((rs) => rs.map((x, idx) => (idx === i ? { ...x, note: e.target.value } : x)))} placeholder="Note (optional)" />
                <button type="button" className="btn-ghost" onClick={() => setRefLinks((rs) => rs.filter((_, idx) => idx !== i))} aria-label="Remove reference">
                  ×
                </button>
              </div>
            ))}
            <button type="button" className="btn-ghost" onClick={() => setRefLinks((rs) => [...rs, { url: "", source: "pinterest", note: "" }])}>
              + Add link
            </button>

            <SectionTitle>Reference images</SectionTitle>
            <p className="wiz__hint">Or upload images the client sent. They&apos;re stored as brand references.</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => {
                addFiles(e.target.files);
                if (fileInputRef.current !== null) fileInputRef.current.value = "";
              }}
            />
            <button type="button" className="btn-ghost" onClick={() => fileInputRef.current?.click()}>
              + Upload images
            </button>
            {files.length > 0 && (
              <ul className="wiz-files">
                {files.map((f, i) => (
                  <li className="wiz-file" key={`${f.name}-${i}`}>
                    <span className="wiz-file__name">{f.name}</span>
                    <span className="wiz-file__size">{Math.round(f.size / 1024)} KB</span>
                    <button type="button" className="brief-chip__x" aria-label={`Remove ${f.name}`} onClick={() => setFiles((fs) => fs.filter((_, idx) => idx !== i))}>
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </StepBody>
        )}

        {step === 4 && (
          <StepBody>
            <SectionTitle>Review</SectionTitle>
            <ReviewGroup label="Client">
              {clientName || "—"}
              {industry !== "" ? ` · ${industry}` : ""}
            </ReviewGroup>
            <ReviewGroup label="Brand">
              {brandName || "—"}
              {niche !== "" ? ` · ${niche}` : ""}
            </ReviewGroup>
            <ReviewGroup label="Palette">
              {colors.filter((c) => c.hex.trim() !== "").length === 0 ? (
                "—"
              ) : (
                <span className="wiz-review__swatches">
                  {colors
                    .filter((c) => c.hex.trim() !== "")
                    .map((c, i) => (
                      <span key={i} className="wiz-review__swatch" style={{ background: c.hex }} title={c.name} />
                    ))}
                </span>
              )}
            </ReviewGroup>
            <ReviewGroup label="Typography">
              {headingFont || bodyFont ? `${headingFont || "—"} / ${bodyFont || "—"}` : "—"}
            </ReviewGroup>
            <ReviewGroup label="Pillars">
              {selectedPresets.length + customPillars.filter((c) => c.name.trim() !== "").length === 0
                ? "—"
                : `${selectedPresets.length} preset${selectedPresets.length === 1 ? "" : "s"}` +
                  (customPillars.filter((c) => c.name.trim() !== "").length > 0
                    ? ` · ${customPillars.filter((c) => c.name.trim() !== "").length} custom`
                    : "")}
            </ReviewGroup>
            <ReviewGroup label="References">
              {refLinks.filter((r) => r.url.trim() !== "").length + files.length === 0
                ? "—"
                : `${refLinks.filter((r) => r.url.trim() !== "").length} link(s) · ${files.length} image(s)`}
            </ReviewGroup>
            <p className="wiz__hint">On finish this creates the client, brand, pillars and references, then drafts a brief.</p>
            {error !== null && (
              <p className="brief-savemsg brief-savemsg--err" role="alert">
                {error}
              </p>
            )}
          </StepBody>
        )}

        <div className="wiz-footer">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0 || busy}
          >
            Back
          </button>
          {isLast ? (
            <button type="button" className="btn-primary" onClick={onFinish} disabled={busy}>
              {busy ? "Creating…" : "Finish & draft brief"}
            </button>
          ) : (
            <button
              type="button"
              className="btn-primary"
              onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
              disabled={!canAdvance}
              title={!canAdvance ? "Client name and brand name are required" : undefined}
            >
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StepBody({ children }: { children: React.ReactNode }): JSX.Element {
  return <div className="wiz__body">{children}</div>;
}

function SectionTitle({ children }: { children: React.ReactNode }): JSX.Element {
  return <h2 className="wiz-section-title">{children}</h2>;
}

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <label className="wiz-field">
      <span className="wiz-field__label">
        {label}
        {required === true && <span className="wiz-field__req"> *</span>}
      </span>
      {hint !== undefined && <span className="wiz-field__hint">{hint}</span>}
      {children}
    </label>
  );
}

function ReviewGroup({ label, children }: { label: string; children: React.ReactNode }): JSX.Element {
  return (
    <div className="wiz-review__row">
      <span className="wiz-review__key">{label}</span>
      <span className="wiz-review__val">{children}</span>
    </div>
  );
}
