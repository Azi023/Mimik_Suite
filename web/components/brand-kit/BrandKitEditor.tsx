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

  return (
    <BrandBookCanvas
      brand={brand}
      clientName={clientName}
      view="studio"
      controls={controls}
      onSaveTextField={saveTextField}
    />
  );
}
