"use client";

/**
 * Studio-only control bar for the brand book (spec §8): publish/unpublish the client
 * share link, download the full-book PDF, and export any chapter as a PNG.
 *
 * Publish state flips through the same-origin `/api/brand-kit/[id]/publish` route so the
 * user bearer stays in its httpOnly cookie; the PDF/PNG links point at the API's export
 * endpoints directly (spec §8 contract). Styled entirely in the book's own scoped CSS —
 * quiet mono chrome, like the font-pack button.
 */

import { useState, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { removeBrandAction } from "@/app/crud-actions";

/** One per-section PNG export link (registry order). */
export interface KitSectionLink {
  key: string;
  label: string;
  href: string;
}

interface BrandKitControlsProps {
  brandId: string;
  /** `BrandKit.published` at render time (false when the brand has no kit yet). */
  initialPublished: boolean;
  /** `{API}/brands/{id}/brand-book.pdf` */
  pdfHref: string;
  sectionLinks: KitSectionLink[];
}

interface ShareState {
  published: boolean;
  shareUrl: string | null;
}

/** Narrow the publish proxy's JSON to the share shape; null ⇒ unexpected payload. */
function parseShare(value: unknown): ShareState | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.published !== "boolean") {
    return null;
  }
  const shareUrl =
    typeof record.share_url === "string" && record.share_url !== "" ? record.share_url : null;
  return { published: record.published, shareUrl };
}

export function BrandKitControls({
  brandId,
  initialPublished,
  pdfHref,
  sectionLinks,
}: BrandKitControlsProps): JSX.Element {
  const router = useRouter();
  const [published, setPublished] = useState<boolean>(initialPublished);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  async function setPublishState(next: boolean): Promise<void> {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const response = await fetch(`/api/brand-kit/${encodeURIComponent(brandId)}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ publish: next }),
      });
      const data: unknown = await response.json().catch((): null => null);
      if (!response.ok) {
        setError(
          next
            ? "Could not publish — the studio API declined the request."
            : "Could not unpublish — the studio API declined the request.",
        );
        return;
      }
      const share = parseShare(data);
      if (share === null) {
        setError("The studio API returned an unexpected response.");
        return;
      }
      setPublished(share.published);
      setShareUrl(share.published ? share.shareUrl : null);
    } catch {
      setError("Could not reach the studio API.");
    } finally {
      setBusy(false);
    }
  }

  async function copyShareUrl(): Promise<void> {
    if (shareUrl === null) {
      return;
    }
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      window.setTimeout((): void => setCopied(false), 2000);
    } catch {
      setError("Copy failed — select the link text instead.");
    }
  }

  async function removeBrand(): Promise<void> {
    if (!window.confirm("Remove this brand? It will be hidden, not destroyed.")) return;
    setBusy(true);
    setError(null);
    const result = await removeBrandAction(brandId);
    setBusy(false);
    if (result.ok) {
      router.push("/clients");
      router.refresh();
    } else {
      setError(result.error ?? "Could not remove this brand.");
    }
  }

  return (
    <div className="bk-ctlbar">
      <div className="bk-ctl-status">
        <span className={published ? "bk-ctl-dot bk-ctl-dot--live" : "bk-ctl-dot"} />
        <span className="bk-ctl-k">{published ? "Published" : "Private"}</span>
        <span className="bk-ctl-note">
          {published
            ? "anyone with the share link can read this book"
            : "only the studio can see this book"}
        </span>
      </div>
      <div className="bk-ctl-actions">
        <Link className="bk-btn" href={`/brands/${encodeURIComponent(brandId)}/kit`}>
          Edit brand
        </Link>
        <button
          type="button"
          className={published ? "bk-btn" : "bk-btn bk-btn--primary"}
          disabled={busy}
          onClick={(): void => {
            void setPublishState(!published);
          }}
        >
          {busy ? "Working…" : published ? "Unpublish" : "Publish"}
        </button>
        {published && shareUrl === null && (
          <button
            type="button"
            className="bk-btn"
            disabled={busy}
            onClick={(): void => {
              void setPublishState(true);
            }}
          >
            Show share link
          </button>
        )}
        <a className="bk-btn" href={pdfHref} download>
          Download PDF
        </a>
        <details className="bk-ctl-menu">
          <summary className="bk-btn bk-ctl-summary">Export PNG</summary>
          <div className="bk-ctl-menu-list">
            {sectionLinks.map((link) => (
              <a key={link.key} href={link.href} download>
                {link.label}
              </a>
            ))}
          </div>
        </details>
        <button
          type="button"
          className="bk-btn bk-btn--danger"
          disabled={busy}
          onClick={(): void => {
            void removeBrand();
          }}
        >
          Remove brand
        </button>
      </div>
      {shareUrl !== null && (
        <div className="bk-ctl-share">
          <code>{shareUrl}</code>
          <button
            type="button"
            className="bk-btn"
            onClick={(): void => {
              void copyShareUrl();
            }}
          >
            {copied ? "Copied" : "Copy link"}
          </button>
        </div>
      )}
      {error !== null && <p className="bk-ctl-err">{error}</p>}
    </div>
  );
}
