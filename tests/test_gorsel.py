# -*- coding: utf-8 -*-
"""
gorsel.py testleri — Gemini'ye istek atmaz (sahte istemci), internet gerektirmez.

    python tests/test_gorsel.py
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import gorsel  # noqa: E402


def dama(g=1200, y=900, acik=190, koyu=90, kare=40) -> Image.Image:
    """Net, orta parlaklıkta, yüksek kontrastlı yapay fotoğraf."""
    img = Image.new("RGB", (g, y), (acik, acik, acik))
    d = ImageDraw.Draw(img)
    for x in range(0, g, kare):
        for yy in range(0, y, kare):
            if (x // kare + yy // kare) % 2:
                d.rectangle([x, yy, x + kare - 1, yy + kare - 1], fill=(koyu, koyu - 20, koyu + 20))
    return img


def _hata_bekle(fonk, *arg, **kw):
    try:
        fonk(*arg, **kw)
    except ValueError:
        return
    raise AssertionError("ValueError bekleniyordu")


# ---------------------------------------------------------------- açma
def test_foto_ac_dogrular_kucultur_ve_seffafligi_beyaza_cevirir():
    _hata_bekle(gorsel.foto_ac, b"")
    _hata_bekle(gorsel.foto_ac, b"bu bir foto degil")
    buyuk = Image.new("RGBA", (3200, 2000), (0, 0, 0, 0))
    tampon = io.BytesIO()
    buyuk.save(tampon, "PNG")
    img = gorsel.foto_ac(tampon.getvalue())
    assert img.mode == "RGB" and max(img.size) == 1600 and img.getpixel((10, 10)) == (255, 255, 255)
    fazla = b"0" * (gorsel.MAKS_YUKLEME_BAYT + 1)
    _hata_bekle(gorsel.foto_ac, fazla)


# ---------------------------------------------------------------- kalite
def test_iyi_fotografta_uyari_yok():
    r = gorsel.kalite_olc(dama())
    assert r.uyarilar == [] and r.puan == 100, (r.uyarilar, r.parlaklik, r.kontrast, r.netlik)


def test_karanlik_bulanik_soluk_ve_kucuk_fotograf_uyarilari():
    karanlik = Image.eval(dama(), lambda v: int(v * 0.35))
    assert any("karanlık" in u for u in gorsel.kalite_olc(karanlik).uyarilar)
    bulanik = dama().filter(ImageFilter.GaussianBlur(12))
    r = gorsel.kalite_olc(bulanik)
    assert any("bulanık" in u for u in r.uyarilar), r.netlik
    soluk = dama(acik=150, koyu=135)
    assert any("soluk" in u for u in gorsel.kalite_olc(soluk).uyarilar)
    kucuk = dama(400, 300, kare=10)
    assert any("Çözünürlük" in u for u in gorsel.kalite_olc(kucuk).uyarilar)
    assert gorsel.kalite_olc(karanlik).puan < 100


def test_hizli_duzeltme_aydinlatir_rengi_korur_ve_kirpar():
    import numpy as np
    koyu = Image.new("RGB", (900, 600), (60, 25, 40))                 # koyu pembe ürün
    ImageDraw.Draw(koyu).rectangle([200, 150, 700, 450], fill=(110, 45, 70))
    duzelt = gorsel.hizli_duzelt(koyu)
    assert duzelt.size == koyu.size
    assert np.asarray(duzelt.convert("L")).mean() > np.asarray(koyu.convert("L")).mean() + 20
    r, g, b = duzelt.getpixel((450, 300))
    assert r > g and r > b                                             # pembe ton korunur, griye dönmez
    assert gorsel.hizli_duzelt(koyu, kare=True).size == (600, 600)


# ---------------------------------------------------------------- paylaşım görseli
def test_paylasim_gorseli_boyutlari_uzun_baslik_ve_emoji():
    foto = dama(800, 1200)
    for bicim, boyut in gorsel.BICIMLER.items():
        for tema in gorsel.TEMALAR:
            img = gorsel.paylasim_gorseli(
                foto, "🧶 El örgüsü organik pamuk bebek battaniyesi, anneannemden öğrendiğim desenle "
                      "tamamen elde örülmüş çok uzun bir başlık ŞşİıĞğ",
                "Sipariş için DM 💌 " * 5, bicim=bicim, tema=tema, rozet="🌸 Yeni ürün")
            assert img.size == boyut
    _hata_bekle(gorsel.paylasim_gorseli, foto, "x", bicim="kare")


def test_metin_sarma_sinirlar():
    font = gorsel._font(40, kalin=True)
    satirlar = gorsel._sar("Çoooooooooooooooooooooooooooooooooooooookuzun kelime ve devamı " * 3, font, 300, 3)
    assert len(satirlar) == 3 and satirlar[-1].endswith("…")
    assert all(font.getlength(s) <= 300 for s in satirlar)
    assert gorsel._temiz("🧶 El işi ✨") == "El işi"


def test_tl_metni():
    assert gorsel.tl_metni(1250) == "1.250 TL" and gorsel.tl_metni(99.5) == "99,50 TL"


# ---------------------------------------------------------------- katalog
def test_katalog_pdf_sayfa_sayisi():
    urunler = [{"ad": f"Ürün {i} 🧶", "aciklama": "El örgüsü, organik pamuk. " * 6,
                "fiyat": 450 + i if i % 3 else None, "foto": dama(600, 600) if i % 2 else None}
               for i in range(7)]
    pdf = gorsel.katalog_pdf(urunler, "Ayşe'nin Atölyesi", "Sipariş: Instagram @ornek")
    assert pdf.startswith(b"%PDF")
    assert len(re.findall(rb"/Type\s*/Page\b(?!s)", pdf)) == 2
    _hata_bekle(gorsel.katalog_pdf, [])


# ---------------------------------------------------------------- yapay zekâ (sahte istemci)
class _Yanit:
    def __init__(self, metin=None, gorsel_bayt=None):
        self.text = metin
        parca = type("P", (), {"inline_data": type("I", (), {"data": gorsel_bayt})()})() if gorsel_bayt else None
        icerik = type("C", (), {"parts": [parca] if parca else []})()
        self.candidates = [type("A", (), {"content": icerik})()]


class SahteIstemci:
    def __init__(self, yanit=None, hata=None):
        self.yanit, self.hata, self.cagrilar = yanit, hata, []
        self.models = self

    def generate_content(self, model, contents, config=None):
        self.cagrilar.append((model, contents, config))
        if self.hata:
            raise self.hata
        return self.yanit


def test_foto_anlatim_fotografi_gonderir_ve_belirsizi_reddeder():
    veri = {"urun": "örgü battaniye", "gorunen_ozellikler": ["zikzak desen"], "renkler": ["pembe"],
            "anlatim_taslagi": "Pembe zikzak desenli battaniyemi [malzeme] ile örüyorum.",
            "sorular": ["Hangi ipi kullandınız?"]}
    c = SahteIstemci(_Yanit(json.dumps(veri, ensure_ascii=False)))
    sonuc = gorsel.foto_anlatim_uret(dama(), "Tekstil / El sanatı", client=c)
    assert sonuc.urun == "örgü battaniye" and sonuc.sorular == ["Hangi ipi kullandınız?"]
    _, contents, config = c.cagrilar[0]
    assert contents[0].inline_data.mime_type == "image/jpeg" and "UYDURMA" in contents[1]
    assert config.response_mime_type == "application/json"
    belirsiz = SahteIstemci(_Yanit(json.dumps({"urun": "belirsiz", "anlatim_taslagi": ""})))
    _hata_bekle(gorsel.foto_anlatim_uret, dama(), "Gıda", client=belirsiz)


def test_arka_plan_ucretsiz_katman_hatasi_ve_basari():
    sahne = next(iter(gorsel.prompts.ARKA_PLAN_SAHNELERI))
    hata = Exception("429 RESOURCE_EXHAUSTED quotaMetric generativelanguage.googleapis.com/generate_content_free_tier_requests")
    try:
        gorsel.arka_plan_degistir(dama(), sahne, client=SahteIstemci(hata=hata))
        raise AssertionError("GorselKotaHatasi bekleniyordu")
    except gorsel.GorselKotaHatasi as e:
        assert e.args[0] == "ucretsiz"

    tampon = io.BytesIO()
    Image.new("RGB", (512, 512), (240, 230, 220)).save(tampon, "PNG")
    c = SahteIstemci(_Yanit(gorsel_bayt=tampon.getvalue()))
    sonuc = gorsel.arka_plan_degistir(dama(), sahne, client=c)
    assert sonuc.size == (512, 512)
    model, contents, config = c.cagrilar[0]
    assert model == gorsel.GORSEL_MODEL and config.response_modalities == ["IMAGE"]
    assert "HİÇ DEĞİŞTİRME" in contents[1]
    _hata_bekle(gorsel.arka_plan_degistir, dama(), "Uzay", client=c)
    _hata_bekle(gorsel.arka_plan_degistir, dama(), sahne, client=SahteIstemci(_Yanit(metin="görsel yok")))


if __name__ == "__main__":
    testler = [(ad, f) for ad, f in sorted(globals().items()) if ad.startswith("test_")]
    hatali = 0
    for ad, f in testler:
        try:
            f()
            print(f"  OK    {ad}")
        except Exception as hata:
            hatali += 1
            print(f"  HATA  {ad}: {hata!r}")
    print(f"\n{len(testler) - hatali}/{len(testler)} test geçti")
    sys.exit(1 if hatali else 0)
