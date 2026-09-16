# -*- coding: utf-8 -*-
"""
Üretken Kadın — görsel stüdyosu

  • Kalite ölçümü      : parlaklık, kontrast, netlik, çözünürlük uyarıları (yapay zekâ yok)
  • Hızlı düzeltme     : ışık ve kontrast dengesi, hafif keskinlik, kare kırpma (yapay zekâ yok;
                         ürünün rengine dokunmaz: yalnızca parlaklık tonu ayarlanır)
  • Fotoğraftan anlatım: Gemini fotoğrafa bakar, yalnızca GÖRÜNENİ yazar, bilinmeyeni sorar
  • Paylaşım görseli   : fotoğraf + başlık, Instagram kare / hikâye (Pillow, yapay zekâ yok)
  • Katalog            : ürün kartlarından A4 PDF (Pillow, yapay zekâ yok)

Streamlit'e bağımlı değildir (tests/test_gorsel.py).
"""

from __future__ import annotations

import functools
import io
import os
import re
from dataclasses import dataclass

import numpy as np
from google.genai import types
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, UnidentifiedImageError

import prompts
import uret

MAKS_YUKLEME_BAYT = 10 * 1024 * 1024
MAKS_KENAR = 1600

MUREKKEP = (43, 22, 56)
TEMALAR = {"🌸 Pembe": (255, 227, 238), "🌼 Sarı": (255, 241, 201),
           "💧 Mavi": (230, 244, 255), "🤍 Krem": (251, 245, 234)}
VURGULAR = {"🌸 Pembe": (255, 92, 138), "🌼 Sarı": (255, 211, 77),
            "💧 Mavi": (77, 212, 255), "🤍 Krem": (240, 180, 90)}
BICIMLER = {"📱 Instagram kare": (1080, 1080), "📲 Hikâye (dikey)": (1080, 1920)}
A4_150DPI = (1240, 1754)


# ---------------------------------------------------------------------------
# Açma / kaydetme
# ---------------------------------------------------------------------------
def foto_ac(bayt: bytes) -> Image.Image:
    """Yüklenen dosyayı doğrular, yönünü düzeltir, RGB'ye çevirir ve en uzun kenarı 1600 px'e indirir."""
    if not bayt:
        raise ValueError("Fotoğraf boş.")
    if len(bayt) > MAKS_YUKLEME_BAYT:
        raise ValueError("Fotoğraf en fazla 10 MB olabilir.")
    try:
        img = Image.open(io.BytesIO(bayt))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as hata:
        raise ValueError("Bu dosya fotoğraf olarak açılamadı. JPG ya da PNG deneyin.") from hata
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        zemin = Image.new("RGB", img.size, (255, 255, 255))
        zemin.paste(img, mask=img.getchannel("A"))
        img = zemin
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAKS_KENAR, MAKS_KENAR), Image.LANCZOS)
    return img


def jpeg(img: Image.Image, kalite: int = 90) -> bytes:
    tampon = io.BytesIO()
    img.convert("RGB").save(tampon, "JPEG", quality=kalite, optimize=True)
    return tampon.getvalue()


def png(img: Image.Image) -> bytes:
    tampon = io.BytesIO()
    img.save(tampon, "PNG", optimize=True)
    return tampon.getvalue()


# ---------------------------------------------------------------------------
# Kalite ölçümü ve hızlı düzeltme
# ---------------------------------------------------------------------------
@dataclass
class KaliteRaporu:
    puan: int
    parlaklik: float        # 0-255 ortalama
    kontrast: float         # parlaklık standart sapması
    netlik: float           # Laplace varyansı (512 px ölçekte)
    boyut: tuple[int, int]
    uyarilar: list[str]
    iyi_yanlar: list[str]


