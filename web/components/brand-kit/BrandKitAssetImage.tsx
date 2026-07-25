"use client";

import Image from "next/image";
import { useState, type JSX } from "react";
import { assetRawUrl } from "@/lib/api";

interface BrandKitAssetImageProps {
  /** BrandAsset id — loaded through the same-origin `/api/assets/{id}/raw` proxy (CSP-safe). */
  assetId: string;
  alt: string;
  /** cover = moodboard tiles / social circles; contain = logo specimens. */
  fit: "cover" | "contain";
  /** Mono label shown in place of the image if the bytes fail to load — never a broken glyph. */
  fallbackLabel: string;
  className?: string;
}

/**
 * A brand-book asset image (spec §7 — self-contained by contract: no external hosts).
 * Renders inside a `position: relative` container; on load failure it degrades to a quiet
 * typeset fallback tile instead of the browser's broken-image icon (spec §5 hard rule).
 */
export function BrandKitAssetImage({
  assetId,
  alt,
  fit,
  fallbackLabel,
  className,
}: BrandKitAssetImageProps): JSX.Element {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return <span className="bk-img-fallback">{fallbackLabel}</span>;
  }

  return (
    <Image
      src={assetRawUrl(assetId)}
      alt={alt}
      fill
      unoptimized
      sizes="(max-width: 900px) 100vw, 600px"
      className={className}
      style={{ objectFit: fit }}
      onError={(): void => setFailed(true)}
    />
  );
}
