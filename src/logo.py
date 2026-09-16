# -*- coding: utf-8 -*-
"""
Üretken Kadın logosu — "İlmekli ü": kesintisiz bir iplikten çizilmiş ü; ipliğin ucu bir ilmek atıp
serbest kalır, noktalar iki düğüm. Renkler: çivit #27348B, nane #3FB59E, kâğıt #F7F7F2.

Sekme simgesi (assets/favicon.png) bu SVG'den bir kez üretilmiştir; SVG değişirse yeniden üretin:
    python src/logo.py        # assets/logo.svg yazar ve PNG için komutu gösterir
"""

from __future__ import annotations

from pathlib import Path

CIVIT, NANE, KAGIT = "#27348B", "#3FB59E", "#F7F7F2"

SVG = (
    '<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Üretken Kadın logosu">'
    f'<rect width="120" height="120" rx="28" fill="{CIVIT}"/>'
    f'<circle cx="41" cy="28" r="6.5" fill="{NANE}"/><circle cx="73" cy="28" r="6.5" fill="{NANE}"/>'
    '<path d="M41 46 V70 C41 94 73 94 73 70 V46 V86 C73 100 84 104 92 97 C100 90 94 78 85 82 '
    f'C78 86 84 100 100 102" stroke="{KAGIT}" stroke-width="9" fill="none" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>'
)                                                           # tek satır: Markdown içine gömülünce bozulmasın

KLASOR = Path(__file__).resolve().parent / "assets"          # src/ altında: Docker imajına da girer
FAVICON_YOLU = KLASOR / "favicon.png"


def page_icon() -> str:
    """st.set_page_config için; PNG yoksa emojiye düşer (uygulama logoya bağlı olarak çökmesin)."""
    return str(FAVICON_YOLU) if FAVICON_YOLU.exists() else "🧵"


if __name__ == "__main__":
    KLASOR.mkdir(exist_ok=True)
    svg_yolu = KLASOR / "logo.svg"
    svg_yolu.write_text(SVG, encoding="utf-8")
    print(f"{svg_yolu} yazıldı. PNG için (Windows, Edge):")
    print(f'  msedge --headless=new --default-background-color=00000000 --window-size=256,256 '
          f'--screenshot="{FAVICON_YOLU}" "{svg_yolu.as_uri()}"')
