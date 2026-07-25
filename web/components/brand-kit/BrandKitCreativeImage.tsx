"use client";

import Image from "next/image";
import { useState, type JSX } from "react";

interface BrandKitCreativeImageProps {
  creativeId: string;
  alt: string;
  fallbackLabel: string;
  className?: string;
}

/**
 * A rendered CreativeDoc preview loaded through the existing same-origin proxy. Browser
 * credentials remain httpOnly; a missing render becomes the book's typeset image fallback.
 */
export function BrandKitCreativeImage({
  creativeId,
  alt,
  fallbackLabel,
  className,
}: BrandKitCreativeImageProps): JSX.Element {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return <span className="bk-img-fallback">{fallbackLabel}</span>;
  }

  return (
    <Image
      src={`/api/creatives/${encodeURIComponent(creativeId)}/preview`}
      alt={alt}
      fill
      unoptimized
      sizes="(max-width: 900px) 100vw, 520px"
      className={className}
      style={{ objectFit: "cover" }}
      onError={(): void => setFailed(true)}
    />
  );
}
