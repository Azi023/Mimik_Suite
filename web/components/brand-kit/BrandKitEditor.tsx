"use client";

import { useState, type JSX, type ReactNode } from "react";
import type { ApiBrand, UpdateBrandKitBody } from "@/lib/api";
import { BrandBookCanvas } from "./BrandBookCanvas";
import type { BrandKitTextTarget } from "./shared";

interface BrandKitEditorProps {
  brand: ApiBrand;
  clientName: string;
  controls?: ReactNode;
}

function kitPatch(target: BrandKitTextTarget, value: string | null): UpdateBrandKitBody {
  if (target.section === "discovery") {
    return { kit: { discovery: { [target.field]: value } } };
  }
  return { kit: { direction: { [target.field]: value } } };
}

export function BrandKitEditor({
  brand: initialBrand,
  clientName,
  controls = null,
}: BrandKitEditorProps): JSX.Element {
  const [brand, setBrand] = useState(initialBrand);
  const [overwrite, setOverwrite] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generateNotice, setGenerateNotice] = useState<string | null>(null);

  async function saveTextField(target: BrandKitTextTarget, value: string | null): Promise<void> {
    const response = await fetch(`/api/brand-kit/${encodeURIComponent(brand.id)}`, {
      method: "PATCH",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(kitPatch(target, value)),
    });
    if (!response.ok) {
      throw new Error("Brand-kit field unchanged");
    }
    setBrand((await response.json()) as ApiBrand);
  }

  async function generateKit(): Promise<void> {
    if (
      overwrite &&
      !window.confirm(
        "Replace all generated Brand Kit narrative, including operator-authored fields?",
      )
    ) {
      return;
    }
    setGenerating(true);
    setGenerateError(null);
    setGenerateNotice(null);
    try {
      const response = await fetch(
        `/api/brand-kit/${encodeURIComponent(brand.id)}/generate`,
        {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ overwrite }),
        },
      );
      const data: unknown = await response.json().catch((): null => null);
      if (!response.ok) {
        const message =
          typeof data === "object" &&
          data !== null &&
          !Array.isArray(data) &&
          typeof (data as Record<string, unknown>).error === "string"
            ? String((data as Record<string, unknown>).error)
            : "Brand kit generation failed. Try again.";
        setGenerateError(message);
        return;
      }
      setBrand(data as ApiBrand);
      setGenerateNotice(
        overwrite
          ? "Brand kit regenerated. Existing narrative was replaced."
          : "Brand kit generated. Existing narrative was preserved.",
      );
    } catch {
      setGenerateError("Could not reach the studio API. Try again.");
    } finally {
      setGenerating(false);
    }
  }

  const generationControl = (
    <section className="bk-generate" aria-labelledby="bk-generate-title">
      <div className="bk-generate__copy">
        <strong id="bk-generate-title">Generate brand kit</strong>
        <span>
          Draft discovery and direction from this brand record. By default, only empty fields
          are filled.
        </span>
      </div>
      <label className="bk-generate__overwrite">
        <input
          type="checkbox"
          checked={overwrite}
          disabled={generating}
          onChange={(event): void => setOverwrite(event.target.checked)}
        />
        Replace existing narrative
      </label>
      <button
        type="button"
        className="bk-btn bk-btn--primary"
        disabled={generating}
        onClick={(): void => {
          void generateKit();
        }}
      >
        {generating ? "Generating…" : overwrite ? "Regenerate all fields" : "Generate brand kit"}
      </button>
      {generateNotice !== null && (
        <p className="bk-generate__message" role="status">
          {generateNotice}
        </p>
      )}
      {generateError !== null && (
        <p className="bk-generate__message bk-generate__message--error" role="alert">
          {generateError}
        </p>
      )}
    </section>
  );

  return (
    <BrandBookCanvas
      brand={brand}
      clientName={clientName}
      view="studio"
      controls={
        <>
          {generationControl}
          {controls}
        </>
      }
      onSaveTextField={saveTextField}
    />
  );
}
