"""
Image Branding — Wendet Marken-Branding auf Bilder an.
Nutzt Pillow für Overlays, Logo, Farben, Text.
Farben werden aus brand_knowledge.json geladen (Fallback: neutrales Dunkelblau).
"""
import json
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Lädt eine serifenlose Schrift passend zum Betriebssystem."""
    candidates = [
        "arial.ttf",                              # Windows (im PATH)
        "C:/Windows/Fonts/arial.ttf",             # Windows (absolut)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",   # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",    # macOS
        "/System/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    """Wandelt #RRGGBB in (R, G, B) um."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _get_brand_colors() -> tuple:
    """
    Lädt Markenfarben aus brand_knowledge.json.
    Gibt (accent_color, bar_color) als RGB-Tuple zurück.
    Fallback: neutrales Dunkelblau + mittleres Blau.
    """
    try:
        bk = json.loads(Path("client/brand_knowledge.json").read_text(encoding="utf-8"))
        accent = bk.get("brand_color_accent") or bk.get("brand_color") or "#4f46e5"
        bar    = bk.get("brand_color_bar")    or "#1e1b4b"
        return _hex_to_rgb(accent), _hex_to_rgb(bar)
    except Exception:
        return (79, 70, 229), (30, 27, 75)   # Indigo-Palette als neutraler Fallback


# ── Konstanten ────────────────────────────────────────────────────────────────
COLOR_WHITE = (255, 255, 255)
LOGO_PATH   = Path("brand/assets/logo.png")

# ── Plattform-Abmessungen ────────────────────────────────────────────────────
PLATFORM_SIZES = {
    "instagram": (1080, 1080),
    "facebook":  (1200,  630),
    "linkedin":  (1200,  627),
    "twitter":   (1500,  500),
    "tiktok":    (1080, 1920),
    "default":   (1080, 1080),
}


class ImageBrander:

    def get_platform_dimensions(self, platform: str):
        return PLATFORM_SIZES.get(platform, PLATFORM_SIZES["default"])

    def apply_branding(self, source_path: Path, output_path: Path, options: dict = None) -> Path:
        """
        Öffnet source_path, skaliert auf Plattform-Größe,
        legt einen Marken-Balken unten drüber, speichert in output_path.
        """
        if options is None:
            options = {}

        platform = options.get("platform", "instagram")
        w, h = self.get_platform_dimensions(platform)

        # ── Bild öffnen & skalieren ───────────────────────────────────────
        img = Image.open(source_path).convert("RGB")
        img = self._fill_cover(img, w, h)

        # ── Unterer Marken-Balken ─────────────────────────────────────────
        accent_color, bar_color = _get_brand_colors()
        bar_h = int(h * 0.18)
        overlay = Image.new("RGBA", (w, bar_h), (*bar_color, 210))
        base = img.convert("RGBA")
        base.paste(overlay, (0, h - bar_h), overlay)

        # ── Akzentstreifen (4px) ──────────────────────────────────────────
        accent = Image.new("RGBA", (w, 4), (*accent_color, 255))
        base.paste(accent, (0, h - bar_h - 4))

        # ── Logo oder Text ────────────────────────────────────────────────
        draw = ImageDraw.Draw(base)

        if LOGO_PATH.exists():
            self._paste_logo(base, bar_h, w, h)
        else:
            self._draw_brand_text(draw, w, h, bar_h)

        # ── Speichern ─────────────────────────────────────────────────────
        output_path.parent.mkdir(parents=True, exist_ok=True)
        base.convert("RGB").save(str(output_path), "JPEG", quality=92)
        return output_path

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    def _fill_cover(self, img: Image.Image, w: int, h: int) -> Image.Image:
        """Skaliert das Bild so, dass es w×h ausfüllt (Cover-Modus)."""
        img_w, img_h = img.size
        scale = max(w / img_w, h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top  = (new_h - h) // 2
        return img.crop((left, top, left + w, top + h))

    def _paste_logo(self, base: Image.Image, bar_h: int, w: int, h: int):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        max_logo_h = int(bar_h * 0.6)
        logo_w = int(logo.width * max_logo_h / logo.height)
        logo = logo.resize((logo_w, max_logo_h), Image.LANCZOS)
        x = 30
        y = h - bar_h + (bar_h - max_logo_h) // 2
        base.paste(logo, (x, y), logo)

    def _draw_brand_text(self, draw: ImageDraw.Draw, w: int, h: int, bar_h: int):
        """Schreibt Markenname & Slogan in den Balken (Fallback wenn kein Logo)."""
        font_name   = _load_font(int(bar_h * 0.35))
        font_slogan = _load_font(int(bar_h * 0.18))

        from brand.foerderkraft_brand import BRAND
        name   = BRAND.get("name", "Meine Marke")
        slogan = BRAND.get("slogan", "")

        y_start = h - bar_h + int(bar_h * 0.12)
        draw.text((30, y_start), name,   font=font_name,   fill=COLOR_WHITE)
        draw.text((30, y_start + int(bar_h * 0.42)), slogan,
                  font=font_slogan, fill=(*COLOR_WHITE[:3], 200))
