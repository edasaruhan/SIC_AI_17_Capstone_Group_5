# -*- coding: utf-8 -*-
"""
Araç ekranları arayüz testleri (Streamlit AppTest) — yapay zekâ fonksiyonları sahtedir,
Gemini'ye istek atılmaz.

    python tests/test_arayuz_araclar.py
"""
import contextlib
import os
import sys
import tempfile
from datetime import date

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "src"))

from PIL import Image, ImageDraw  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import ekran_araclar  # noqa: E402
import gorsel  # noqa: E402
import hesap  # noqa: E402
import satis  # noqa: E402
import uret  # noqa: E402

APP = os.path.join(KOK, "src", "app.py")
GS, SATIS = ekran_araclar.GS_SEKMELER, ekran_araclar.SATIS_SEKMELER


def foto_bayt() -> bytes:
    img = Image.new("RGB", (900, 900), (190, 190, 190))
    d = ImageDraw.Draw(img)
    for x in range(0, 900, 45):
        for y in range(0, 900, 45):
            if (x // 45 + y // 45) % 2:
                d.rectangle([x, y, x + 44, y + 44], fill=(200, 90, 130))
    return gorsel.jpeg(img)


def kayit(no: int) -> dict:
    return {"id": f"k{no}", "tarih": "2026-09-16", "saat": "10:00", "kategori": "Tekstil / El sanatı",
            "anlatim": f"Keçe patik {no} yapıyorum. Yün keçe kullanıyorum, bir günde bitiriyorum.",
            "instagram": f"IG {no}", "shopier": f"Keçe patik {no}. Yün keçeden elde dikilir.", "ekler": {}}


os.environ.pop("DATABASE_URL", None)                       # testler Neon'a asla yazmasın
os.environ["HESAP_DB_YOLU"] = os.path.join(tempfile.mkdtemp(prefix="uk_arayuz_test_"), "test.db")
_KULLANICI = hesap.kayit_ol("test@ornek.com", "Test", "Yumak2026!", "Yumak2026!", True)
OTURUM = {"id": _KULLANICI.id, "eposta": _KULLANICI.eposta, "ad": _KULLANICI.ad,
          "olusturma": _KULLANICI.olusturma.isoformat()}


def uygulama(ekran: str, **durum) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90)
    at.query_params["ekran"] = ekran
    durum.setdefault("kullanici", OTURUM)                      # araçlar girişten sonra açılır
    for anahtar, deger in durum.items():
        at.session_state[anahtar] = deger
    at.run()
    return at


@contextlib.contextmanager
def yamala(nesne, **degerler):
    eski = {ad: getattr(nesne, ad) for ad in degerler}
    for ad, deger in degerler.items():
        setattr(nesne, ad, deger)
    try:
        yield
    finally:
        for ad, deger in eski.items():
            setattr(nesne, ad, deger)


def metinler(at: AppTest) -> str:
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption] +
                    [s.value for s in at.success] + [i.value for i in at.info] +
                    [w.value for w in at.warning] + [c.value for c in at.code])


def hatasiz(at: AppTest) -> None:
    hatalar = [e.value for e in at.exception]
    assert not hatalar, hatalar[:1]


# ---------------------------------------------------------------- araç kutusu
def test_arac_kutusu_gezinir_ve_giris_yapan_tanitimi_atlar():
    at = uygulama("araclar")
    hatasiz(at)
    assert metinler(at).count('class="arac-karti') == 4
    at.button(key="kutu_gorsel").click().run()
    assert at.session_state["ekran"] == "gorsel"
    at = uygulama("karsilama")
    hatasiz(at)
    assert at.session_state["ekran"] == "araclar" and "Hoş geldin, Test!" in metinler(at)


