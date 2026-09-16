# -*- coding: utf-8 -*-
"""
API başvuruları: basvuru.py birim testleri ve form / yönetici paneli arayüz testleri (geçici SQLite).

    python tests/test_basvuru.py
"""
import os
import sys
import tempfile
from pathlib import Path

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "src"))

_KLASOR = tempfile.mkdtemp(prefix="uk_basvuru_test_")
os.environ.pop("DATABASE_URL", None)                       # testler Neon'a asla yazmasın
os.environ["HESAP_DB_YOLU"] = os.path.join(_KLASOR, "arayuz.db")

from streamlit.testing.v1 import AppTest  # noqa: E402

import basvuru  # noqa: E402
import hesap  # noqa: E402

APP = os.path.join(KOK, "src", "app.py")
AMAC = "Pazaryerimizdeki kadın üreticilerin ürün açıklamalarını hazırlamasına yardım etmek istiyoruz."


def yeni_motor(ad):
    return hesap._motor(f"sqlite:///{(Path(_KLASOR) / f'{ad}.db').as_posix()}")


def _gecerli(**degisen):
    alanlar = dict(kurum="Örnek Pazar A.Ş.", kurum_turu=basvuru.KURUM_TURLERI[0], yetkili="Elif Kaya",
                   eposta="elif@ornekpazar.com", web="www.ornekpazar.com", amac=AMAC,
                   aylik_hacim=basvuru.AYLIK_HACIMLER[1], kvkk_onay=True)
    alanlar.update(degisen)
    return alanlar


def _hata(icerir, m, **degisen):
    try:
        basvuru.basvuru_yap(**_gecerli(**degisen), m=m)
    except ValueError as e:
        assert icerir in str(e), f"{icerir!r} beklenirken: {e}"
        return
    raise AssertionError("ValueError bekleniyordu")


def test_gecerli_basvuru_kaydedilir_ve_listelenir():
    m = yeni_motor("kayit")
    no = basvuru.basvuru_yap(**_gecerli(eposta="Elif@OrnekPazar.com"), m=m)
    kayitlar = basvuru.liste(m=m)
    assert len(no) == 8 and len(kayitlar) == 1
    x = kayitlar[0]
    assert x.id.upper().startswith(no) and x.eposta == "elif@ornekpazar.com" and x.durum == "yeni"


def test_dogrulama_hatalari():
    m = yeni_motor("dogrulama")
    _hata("aydınlatma", m, kvkk_onay=False)
    _hata("Kurum adı", m, kurum=" ")
    _hata("e-posta", m, eposta="elif@")
    _hata("en az 30", m, amac="API lazım")
    _hata("Web sitesi", m, web="bu bir adres değil")
    _hata("Kurum türünü", m, kurum_turu="Uydurma")
    _hata("kullanım miktarını", m, aylik_hacim="")
    assert basvuru.liste(m=m) == []


def test_ayni_epostadan_gunluk_sinir():
    m = yeni_motor("sinir")
    for _ in range(basvuru.EPOSTA_GUNLUK_SINIR):
        basvuru.basvuru_yap(**_gecerli(), m=m)
    _hata("bugün zaten", m)
    basvuru.basvuru_yap(**_gecerli(eposta="baska@ornek.com"), m=m)


def test_durum_degistirme_ve_silme():
    m = yeni_motor("durum")
    no = basvuru.basvuru_yap(**_gecerli(), m=m)
    basvuru.durum_degistir(no, "onaylandi", m=m)
    assert basvuru.liste(m=m)[0].durum == "onaylandi"
    for fonk, arg in ((basvuru.durum_degistir, (no, "uydurma")), (basvuru.durum_degistir, ("ABC", "yeni")),
                      (basvuru.sil, ("00000000",))):
        try:
            fonk(*arg, m=m)
            raise AssertionError("ValueError bekleniyordu")
        except ValueError:
            pass
    basvuru.sil(no, m=m)
    assert basvuru.liste(m=m) == []


