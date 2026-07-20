"use client";

import { useState, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  reviseBriefAction,
  saveBrief,
  signOffBrief,
  type BriefActionResult,
} from "@/app/briefs/actions";
import type { ApiBrief, ApiBriefSections } from "@/lib/api";
import { CheckIcon, LockIcon } from "./icons";

interface BriefEditorViewProps {
  brief: ApiBrief;
  clientName: string | null;
}

/** A signed-off brief is immutable. Everything else (draft / in-review) is editable. */
function isLocked(brief: ApiBrief): boolean {
  return brief.status === "frozen" || brief.status === "signed_off";
}

/** Trim, and collapse an empty string to null — matches the contract's `str | None` sections. */
function trimToNull(value: string): string | null {
  const t = value.trim();
  return t === "" ? null : t;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function BriefEditorView({ brief, clientName }: BriefEditorViewProps): JSX.Element {
  const router = useRouter();
  const locked = isLocked(brief);
  const sections = brief.sections;

  // Editable text/list sections. Brand tokens (§3-4) and references (§8) are shown read-only —
  // they're owned by the brand-kit editor and the style-reference step, not this screen — and are
  // carried through unchanged on save.
  const [snapshot, setSnapshot] = useState(sections.snapshot ?? "");
  const [logoNotes, setLogoNotes] = useState(sections.logo_notes ?? "");
  const [voiceTone, setVoiceTone] = useState(sections.voice_tone ?? "");
  const [imageryStyle, setImageryStyle] = useState(sections.imagery_style ?? "");
  const [dos, setDos] = useState<string[]>(sections.guardrails_dos);
  const [donts, setDonts] = useState<string[]>(sections.guardrails_donts);
  const [formats, setFormats] = useState<string[]>(sections.deliverable_formats);

  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BriefActionResult | null>(null);
  const [signOpen, setSignOpen] = useState(false);

  // Any edit marks the form dirty and clears the last save banner.
  function edited<T>(setter: (v: T) => void): (v: T) => void {
    return (v: T) => {
      setter(v);
      setDirty(true);
      setResult(null);
    };
  }

  function collectSections(): ApiBriefSections {
    return {
      snapshot: trimToNull(snapshot),
      logo_notes: trimToNull(logoNotes),
      tokens: sections.tokens,
      voice_tone: trimToNull(voiceTone),
      imagery_style: trimToNull(imageryStyle),
      guardrails_dos: dos,
      guardrails_donts: donts,
      references: sections.references,
      deliverable_formats: formats,
    };
  }

  async function onSave(): Promise<void> {
    setBusy(true);
    const res = await saveBrief(brief.id, collectSections());
    setResult(res);
    if (res.ok) setDirty(false);
    setBusy(false);
  }

  async function onSignOff(signedOffBy: string): Promise<void> {
    setBusy(true);
    const res = await signOffBrief(brief.id, signedOffBy);
    if (res.ok) {
      // Re-fetch the server component so the editor flips to its locked, read-only state.
      setSignOpen(false);
      router.refresh();
    } else {
      setResult(res);
      setBusy(false);
    }
  }

  async function onRevise(): Promise<void> {
    setBusy(true);
    const res = await reviseBriefAction(brief.id);
    if (res.ok && res.newBriefId !== undefined) {
      router.push(`/briefs/${res.newBriefId}`);
    } else {
      setResult({ ok: false, error: res.error });
      setBusy(false);
    }
  }

  return (
    <div className="brief-editor">
      <header className="brief-editor__bar">
        <div className="brief-editor__ident">
          <Link href="/briefs" className="brief-editor__back">
            ← Briefs
          </Link>
          <div>
            <h1 className="brief-editor__title">{clientName ?? "Brand brief"}</h1>
            <div className="brief-editor__submeta">
              <span>Version {brief.version}</span>
              <span aria-hidden="true">·</span>
              {locked ? (
                <span className="brief-pill brief-pill--locked">
                  <LockIcon size={11} /> Signed off
                </span>
              ) : (
                <span className="brief-pill brief-pill--open">Draft</span>
              )}
            </div>
          </div>
        </div>

        <div className="brief-editor__actions">
          {locked ? (
            <button type="button" className="btn-primary" onClick={onRevise} disabled={busy}>
              {busy ? "Creating…" : "Revise (new version)"}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn-ghost"
                onClick={onSave}
                disabled={busy || !dirty}
              >
                {busy ? "Saving…" : dirty ? "Save changes" : "Saved"}
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => setSignOpen(true)}
                disabled={busy || dirty}
                title={dirty ? "Save your changes before signing off" : undefined}
              >
                Sign off
              </button>
            </>
          )}
        </div>
      </header>

      {locked && (
        <div className="brief-banner" role="status">
          <LockIcon />
          <span>
            Signed off{brief.signed_off_by !== null ? ` by ${brief.signed_off_by}` : ""}
            {brief.frozen_at !== null ? ` on ${formatDate(brief.frozen_at)}` : ""}. This brief is
            locked — revise it to create the next version.
          </span>
        </div>
      )}

      {result !== null && (
        <p
          className={result.ok ? "brief-savemsg brief-savemsg--ok" : "brief-savemsg brief-savemsg--err"}
          role={result.ok ? "status" : "alert"}
        >
          {result.ok ? "Changes saved." : result.error}
        </p>
      )}

      <div className="brief-sections">
        <Section n={1} title="Brand snapshot" hint="Who they are, positioning, audience, competitors.">
          <TextArea
            value={snapshot}
            onChange={edited(setSnapshot)}
            disabled={locked}
            placeholder="A one-paragraph read on the brand…"
            rows={4}
          />
        </Section>

        <Section n={2} title="Logo notes" hint="Usable as-is, or needs a redesign — and why.">
          <TextArea
            value={logoNotes}
            onChange={edited(setLogoNotes)}
            disabled={locked}
            placeholder="Logo assessment and usage notes…"
            rows={3}
          />
        </Section>

        <Section
          n={3}
          title="Brand tokens"
          hint="Palette and typography — managed in the brand kit; shown here for reference."
        >
          <TokensPreview tokens={sections.tokens} />
          <Link href={`/brands/${brief.brand_id}/kit`} className="brief-kit-link">
            Edit in brand kit →
          </Link>
        </Section>

        <Section n={5} title="Voice & tone" hint="Adjectives and short examples of how the brand speaks.">
          <TextArea
            value={voiceTone}
            onChange={edited(setVoiceTone)}
            disabled={locked}
            placeholder="e.g. Warm, precise, a little playful…"
            rows={3}
          />
        </Section>

        <Section n={6} title="Imagery style" hint="Photo vs illustration, mood, and what to avoid.">
          <TextArea
            value={imageryStyle}
            onChange={edited(setImageryStyle)}
            disabled={locked}
            placeholder="Bright product photography on paper grounds; avoid stock gradients…"
            rows={3}
          />
        </Section>

        <Section n={7} title="Guardrails" hint="The hard do's and don'ts every creative must respect.">
          <div className="brief-guardrails">
            <ListEditor
              label="Do"
              tone="do"
              items={dos}
              onChange={edited(setDos)}
              disabled={locked}
              placeholder="Add a do…"
            />
            <ListEditor
              label="Don't"
              tone="dont"
              items={donts}
              onChange={edited(setDonts)}
              disabled={locked}
              placeholder="Add a don't…"
            />
          </div>
        </Section>

        <Section n={8} title="References" hint="The vetted mood board — added in the style-reference step.">
          <ReferencesPreview references={sections.references} />
        </Section>

        <Section n={9} title="Deliverable formats" hint="The formats this brand ships, per channel.">
          <ListEditor
            label="Formats"
            tone="neutral"
            items={formats}
            onChange={edited(setFormats)}
            disabled={locked}
            placeholder="e.g. ig_post"
          />
        </Section>
      </div>

      {signOpen && (
        <SignOffDialog
          brand={clientName ?? "this brand"}
          busy={busy}
          onCancel={() => setSignOpen(false)}
          onConfirm={onSignOff}
        />
      )}
    </div>
  );
}