def kalite_olc(img: Image.Image) -> KaliteRaporu:
    gri = img.convert("L")
    gri.thumbnail((512, 512))
    a = np.asarray(gri, dtype=np.float32)
    parlaklik, kontrast = float(a.mean()), float(a.std())
    laplace = -4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    netlik = float(laplace.var())

    uyarilar, iyi, puan = [], [], 100
    if parlaklik < 80:
        uyarilar.append("Fotoğraf karanlık: gün ışığında, pencere kenarında çekmeyi deneyin.")
        puan -= 25
    elif parlaklik > 205:
        uyarilar.append("Fotoğraf çok parlak: doğrudan güneş ya da flaş yerine yumuşak ışık kullanın.")
        puan -= 20
    else:
        iyi.append("Işık yeterli")
    if netlik < 60:
        uyarilar.append("Fotoğraf bulanık görünüyor: telefonu sabit tutun, ekranda ürüne dokunup odaklayın.")
        puan -= 30
    else:
        iyi.append("Netlik iyi")
    if kontrast < 30:
        uyarilar.append("Fotoğraf soluk: ürünü zeminden ayıran, farklı renkte bir arka plan seçin.")
        puan -= 15
    if min(img.size) < 700:
        uyarilar.append("Çözünürlük düşük: büyütüldüğünde bulanık görünebilir; daha yakından çekin.")
        puan -= 15
    else:
        iyi.append("Çözünürlük yeterli")
    return KaliteRaporu(max(puan, 0), round(parlaklik, 1), round(kontrast, 1), round(netlik, 1),
                        img.size, uyarilar, iyi)


def kare_kirp(img: Image.Image) -> Image.Image:
    g, y = img.size
    k = min(g, y)
    sol, ust = (g - k) // 2, (y - k) // 2
    return img.crop((sol, ust, sol + k, ust + k))


def hizli_duzelt(img: Image.Image, kare: bool = False) -> Image.Image:
    """
    Işık/kontrast dengesi ve hafif keskinlik. Yalnızca parlaklık (Y) kanalı değişir; renk kanalları
    (Cb, Cr) aynen kalır → ürünün rengi korunur. Kontrast artışı sınırlıdır: dar ışık aralığındaki
    fotoğraflarda germe, renkleri patlatıp tonu değiştirmesin (pembe ürün mora dönmesin).
    """
    y, cb, cr = img.convert("YCbCr").split()
    a = np.asarray(y, dtype=np.float32)
    alt, ust = float(np.percentile(a, 1)), float(np.percentile(a, 99))
    aralik = max(ust - alt, 1.0)
    kazanc = min(255.0 / aralik, 1.8)
    a = (a - alt) * kazanc + max(0.0, (255.0 - aralik * kazanc) / 2)
    ortalama = float(a.mean())
    if ortalama < 115:
        a += min(130 - ortalama, 60)
    elif ortalama > 195:
        a -= min(ortalama - 175, 40)
    y = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L")
    sonuc = Image.merge("YCbCr", (y, cb, cr)).convert("RGB")
    sonuc = sonuc.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=3))
    return kare_kirp(sonuc) if kare else sonuc


# ---------------------------------------------------------------------------
# Yapay zekâ: fotoğraftan anlatım
# ---------------------------------------------------------------------------
@dataclass
class FotoAnlatim:
    urun: str
    gorunen_ozellikler: list[str]
    renkler: list[str]
    anlatim_taslagi: str
    sorular: list[str]


def _metin_listesi(deger, sinir: int = 8) -> list[str]:
    return [str(x).strip() for x in (deger if isinstance(deger, list) else []) if str(x).strip()][:sinir]


def foto_anlatim_uret(img: Image.Image, kategori: str, ozenli: bool = False, client=None) -> FotoAnlatim:
    kucuk = img.copy()
    kucuk.thumbnail((1024, 1024))
    veri = uret.json_coz(uret.metin_uret(
        [types.Part.from_bytes(data=jpeg(kucuk, 85), mime_type="image/jpeg"), prompts.foto_anlatim(kategori)],
        ozenli=ozenli, json_yanit=True, client=client))
    urun = str(veri.get("urun", "")).strip()
    taslak = str(veri.get("anlatim_taslagi", "")).strip()
    if not taslak or urun.lower() in ("", "belirsiz"):
        raise ValueError("Fotoğrafta ürün seçilemedi. Ürünü yakından, sade bir zeminde çekmeyi deneyin.")
    return FotoAnlatim(urun, _metin_listesi(veri.get("gorunen_ozellikler")),
                       _metin_listesi(veri.get("renkler")), taslak, _metin_listesi(veri.get("sorular"), 6))



