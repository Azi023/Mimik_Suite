"use client";

import type { FormEvent, JSX } from "react";
import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { saveClientBrand } from "@/app/clients/[id]/edit/actions";
import { ChipsInput } from "@/components/ChipsInput";
import {
  OnboardingField as Field,
  OnboardingSectionTitle as SectionTitle,
} from "@/components/OnboardingFields";
import type { ApiBrand, ApiClient } from "@/lib/api";
import { useUnsavedGuard } from "@/lib/hooks";

interface ClientBrandEditorProps {
  client: ApiClient;
  brand: ApiBrand | null;
}

interface EditableColor {
  name: string;
  hex: string;
  usage: string;
}

type ColorField = keyof EditableColor;

/** Prefilled editor for the client record and its in-place v1 brand brief. */
export function ClientBrandEditor({ client, brand }: ClientBrandEditorProps): JSX.Element {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [toneKeywords, setToneKeywords] = useState(brand?.tone_keywords ?? []);
  const [dos, setDos] = useState(brand?.dos ?? []);
  const [donts, setDonts] = useState(brand?.donts ?? []);
  const [palette, setPalette] = useState<EditableColor[]>(
    brand?.tokens.colors.map((color) => ({
      name: color.name,
      hex: color.hex,
      usage: color.usage ?? "",
    })) ?? [],
  );
  useUnsavedGuard(dirty);

  function updateChips(setter: (items: string[]) => void, items: string[]): void {
    setter(items);
    setDirty(true);
  }

  function updateColor(index: number, field: ColorField, value: string): void {
    setPalette((colors) =>
      colors.map((color, colorIndex) =>
        colorIndex === index ? { ...color, [field]: value } : color,
      ),
    );
    setDirty(true);
  }

  function addColor(): void {
    setPalette((colors) => [...colors, { name: "", hex: "#4b5563", usage: "" }]);
    setDirty(true);
  }

  function removeColor(index: number): void {
    setPalette((colors) => colors.filter((_, colorIndex) => colorIndex !== index));
    setDirty(true);
  }

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setMessage(null);
    const formData = new FormData(event.currentTarget);
    startTransition(async (): Promise<void> => {
      const result = await saveClientBrand(client.id, brand?.id ?? null, formData);
      if (result.ok) {
        setDirty(false);
        setMessage({ ok: true, text: "Client details and brand brief saved." });
        router.refresh();
      } else {
        setMessage({ ok: false, text: result.error ?? "Could not save the changes." });
      }
    });
  }

  return (
    <div className="wiz">
      <header className="wiz__head">
        <h1 className="wiz__title">Edit client and brand brief</h1>
        <p className="wiz__sub">
          Keep the client record and the creative direction current after onboarding.
        </p>
      </header>

      <form className="wiz__panel" onSubmit={submit} onChange={() => setDirty(true)}>
        <div className="wiz__body">
          <SectionTitle>Client details</SectionTitle>
          <div className="wiz-grid">
            <Field label="Client name" required>
              <input className="input" name="client_name" defaultValue={client.name} required />
            </Field>
            <Field label="Industry">
              <input className="input" name="industry" defaultValue={client.industry ?? ""} />
            </Field>
            <Field label="Contact email">
              <input
                className="input"
                name="contact_email"
                type="email"
                defaultValue={client.contact_email ?? ""}
              />
            </Field>
          </div>

          <SectionTitle>Brand brief</SectionTitle>
          {brand === null ? (
            <p className="wiz__hint">
              No brand brief is linked to this client yet. Client details can still be saved.
            </p>
          ) : (
            <>
              <div className="wiz-grid">
                <Field label="Niche">
                  <input className="input" name="niche" defaultValue={brand.niche ?? ""} />
                </Field>
                <Field label="Imagery style notes" hint="Describe lighting, composition, texture, or visual treatment.">
                  <textarea
                    className="input brief-textarea"
                    name="imagery_style"
                    rows={2}
                    defaultValue={brand.imagery_style ?? ""}
                  />
                </Field>
              </div>
              <Field label="Target audience">
                <textarea
                  className="input brief-textarea"
                  name="target_audience"
                  rows={2}
                  defaultValue={brand.target_audience ?? ""}
                />
              </Field>
              <Field label="Brand voice">
                <textarea
                  className="input brief-textarea"
                  name="brand_voice"
                  rows={2}
                  defaultValue={brand.brand_voice ?? ""}
                />
              </Field>
              <Field label="Tone keywords" hint="A few adjectives that describe the brand.">
                <ChipsInput
                  items={toneKeywords}
                  onChange={(items) => updateChips(setToneKeywords, items)}
                  placeholder="e.g. warm"
                />
                {toneKeywords.map((item) => (
                  <input key={item} type="hidden" name="tone_keywords" value={item} />
                ))}
              </Field>

              <SectionTitle>Guardrails</SectionTitle>
              <div className="wiz-grid">
                <Field label="Do's" hint="Required creative choices.">
                  <ChipsInput
                    items={dos}
                    onChange={(items) => updateChips(setDos, items)}
                    placeholder="e.g. Keep styling modest"
                    tone="do"
                  />
                  {dos.map((item) => (
                    <input key={item} type="hidden" name="dos" value={item} />
                  ))}
                </Field>
                <Field label="Don'ts" hint="Hard creative exclusions.">
                  <ChipsInput
                    items={donts}
                    onChange={(items) => updateChips(setDonts, items)}
                    placeholder="e.g. No stock gradients"
                    tone="dont"
                  />
                  {donts.map((item) => (
                    <input key={item} type="hidden" name="donts" value={item} />
                  ))}
                </Field>
              </div>

              <SectionTitle>Palette colors</SectionTitle>
              <p className="wiz__hint">The brand colours every creative composes from.</p>
              <div className="wiz-colors">
                {palette.map((color, index) => (
                  <div className="wiz-color-row" key={`${index}-${color.hex}`}>
                    <input
                      className="wiz-color__swatch"
                      name="color_hex"
                      type="color"
                      value={color.hex}
                      onChange={(event) => updateColor(index, "hex", event.target.value)}
                      aria-label={`Color ${index + 1}`}
                    />
                    <input
                      className="input"
                      name="color_name"
                      value={color.name}
                      onChange={(event) => updateColor(index, "name", event.target.value)}
                      placeholder="Name (e.g. Rose)"
                    />
                    <input
                      className="input"
                      name="color_usage"
                      value={color.usage}
                      onChange={(event) => updateColor(index, "usage", event.target.value)}
                      placeholder="Usage (e.g. CTA)"
                    />
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => removeColor(index)}
                      aria-label="Remove colour"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              <button type="button" className="btn-ghost" onClick={addColor}>
                Add colour
              </button>
            </>
          )}

          {message !== null && (
            <p
              className={`brief-savemsg brief-savemsg--${message.ok ? "ok" : "err"}`}
              role={message.ok ? "status" : "alert"}
            >
              {message.text}
            </p>
          )}
        </div>

        <div className="wiz-footer">
          <Link href="/" className="btn-ghost">
            Cancel
          </Link>
          <button type="submit" className="btn-primary" disabled={pending}>
            {pending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
