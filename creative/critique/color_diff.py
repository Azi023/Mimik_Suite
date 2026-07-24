"""A1 — Brand-token-diff (OBJECTIVE, no network, no vision).

Extracts the rendered PNG's dominant colors via Lab-space k-means (alpha-weighted),
diffs each dominant cluster against the brand palette with ΔE2000, and scores 1-5 on the
DESIGN_CRITIC_SPEC.md §2 A1 anchors. Fully deterministic: same pixels + same palette →
same score. Zero vision cost, zero calibration risk.

Reuses the pure-python PNG decoder already in the repo (`creative.export.psd._decode_png_rgba`,
the same non-interlaced 8-bit RGB/RGBA decoder the compositor emits) so the critic reads the
exact bytes the render produces — no Pillow dependency (Pillow is not installed).

Illustration-region masking (spec step 3): an AI-illustration hero legitimately carries
non-token colors and is exempt by mask. Slice-1 fixtures are pure engine-vector (no
illustration region), so `exempt_mask` defaults to None; the seam is here for Slice 4.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

# Reuse, don't rebuild: the repo's non-interlaced 8-bit PNG decoder (RGBA out). Import-only —
# this module is never modified here.
from creative.export.psd import _decode_png_rgba

from .report import AxisScore

_MIN_CLUSTER_COVERAGE = 0.03  # clusters below 3% coverage are ignored (spec step 2)
_OFF_BRAND_DE = 10.0  # ΔE2000 > 10 to every token = off-palette (spec step 3)
_MAX_SAMPLES = 20000  # downsample cap for k-means speed (deterministic w/ fixed seed)
_KMEANS_ITERS = 12
_SEED = 1_729


# --------------------------------------------------------------------------------------------
# sRGB -> CIE Lab (D65). Vectorised over (..., 3) float arrays in 0..255.
# --------------------------------------------------------------------------------------------
def _srgb_to_lab(rgb: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    c = rgb / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    # sRGB D65 -> XYZ
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    # Normalise by D65 white point
    x /= 0.95047
    z /= 1.08883

    def f(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        delta = 6.0 / 29.0
        return np.where(t > delta**3, np.cbrt(t), t / (3 * delta**2) + 4.0 / 29.0)

    fx, fy, fz = f(x), f(y), f(z)
    lab_l = 116 * fy - 16
    lab_a = 500 * (fx - fy)
    lab_b = 200 * (fy - fz)
    return np.stack([lab_l, lab_a, lab_b], axis=-1)


def _hex_to_lab(hex_color: str) -> npt.NDArray[np.float64]:
    raw = hex_color.lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    rgb = np.array([int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)], dtype=np.float64)
    return _srgb_to_lab(rgb)


# --------------------------------------------------------------------------------------------
# ΔE2000. Broadcast form: lab_a (..., 3) vs lab_b (..., 3) -> (...) after broadcasting.
# --------------------------------------------------------------------------------------------
def _delta_e_2000(
    lab1: npt.NDArray[np.float64], lab2: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]

    avg_lp = (l1 + l2) / 2.0
    c1 = np.hypot(a1, b1)
    c2 = np.hypot(a2, b2)
    avg_c = (c1 + c2) / 2.0

    g = 0.5 * (1 - np.sqrt(avg_c**7 / (avg_c**7 + 25.0**7)))
    a1p = a1 * (1 + g)
    a2p = a2 * (1 + g)
    c1p = np.hypot(a1p, b1)
    c2p = np.hypot(a2p, b2)
    avg_cp = (c1p + c2p) / 2.0

    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360

    dlp = l2 - l1
    dcp = c2p - c1p

    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, dhp)
    dhp = np.where(dhp < -180, dhp + 360, dhp)
    # If either chroma is ~0, hue difference is undefined -> contributes 0.
    zero_c = (c1p * c2p) == 0
    dHp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp) / 2.0)
    dHp = np.where(zero_c, 0.0, dHp)

    h_sum = h1p + h2p
    avg_hp = np.where(
        zero_c,
        h_sum,
        np.where(
            np.abs(h1p - h2p) <= 180,
            h_sum / 2.0,
            np.where(h_sum < 360, (h_sum + 360) / 2.0, (h_sum - 360) / 2.0),
        ),
    )

    t = (
        1
        - 0.17 * np.cos(np.radians(avg_hp - 30))
        + 0.24 * np.cos(np.radians(2 * avg_hp))
        + 0.32 * np.cos(np.radians(3 * avg_hp + 6))
        - 0.20 * np.cos(np.radians(4 * avg_hp - 63))
    )
    sl = 1 + (0.015 * (avg_lp - 50) ** 2) / np.sqrt(20 + (avg_lp - 50) ** 2)
    sc = 1 + 0.045 * avg_cp
    sh = 1 + 0.015 * avg_cp * t
    delta_theta = 30 * np.exp(-(((avg_hp - 275) / 25) ** 2))
    rc = 2 * np.sqrt(avg_cp**7 / (avg_cp**7 + 25.0**7))
    rt = -rc * np.sin(np.radians(2 * delta_theta))

    return np.sqrt(
        (dlp / sl) ** 2
        + (dcp / sc) ** 2
        + (dHp / sh) ** 2
        + rt * (dcp / sc) * (dHp / sh)
    )


# --------------------------------------------------------------------------------------------
# k-means in Lab space (weighted by alpha coverage).
# --------------------------------------------------------------------------------------------
def _kmeans(
    points: npt.NDArray[np.float64], weights: npt.NDArray[np.float64], k: int
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    rng = np.random.default_rng(_SEED)
    n = points.shape[0]
    k = min(k, n)
    # k-means++ style seeding kept simple: weighted random initial centers.
    probs = weights / weights.sum()
    init_idx = rng.choice(n, size=k, replace=False, p=probs)
    centers = points[init_idx].copy()

    labels = np.zeros(n, dtype=np.int64)
    for _ in range(_KMEANS_ITERS):
        # (n, k) squared euclidean in Lab
        dists = np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        new_labels = np.argmin(dists, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for ci in range(k):
            mask = labels == ci
            w = weights[mask]
            if w.sum() > 0:
                centers[ci] = np.average(points[mask], axis=0, weights=w)

    coverage = np.array(
        [weights[labels == ci].sum() for ci in range(k)], dtype=np.float64
    )
    coverage /= coverage.sum()
    return centers, coverage


def dominant_colors(
    png_bytes: bytes,
    *,
    k: int = 8,
    exempt_mask: npt.NDArray[np.bool_] | None = None,
) -> list[tuple[npt.NDArray[np.float64], str, float]]:
    """Top-`k` Lab clusters of the PNG (alpha-weighted). Returns [(lab, hex, coverage), ...]
    sorted by coverage desc. `exempt_mask` (H, W) True = illustration region, excluded."""
    pixels = _decode_png_rgba(png_bytes).astype(np.float64)  # (H, W, 4)
    h, w = pixels.shape[:2]
    rgb = pixels[:, :, :3].reshape(-1, 3)
    alpha = pixels[:, :, 3].reshape(-1) / 255.0
    if exempt_mask is not None:
        keep = ~exempt_mask.reshape(-1)
        rgb, alpha = rgb[keep], alpha[keep]

    visible = alpha > 0.05
    rgb, alpha = rgb[visible], alpha[visible]
    if rgb.shape[0] == 0:
        return []

    if rgb.shape[0] > _MAX_SAMPLES:
        rng = np.random.default_rng(_SEED)
        idx = rng.choice(rgb.shape[0], size=_MAX_SAMPLES, replace=False)
        rgb, alpha = rgb[idx], alpha[idx]

    lab = _srgb_to_lab(rgb)
    centers, coverage = _kmeans(lab, alpha, k)
    out = [
        (centers[i], _lab_to_hex(centers[i]), float(coverage[i])) for i in range(len(centers))
    ]
    out.sort(key=lambda t: t[2], reverse=True)
    return out


def _lab_to_hex(lab: npt.NDArray[np.float64]) -> str:
    """Approximate Lab -> sRGB hex (for human-readable findings only, not for the ΔE math)."""
    lab_l, lab_a, lab_b = lab
    fy = (lab_l + 16) / 116
    fx = fy + lab_a / 500
    fz = fy - lab_b / 200

    def inv(t: float) -> float:
        delta = 6.0 / 29.0
        return t**3 if t > delta else 3 * delta**2 * (t - 4.0 / 29.0)

    x = inv(fx) * 0.95047
    y = inv(fy)
    z = inv(fz) * 1.08883
    r = x * 3.2406 - y * 1.5372 - z * 0.4986
    g = -x * 0.9689 + y * 1.8758 + z * 0.0415
    b = x * 0.0557 - y * 0.2040 + z * 1.0570

    def gamma(c: float) -> int:
        c = max(0.0, min(1.0, c))
        c = 1.055 * c ** (1 / 2.4) - 0.055 if c > 0.0031308 else 12.92 * c
        return int(round(max(0.0, min(1.0, c)) * 255))

    return "#{:02X}{:02X}{:02X}".format(gamma(r), gamma(g), gamma(b))


def critique_a1(
    png_bytes: bytes,
    palette_hexes: list[str],
    *,
    exempt_mask: npt.NDArray[np.bool_] | None = None,
) -> AxisScore:
    """Score A1 (brand-token-diff) on the rendered PNG vs the brand palette. Deterministic."""
    findings: list[str] = []
    if not palette_hexes:
        return AxisScore(
            axis="A1",
            name="Brand-token-diff",
            objective=True,
            score=None,
            findings=["A1: brand palette is empty — cannot diff (unknown)."],
        )

    palette_lab = np.stack([_hex_to_lab(h) for h in palette_hexes])  # (p, 3)
    clusters = dominant_colors(png_bytes, exempt_mask=exempt_mask)
    considered = [c for c in clusters if c[2] >= _MIN_CLUSTER_COVERAGE]

    off_brand_coverage = 0.0
    for lab, hex_str, coverage in considered:
        de = _delta_e_2000(lab[None, :], palette_lab)  # (p,)
        nearest = float(de.min())
        if nearest > _OFF_BRAND_DE:
            off_brand_coverage += coverage
            findings.append(
                f"off-palette color {hex_str} covers {coverage * 100:.1f}% "
                f"(nearest brand token ΔE2000={nearest:.1f} > {_OFF_BRAND_DE:.0f}) "
                f"— replace with the nearest brand role or remove."
            )

    pct = off_brand_coverage * 100
    hard_fail = off_brand_coverage > 0.40
    if off_brand_coverage < 0.05:
        score, anchor = 5, "off_brand_coverage < 5%"
    elif off_brand_coverage <= 0.15:
        score, anchor = 3, "off_brand_coverage 5-15%"
    elif off_brand_coverage <= 0.30:
        score, anchor = 2, "off_brand_coverage 15-30%"
    else:
        score, anchor = 1, "off_brand_coverage > 30%"

    findings.insert(0, f"off_brand_coverage = {pct:.1f}% across {len(considered)} dominant clusters.")
    if hard_fail:
        findings.append("◆ A1 hard fail: off_brand_coverage > 40%.")

    return AxisScore(
        axis="A1",
        name="Brand-token-diff",
        objective=True,
        score=score,
        findings=findings,
        anchor=anchor,
        hard_fail=hard_fail,
    )