def test_yonetici_yalnizca_ortam_degiskeninden():
    eski = os.environ.get("YONETICI_EPOSTALARI")
    try:
        os.environ.pop("YONETICI_EPOSTALARI", None)
        assert not basvuru.yonetici_mi("ekip@ornek.com")
        os.environ["YONETICI_EPOSTALARI"] = " Ekip@Ornek.com , ikinci@ornek.com"
        assert basvuru.yonetici_mi("ekip@ornek.com") and basvuru.yonetici_mi("ikinci@ornek.com")
        assert not basvuru.yonetici_mi("baskasi@ornek.com") and not basvuru.yonetici_mi(None)
    finally:
        if eski is None:
            os.environ.pop("YONETICI_EPOSTALARI", None)
        else:
            os.environ["YONETICI_EPOSTALARI"] = eski


# ---------------------------------------------------------------- arayüz
def _form_doldur(at, **degisen):
    a = _gecerli(**degisen)
    at.text_input(key="basvuru_kurum").input(a["kurum"])
    at.selectbox(key="basvuru_tur").select(a["kurum_turu"])
    at.text_input(key="basvuru_yetkili").input(a["yetkili"])
    at.text_input(key="basvuru_eposta").input(a["eposta"])
    at.text_area(key="basvuru_amac").input(a["amac"])
    at.selectbox(key="basvuru_hacim").select(a["aylik_hacim"])
    if a["kvkk_onay"]:
        at.checkbox(key="basvuru_onay").check()
    next(b for b in at.button if b.label == "📨 Başvuruyu gönder").click()
    at.run()


def _api_sayfasi():
    at = AppTest.from_file(APP, default_timeout=90)
    at.query_params["ekran"] = "api"
    at.run()
    assert not at.exception
    return at


def test_ziyaretci_formdan_basvurur_ve_yonetici_gorur():
    once = len(basvuru.liste())
    at = _api_sayfasi()
    _form_doldur(at, eposta="form@ornekpazar.com", kvkk_onay=False)
    assert any("aydınlatma" in e.value for e in at.error) and len(basvuru.liste()) == once
    at.checkbox(key="basvuru_onay").check()
    next(b for b in at.button if b.label == "📨 Başvuruyu gönder").click()
    at.run()
    assert not at.exception and at.session_state.basvuru_no
    assert any("Başvurunuz alındı" in s.value for s in at.success)
    assert basvuru.liste()[0].eposta == "form@ornekpazar.com"

    # tuzak alan doldurulursa kayıt yapılmaz ama bota başarı gösterilir
    bot = _api_sayfasi()
    bot.text_input(key="basvuru_tuzak").input("http://spam")
    _form_doldur(bot, eposta="bot@spam.com")
    assert bot.session_state.basvuru_no == "ALINDI" and all(x.eposta != "bot@spam.com" for x in basvuru.liste())

    # yönetici Hesabım sayfasında görür; sıradan kullanıcı görmez
    os.environ["YONETICI_EPOSTALARI"] = "ekip@ornek.com"
    try:
        for eposta, gorur in (("ekip@ornek.com", True), ("uye@ornek.com", False)):
            k = hesap.kayit_ol(eposta, "Ekip", "Yumak2026!", "Yumak2026!", True)
            h = AppTest.from_file(APP, default_timeout=90)
            h.query_params["ekran"] = "hesap"
            h.session_state["kullanici"] = {"id": k.id, "eposta": k.eposta, "ad": k.ad,
                                            "olusturma": k.olusturma.isoformat()}
            h.run()
            assert not h.exception
            metin = " ".join(x.value for x in h.markdown)
            assert ("form@ornekpazar.com" in metin) is gorur and \
                   any("API başvuruları" in e.label for e in h.expander) is gorur
    finally:
        os.environ.pop("YONETICI_EPOSTALARI", None)


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