# ---------------------------------------------------------------------------
# Yazı tipi ve metin yerleşimi
# ---------------------------------------------------------------------------
_FONT_ADAYLARI = {
    True: ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf",
           "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    False: ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"),
}
_EMOJI = re.compile("[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F\u200D\u2B00-\u2BFF]")


@functools.lru_cache(maxsize=64)
def _font(boyut: int, kalin: bool = False) -> ImageFont.FreeTypeFont:
    ozel = os.getenv("GORSEL_FONT_KALIN" if kalin else "GORSEL_FONT", "")
    for yol in (ozel, *_FONT_ADAYLARI[kalin]):
        if yol and os.path.exists(yol):
            try:
                return ImageFont.truetype(yol, boyut)
            except OSError:
                continue
    return ImageFont.load_default(size=boyut)


def _temiz(metin: str) -> str:
    """Resme yazılacak metinden emojileri çıkarır (yazı tiplerinde yok, kutu olarak görünürler)."""
    return " ".join(_EMOJI.sub("", metin or "").split())


def _sar(metin: str, font, genislik: int, en_fazla_satir: int) -> list[str]:
    satirlar, satir = [], ""
    for kelime in metin.split():
        while font.getlength(kelime) > genislik and len(kelime) > 1:     # çok uzun tek kelime
            kes = len(kelime)
            while kes > 1 and font.getlength(kelime[:kes]) > genislik:
                kes -= 1
            if satir:
                satirlar.append(satir)
                satir = ""
            satirlar.append(kelime[:kes])
            kelime = kelime[kes:]
        deneme = f"{satir} {kelime}".strip()
        if font.getlength(deneme) <= genislik:
            satir = deneme
        else:
            satirlar.append(satir)
            satir = kelime
    if satir:
        satirlar.append(satir)
    if len(satirlar) > en_fazla_satir:
        satirlar = satirlar[:en_fazla_satir]
        son = satirlar[-1]
        while son and font.getlength(son + "…") > genislik:
            son = son[:-1]
        satirlar[-1] = son.rstrip() + "…"
    return satirlar


def _golgeli_kutu(d: ImageDraw.ImageDraw, kutu, dolgu, cizgi: int = 6, golge: int = 12, yaricap: int = 32):
    x0, y0, x1, y1 = kutu
    d.rounded_rectangle([x0 + golge, y0 + golge, x1 + golge, y1 + golge], radius=yaricap, fill=MUREKKEP)
    d.rounded_rectangle(kutu, radius=yaricap, fill=dolgu, outline=MUREKKEP, width=cizgi)


def tl_metni(tutar: float) -> str:
    """1250.5 → '1.250,50 TL'; tam sayıda kuruş yazılmaz."""
    if abs(tutar - round(tutar)) < 0.005:
        return f"{round(tutar):,}".replace(",", ".") + " TL"
    return f"{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