function Section({
  n,
  title,
  hint,
  children,
}: {
  n: number;
  title: string;
  hint: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section className="brief-section">
      <div className="brief-section__head">
        <span className="brief-section__n">{n}</span>
        <div>
          <h2 className="brief-section__title">{title}</h2>
          <p className="brief-section__hint">{hint}</p>
        </div>
      </div>
      <div className="brief-section__body">{children}</div>
    </section>
  );
}

function TextArea({
  value,
  onChange,
  disabled,
  placeholder,
  rows,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  placeholder: string;
  rows: number;
}): JSX.Element {
  if (disabled) {
    return (
      <p className={value.trim() === "" ? "brief-readonly brief-readonly--empty" : "brief-readonly"}>
        {value.trim() === "" ? "Not filled in." : value}
      </p>
    );
  }
  return (
    <textarea
      className="input brief-textarea"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
    />
  );
}

function ListEditor({
  label,
  tone,
  items,
  onChange,
  disabled,
  placeholder,
}: {
  label: string;
  tone: "do" | "dont" | "neutral";
  items: string[];
  onChange: (items: string[]) => void;
  disabled: boolean;
  placeholder: string;
}): JSX.Element {
  const [draft, setDraft] = useState("");

  function add(): void {
    const v = draft.trim();
    if (v === "") return;
    if (!items.includes(v)) onChange([...items, v]);
    setDraft("");
  }

  function remove(item: string): void {
    onChange(items.filter((i) => i !== item));
  }

  return (
    <div className="brief-list">
      <span className={`brief-list__label brief-list__label--${tone}`}>{label}</span>
      {items.length === 0 && disabled ? (
        <span className="brief-readonly brief-readonly--empty">None.</span>
      ) : (
        <ul className="brief-chips">
          {items.map((item) => (
            <li key={item} className={`brief-chip brief-chip--${tone}`}>
              <span>{item}</span>
              {!disabled && (
                <button
                  type="button"
                  className="brief-chip__x"
                  aria-label={`Remove ${item}`}
                  onClick={() => remove(item)}
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {!disabled && (
        <div className="brief-list__add">
          <input
            className="input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add();
              }
            }}
          />
          <button type="button" className="btn-ghost" onClick={add} disabled={draft.trim() === ""}>
            Add
          </button>
        </div>
      )}
    </div>
  );
}

function TokensPreview({ tokens }: { tokens: ApiBrief["sections"]["tokens"] }): JSX.Element {
  const { colors, typography } = tokens;
  const hasColors = colors.length > 0;
  const hasType = typography.heading_font !== null || typography.body_font !== null;
  if (!hasColors && !hasType) {
    return <span className="brief-readonly brief-readonly--empty">No brand tokens drafted yet.</span>;
  }
  return (
    <div className="brief-tokens">
      {hasColors && (
        <div className="brief-swatches">
          {colors.map((c) => (
            <div key={`${c.name}-${c.hex}`} className="brief-swatch">
              <span className="brief-swatch__chip" style={{ background: c.hex }} aria-hidden="true" />
              <span className="brief-swatch__name">{c.name}</span>
              <span className="brief-swatch__hex">{c.hex}</span>
            </div>
          ))}
        </div>
      )}
      {hasType && (
        <div className="brief-type">
          {typography.heading_font !== null && (
            <span>
              <span className="brief-type__k">Heading</span> {typography.heading_font}
            </span>
          )}
          {typography.body_font !== null && (
            <span>
              <span className="brief-type__k">Body</span> {typography.body_font}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ReferencesPreview({
  references,
}: {
  references: ApiBrief["sections"]["references"];
}): JSX.Element {
  if (references.length === 0) {
    return (
      <span className="brief-readonly brief-readonly--empty">
        No references yet — added in the onboarding style-reference step.
      </span>
    );
  }
  return (
    <ul className="brief-refs">
      {references.map((ref) => (
        <li key={ref.url} className="brief-ref">
          <a href={ref.url} target="_blank" rel="noopener noreferrer" className="brief-ref__url">
            {ref.source ?? ref.url}
          </a>
          {ref.fit_score !== null && (
            <span className="brief-ref__fit">fit {Math.round(ref.fit_score * 100)}%</span>
          )}
          {ref.note !== null && <span className="brief-ref__note">{ref.note}</span>}
        </li>
      ))}
    </ul>
  );
}

function SignOffDialog({
  brand,
  busy,
  onCancel,
  onConfirm,
}: {
  brand: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (signedOffBy: string) => void;
}): JSX.Element {
  const [name, setName] = useState("");
  return (
    <div className="brief-modal" role="dialog" aria-modal="true" aria-labelledby="signoff-title">
      <div className="brief-modal__panel">
        <h2 id="signoff-title" className="brief-modal__title">
          Sign off the brief
        </h2>
        <p className="brief-modal__body">
          Signing off freezes this brief for <strong>{brand}</strong>. It becomes read-only — any
          later change starts a new version. This is the scope-lock.
        </p>
        <label className="brief-modal__label" htmlFor="signoff-by">
          Signed off by
        </label>
        <input
          id="signoff-by"
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name or email"
          autoFocus
        />
        <div className="brief-modal__actions">
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => onConfirm(name)}
            disabled={busy || name.trim() === ""}
          >
            <CheckIcon size={12} /> {busy ? "Signing off…" : "Sign off & freeze"}
          </button>
        </div>
      </div>
    </div>
  );
}