def test_ziyaretci_tanitim_sayfasindan_kayda_gider():
    at = uygulama("karsilama", kullanici=None)
    hatasiz(at)
    metin = metinler(at)
    assert "Neler yapabilirsiniz" in metin and "Kimler için" in metin and "Sık sorulanlar" in metin
    assert not any(b.key == "ayar_gelistirici" for b in at.button)          # ziyaretçiye geliştirici modu yok
    at.button(key="tanitim_alt_kayit").click().run()
    hatasiz(at)
    assert at.session_state["ekran"] == "giris" and at.session_state["giris_sekme"] == "✨ Kayıt ol"
    assert any(t.key == "kayit_eposta" for t in at.text_input)
    assert "önce giriş yapın" not in " ".join(i.value for i in at.info)   # doğrudan gelindi, yönlendirme değil


def test_ust_menude_araclar_dugmesi():
    at = uygulama("anlat")
    at.button(key="nav_araclar").click().run()
    assert at.session_state["ekran"] == "araclar"


# ---------------------------------------------------------------- görsel stüdyosu
def test_gorsel_studyosu_bos_ve_fotografli_hizli_duzeltme():
    at = uygulama("gorsel")
    hatasiz(at)
    assert "Başlamak için bir ürün fotoğrafı" in metinler(at)
    at = uygulama("gorsel", gs_foto=foto_bayt())
    hatasiz(at)
    assert 'class="kalite-kart"' in metinler(at)
    at.button(key="gs_hizli").click().run()
    hatasiz(at)
    assert at.session_state["gs_duzeltilmis"][:2] == b"\xff\xd8"          # JPEG


def test_fotograftan_anlatim_taslakla_anlat_ekranina_gecer():
    sahte = gorsel.FotoAnlatim("örgü patik", ["zikzak desen"], ["pembe"],
                               "Pembe patiklerimi [malzeme] ile örüyorum.", ["Hangi ipi kullandınız?"])
    with yamala(gorsel, foto_anlatim_uret=lambda img, kategori, ozenli=False: sahte):
        at = uygulama("gorsel", gs_foto=foto_bayt(), gs_sekme=GS[1])
        at.button(key="gs_anlatim_btn").click().run()
        hatasiz(at)
        assert "Hangi ipi kullandınız?" in metinler(at) and "zikzak desen" in metinler(at)
        at.button(key="gs_taslak_git").click().run()
    hatasiz(at)
    assert at.session_state["ekran"] == "anlat"
    assert at.session_state["anlatim_metni"] == "Pembe patiklerimi [malzeme] ile örüyorum."


def test_paylasim_gorseli_hazirlanir():
    at = uygulama("gorsel", gs_foto=foto_bayt(), gs_sekme=GS[2])
    at.button(key="gs_pay_btn").click().run()
    assert "başlık girin" in metinler(at)
    at.text_input(key="gs_pay_baslik").input("Keçe patik").run()
    at.button(key="gs_pay_btn").click().run()
    hatasiz(at)
    assert at.session_state["gs_paylasim"][:4] == b"\x89PNG"


def test_katalog_pdf_fiyat_ve_studyo_fotografi():
    at = uygulama("gorsel", gs_sekme=GS[3], gecmis=[kayit(1), kayit(2)], gs_foto=foto_bayt())
    hatasiz(at)
    at.number_input(key="kat_fiyat_k1").set_value(350.0).run()
    at.button(key="kat_studyo_k1").click().run()
    at.checkbox(key="kat_dahil_k2").uncheck().run()
    at.button(key="kat_btn").click().run()
    hatasiz(at)
    pdf = at.session_state["kat_pdf"]
    assert pdf.startswith(b"%PDF")
    gecmis = at.session_state["gecmis"]
    assert gecmis[0]["fiyat"] == 350.0 and gecmis[0]["katalog_foto"]


def test_katalog_bos_durumda_anlata_yonlendirir():
    at = uygulama("gorsel", gs_sekme=GS[3])
    hatasiz(at)
    at.button(key="kat_anlat").click().run()
    assert at.session_state["ekran"] == "anlat"


