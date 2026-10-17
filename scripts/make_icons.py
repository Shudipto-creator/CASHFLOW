"""Generate the CASHFLOW favicon set from a single drawn design.

Produces: favicon.svg (hand drawn), favicon.ico (32px), apple-touch-icon.png
(180px), icon-192.png, icon-512.png, site.webmanifest.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
IMG = STATIC / "img"
ICONS = STATIC  # favicon files live at /static/*

NAVY = (18, 38, 63, 255)
WHITE = (255, 255, 255, 255)


def draw_design(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), NAVY)
    d = ImageDraw.Draw(img)
    pad = size * 0.25
    bar_h = size * 0.125
    # two flat bars of different heights (the CASHFLOW mark)
    d.rounded_rectangle(
        [pad, size * 0.38, pad + size * 0.31, size * 0.38 + bar_h],
        radius=size * 0.06,
        fill=WHITE,
    )
    d.rounded_rectangle(
        [pad + size * 0.06, size * 0.62, pad + size * 0.56, size * 0.62 + bar_h],
        radius=size * 0.06,
        fill=WHITE,
    )
    return img


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)

    # favicon.svg (source of truth)
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="#12263F" rx="6"/>
  <rect x="8" y="10" width="10" height="4" fill="#FFFFFF" rx="2"/>
  <rect x="10" y="18" width="14" height="4" fill="#FFFFFF" rx="2"/>
</svg>'''
    (IMG / "favicon.svg").write_text(svg)

    # favicon.ico (32px)
    draw_design(32).save(ICONS / "favicon.ico", sizes=[(32, 32)])

    # apple-touch-icon 180px
    draw_design(180).save(ICONS / "apple-touch-icon.png")

    # icon-192.png, icon-512.png
    draw_design(192).save(ICONS / "icon-192.png")
    draw_design(512).save(ICONS / "icon-512.png")

    # site.webmanifest
    manifest = {
        "name": "CASHFLOW",
        "short_name": "CASHFLOW",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#F7F8FA",
        "theme_color": "#12263F",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/static/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
    }
    import json

    (ICONS / "site.webmanifest").write_text(json.dumps(manifest, indent=2))
    print("icons generated")


if __name__ == "__main__":
    main()
