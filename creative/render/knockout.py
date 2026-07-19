"""Knockout logo derivation: same mark, every opaque pixel forced to white, alpha kept.

The one-click fix for a brand-QA "logo invisible on its ground" failure (the Glo2Go
dogfood lesson): a purple mark on the purple hero ground needs a white variant, not a
redesign. Pixel work happens in the browser canvas (house rule: no PIL/numpy, data-URI
in/out, no network).
"""

from __future__ import annotations

import base64

_KNOCKOUT_JS = """
async (src) => {
  const img = new Image();
  await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = src; });
  const canvas = document.createElement('canvas');
  canvas.width = img.width; canvas.height = img.height;
  const g = canvas.getContext('2d');
  g.drawImage(img, 0, 0);
  const im = g.getImageData(0, 0, img.width, img.height);
  const d = im.data;
  for (let i = 0; i < d.length; i += 4) { d[i] = 255; d[i + 1] = 255; d[i + 2] = 255; }
  g.putImageData(im, 0, 0);
  return canvas.toDataURL('image/png');
}
"""


async def derive_knockout_png(image_bytes: bytes, mime: str) -> bytes:
    """White-knockout PNG of `image_bytes` (RGB -> white, alpha preserved). Browser-only;
    raises on a broken/undecodable image rather than returning a blank mark."""
    from playwright.async_api import async_playwright

    src = f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii")
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page()
            data_url = await page.evaluate(_KNOCKOUT_JS, src)
        finally:
            await browser.close()
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        raise ValueError(f"knockout produced an unexpected payload: {data_url[:40]!r}")
    return base64.b64decode(data_url[len(prefix) :])