# ---------------------------------------------------------------------------
# Paylaşım görseli
# ---------------------------------------------------------------------------
def paylasim_gorseli(img: Image.Image, baslik: str, alt_yazi: str = "",
                     bicim: str = "📱 Instagram kare", tema: str = "🌸 Pembe",
                     rozet: str = "El emeği") -> Image.Image:
    if bicim not in BICIMLER or tema not in TEMALAR:
        raise ValueError("Bilinmeyen biçim ya da tema.")
    G, Y = BICIMLER[bicim]
    zemin, vurgu = TEMALAR[tema], VURGULAR[tema]
    tuval = Image.new("RGB", (G, Y), zemin)
    d = ImageDraw.Draw(tuval)
    nokta = tuple(max(0, c - 22) for c in zemin)
    for x in range(18, G, 36):
        for y in range(18, Y, 36):
            d.ellipse([x, y, x + 3, y + 3], fill=nokta)

    kenar, kare = 70, G == Y
    foto_kutu = (kenar, 90, G - kenar, 90 + 600) if kare else (kenar, 170, G - kenar, 170 + G - 2 * kenar)
    fg, fy = foto_kutu[2] - foto_kutu[0], foto_kutu[3] - foto_kutu[1]
    d.rounded_rectangle([foto_kutu[0] + 14, foto_kutu[1] + 14, foto_kutu[2] + 14, foto_kutu[3] + 14],
                        radius=36, fill=MUREKKEP)
    maske = Image.new("L", (fg, fy), 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, fg - 1, fy - 1], radius=36, fill=255)
    tuval.paste(ImageOps.fit(img, (fg, fy), Image.LANCZOS), foto_kutu[:2], maske)
    d.rounded_rectangle(foto_kutu, radius=36, outline=MUREKKEP, width=8)

    rozet = _temiz(rozet) or "El emeği"
    font_r = _font(38 if kare else 46, kalin=True)
    rg, ry = int(font_r.getlength(rozet)) + 56, int(font_r.size * 1.9)
    rx, rust = foto_kutu[0] + 34, foto_kutu[1] - ry // 2
    _golgeli_kutu(d, (rx, rust, rx + rg, rust + ry), vurgu, cizgi=5, golge=6, yaricap=ry // 2)
    d.text((rx + rg / 2, rust + ry / 2), rozet, font=font_r, fill=MUREKKEP, anchor="mm")

    # Başlık ve alt yazı, fotoğrafın altında kalan alanda dikey ortalanır
    font_b, font_a = _font(70 if kare else 88, kalin=True), _font(40 if kare else 52)
    b_satirlar = _sar(_temiz(baslik) or "El emeği", font_b, G - 2 * kenar, 2 if kare else 3)
    alt = _temiz(alt_yazi)
    a_satirlar = _sar(alt, font_a, G - 2 * kenar, 2 if kare else 3) if alt else []
    b_ara, a_ara = int(font_b.size * 1.2), int(font_a.size * 1.3)
    blok = len(b_satirlar) * b_ara + (8 + len(a_satirlar) * a_ara if a_satirlar else 0)
    alan_ust, alan_alt = foto_kutu[3] + 14, Y - 50              # gölge payı ve alt kenar boşluğu
    y = max(foto_kutu[3] + 40, alan_ust + (alan_alt - alan_ust - blok) // 2)
    for satir in b_satirlar:
        d.text((kenar, y), satir, font=font_b, fill=MUREKKEP)
        y += b_ara
    y += 8
    for satir in a_satirlar:
        d.text((kenar, y), satir, font=font_a, fill=MUREKKEP)
        y += a_ara
    return tuval


# ---------------------------------------------------------------------------
# Katalog (A4, sayfa başına 6 ürün)
# ---------------------------------------------------------------------------
def katalog_pdf(urunler: list[dict], baslik: str = "Ürün kataloğu", alt_baslik: str = "",
                tema: str = "🌸 Pembe") -> bytes:
    """
    urunler: [{"ad": str, "aciklama": str, "fiyat": float | None, "foto": Image | None}, ...]
    Döndürür: PDF baytları (WhatsApp'ta paylaşılabilir).
    """
    if not urunler:
        raise ValueError("Katalog için en az bir ürün seçin.")
    zemin, vurgu = TEMALAR.get(tema, TEMALAR["🌸 Pembe"]), VURGULAR.get(tema, VURGULAR["🌸 Pembe"])
    G, Y = A4_150DPI
    kenar, ust, aralik, pad = 80, 290, 40, 20
    kart_g = (G - 2 * kenar - aralik) // 2
    kart_y = (Y - ust - 110 - 2 * aralik) // 3
    font_bas, font_alt = _font(64, kalin=True), _font(32)
    font_ad, font_acik, font_fiyat, font_dip = _font(32, kalin=True), _font(23), _font(30, kalin=True), _font(22)
    sayfa_sayisi = (len(urunler) + 5) // 6
    sayfalar = []
    for s in range(sayfa_sayisi):
        sayfa = Image.new("RGB", (G, Y), (255, 255, 255))
        d = ImageDraw.Draw(sayfa)
        d.rectangle([0, 0, G, 210], fill=zemin)
        d.line([0, 210, G, 210], fill=MUREKKEP, width=6)
        d.text((kenar, 55), _sar(_temiz(baslik) or "Ürün kataloğu", font_bas, G - 2 * kenar, 1)[0],
               font=font_bas, fill=MUREKKEP)
        if _temiz(alt_baslik):
            d.text((kenar, 140), _sar(_temiz(alt_baslik), font_alt, G - 2 * kenar, 1)[0],
                   font=font_alt, fill=MUREKKEP)
        for j, urun in enumerate(urunler[s * 6:(s + 1) * 6]):
            x0 = kenar + (j % 2) * (kart_g + aralik)
            y0 = ust + (j // 2) * (kart_y + aralik)
            _golgeli_kutu(d, (x0, y0, x0 + kart_g, y0 + kart_y), (255, 255, 255), cizgi=4, golge=8, yaricap=24)
            foto_kutu = (x0 + pad, y0 + pad, x0 + kart_g - pad, y0 + pad + 200)
            fg, fy = foto_kutu[2] - foto_kutu[0], foto_kutu[3] - foto_kutu[1]
            if isinstance(urun.get("foto"), Image.Image):
                maske = Image.new("L", (fg, fy), 0)
                ImageDraw.Draw(maske).rounded_rectangle([0, 0, fg - 1, fy - 1], radius=16, fill=255)
                sayfa.paste(ImageOps.fit(urun["foto"], (fg, fy), Image.LANCZOS), foto_kutu[:2], maske)
            else:
                d.rounded_rectangle(foto_kutu, radius=16, fill=zemin)
                d.text(((foto_kutu[0] + foto_kutu[2]) / 2, (foto_kutu[1] + foto_kutu[3]) / 2),
                       "Fotoğraf eklenmedi", font=font_acik, fill=MUREKKEP, anchor="mm")
            y = foto_kutu[3] + 12
            ad = _sar(_temiz(urun.get("ad", "")) or "Ürün", font_ad, kart_g - 2 * pad, 1)[0]
            d.text((x0 + pad, y), ad, font=font_ad, fill=MUREKKEP)
            y += 44
            for satir in _sar(_temiz(urun.get("aciklama", "")), font_acik, kart_g - 2 * pad, 2):
                d.text((x0 + pad, y), satir, font=font_acik, fill=MUREKKEP)
                y += 30
            fiyat = urun.get("fiyat")
            etiket = tl_metni(float(fiyat)) if fiyat else "Fiyat için yazın"
            eg = int(font_fiyat.getlength(etiket)) + 48
            ey = y0 + kart_y - pad - 58
            d.rounded_rectangle([x0 + pad, ey, x0 + pad + eg, ey + 56], radius=28, fill=vurgu,
                                outline=MUREKKEP, width=3)
            d.text((x0 + pad + eg / 2, ey + 28), etiket, font=font_fiyat, fill=MUREKKEP, anchor="mm")
        d.text((kenar, Y - 70), "Üretken Kadın ile hazırlandı", font=font_dip, fill=MUREKKEP)
        d.text((G - kenar, Y - 70), f"{s + 1} / {sayfa_sayisi}", font=font_dip, fill=MUREKKEP, anchor="ra")
        sayfalar.append(sayfa)
    tampon = io.BytesIO()
    sayfalar[0].save(tampon, "PDF", save_all=True, append_images=sayfalar[1:], resolution=150.0)
    return tampon.getvalue()