# ---------------------------------------------------------------- satış araçları
def test_fiyat_hesaplayici_mevcut_fiyat_ve_kaydetme():
    at = uygulama("satis", gecmis=[kayit(1)])
    hatasiz(at)
    # varsayılan: (150 + 15 + 6 × 100) × 1,2 = 918 → 920 TL
    assert "920 TL" in metinler(at) and 'class="fiyat-cubugu"' in metinler(at)
    at.number_input(key="fy_mevcut").set_value(500.0).run()
    assert "emeğinizin saati" in metinler(at)
    at.button(key="fy_kaydet").click().run()
    hatasiz(at)
    assert at.session_state["gecmis"][0]["fiyat"] == 920


def test_musteri_hazir_cevap_ve_mesaja_ozel_cevap():
    at = uygulama("satis", satis_sekme=SATIS[1])
    hatasiz(at)
    assert "[fiyat]" in metinler(at)
    alinan = {}

    def sahte(mesaj, urun_bilgisi="", ton="", ozenli=False):
        alinan.update(mesaj=mesaj, urun=urun_bilgisi)
        return "Merhaba 🌸 [kargo süresi] içinde gönderiyorum."
    with yamala(satis, musteri_cevabi_uret=sahte):
        at = uygulama("satis", satis_sekme=SATIS[1], mc_mod="🪄 Mesaja özel cevap", gecmis=[kayit(1)])
        at.text_area(key="mc_mesaj").input("Kargo ne zaman gelir?").run()
        at.button(key="mc_btn").click().run()
    hatasiz(at)
    assert at.session_state["mc_cevap"].startswith("Merhaba") and "[kargo süresi]" in metinler(at)
    assert alinan["mesaj"] == "Kargo ne zaman gelir?" and "Keçe patik 1" in alinan["urun"]


def test_pazaryeri_ilani_eksik_bilgi_ve_cikarilan_etiketler():
    sahte = satis.Ilan("🌍 Etsy (İngilizce)", "Handmade felt baby booties", ["Material: wool felt"],
                       "Hand stitched.", ["felt booties"], ["ölçü"], ["organic cotton"])
    with yamala(satis, pazaryeri_ilani_uret=lambda *a, **k: sahte):
        at = uygulama("satis", satis_sekme=SATIS[2], gecmis=[kayit(1)])
        at.button(key="ilan_btn").click().run()
    hatasiz(at)
    m = metinler(at)
    assert "Handmade felt baby booties" in m and "ölçü" in m and "organic cotton" in m


def test_ozel_gunler_kampanya_ve_takvime_ekleme():
    with yamala(satis, kampanya_onerisi_uret=lambda *a, **k: "**🎯 Kampanya fikri**\nDeneme önerisi"):
        at = uygulama("satis", satis_sekme=SATIS[3], gecmis=[kayit(1)])
        hatasiz(at)
        assert 'class="gun-kartlari"' in metinler(at)
        at.button(key="og_btn").click().run()
        hatasiz(at)
        assert "Deneme önerisi" in metinler(at)
        at.button(key="og_takvim").click().run()
    hatasiz(at)
    plan = at.session_state["plan"]
    assert plan and all(o.metin.startswith("**🎯") and o.icerik_id == "k1" for o in plan)


def test_sonuc_ekranindan_urun_icin_ilan_sekmesine_gecis():
    k = kayit(1)
    at = uygulama("sonuc", gecmis=[k], aktif_id="k1", sonuc=uret.Icerik("IG 1", "SH 1"))
    hatasiz(at)
    at.button(key="bu_urun_1").click().run()
    hatasiz(at)
    assert (at.session_state["ekran"], at.session_state["satis_sekme"], at.session_state["secili_kayit_id"]) == \
        ("satis", SATIS[2], "k1")


if __name__ == "__main__":
    testler = [(ad, f) for ad, f in sorted(globals().items()) if ad.startswith("test_")]
    hatali = 0
    for ad, f in testler:
        try:
            f()
            print(f"  OK    {ad}")
        except Exception as hata:
            hatali += 1
            print(f"  HATA  {ad}: {hata!r}"[:600])
    print(f"\n{len(testler) - hatali}/{len(testler)} test geçti")
    sys.exit(1 if hatali else 0)
