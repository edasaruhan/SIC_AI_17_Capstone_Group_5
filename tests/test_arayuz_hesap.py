# -*- coding: utf-8 -*-
"""
Giriş / kayıt / Hesabım arayüz testleri (Streamlit AppTest) — geçici SQLite; Gemini'ye istek atılmaz.

    python tests/test_arayuz_hesap.py
"""
import os
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "src"))

os.environ["DATABASE_URL"] = ""     # testler Neon'a asla yazmasın (boş değer: .env yüklense de ezilmez)
os.environ["HESAP_DB_YOLU"] = os.path.join(tempfile.mkdtemp(prefix="uk_hesap_arayuz_"), "test.db")

from streamlit.testing.v1 import AppTest  # noqa: E402

import hesap  # noqa: E402

APP = os.path.join(KOK, "src", "app.py")
SIFRE = "Yumak2026!"


def uygulama(ekran: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90)
    at.query_params["ekran"] = ekran
    at.run()
    return at


def _metin(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown) + " " + " ".join(e.value for e in at.error)


def _dugme(at: AppTest, etiket: str):
    return next(b for b in at.button if b.label == etiket)


def _giris(at: AppTest, eposta: str, sifre: str) -> None:
    at.text_input(key="giris_eposta").input(eposta)
    at.text_input(key="giris_sifre").input(sifre)
    at.checkbox(key="giris_hatirla").check()           # AppTest: dokunulmayan form kutusu sonraki çizimde kaybolur
    _dugme(at, "🔑 Giriş yap").click()
    at.run()


def test_karsilama_ve_yardim_giris_istemez():
    for ekran in ("karsilama", "yardim", "api"):
        at = uygulama(ekran)
        assert not at.exception and "Hoş geldiniz" not in _metin(at), ekran


def test_araclar_girise_yonlendirir_ve_giristen_sonra_geri_doner():
    hesap.kayit_ol("zeynep@ornek.com", "Zeynep", SIFRE, SIFRE, True)
    at = uygulama("satis")
    assert not at.exception and "Hoş geldiniz" in _metin(at) and at.session_state.giris_sonrasi == "satis"
    _giris(at, "zeynep@ornek.com", "yanlis-sifre")
    assert hesap.GENEL_GIRIS_HATASI in _metin(at) and at.session_state.kullanici is None
    _giris(at, "zeynep@ornek.com", SIFRE)
    assert not at.exception and at.session_state.kullanici["ad"] == "Zeynep"
    assert at.session_state.ekran == "satis"
    araclar = uygulama("araclar")
    araclar.session_state.kullanici = at.session_state.kullanici
    araclar.run()
    assert "Hoş geldin, Zeynep!" in _metin(araclar)


def test_kayit_rizasiz_olmaz_verileri_saklar_ve_yeni_oturumda_geri_gelir():
    at = uygulama("pano")
    at.segmented_control(key="giris_sekme_secim").set_value("✨ Kayıt ol").run()
    at.text_input(key="kayit_ad").input("Ayşe")
    at.text_input(key="kayit_eposta").input("ayse@ornek.com")
    at.text_input(key="kayit_sifre").input(SIFRE)
    at.text_input(key="kayit_tekrar").input(SIFRE)
    _dugme(at, "✨ Hesabımı oluştur").click()
    at.run()
    assert "aydınlatma" in _metin(at) and at.session_state.kullanici is None
    at.checkbox(key="kayit_onay").check()
    _dugme(at, "✨ Hesabımı oluştur").click()
    at.run()
    at.run()
    assert not at.exception and at.session_state.kullanici["eposta"] == "ayse@ornek.com"

    at.session_state.gecmis = [{"id": "k1", "tarih": "2026-09-16", "saat": "10:00", "kategori": "Gıda",
                                "anlatim": "Ev yapımı salça yapıyorum.", "instagram": "IG salça",
                                "shopier": "Salça", "ekler": {}, "fiyat": 250.0}]
    at.run()                                                   # çizim sonunda otomatik kayıt
    k = at.session_state.kullanici
    assert hesap.verileri_yukle(k["id"])[0][0]["instagram"] == "IG salça"

    yeni = uygulama("iceriklerim")                             # başka cihaz / yeni oturum
    _giris(yeni, "ayse@ornek.com", SIFRE)
    assert not yeni.exception and [i["id"] for i in yeni.session_state.gecmis] == ["k1"]
    assert yeni.session_state.gecmis[0]["fiyat"] == 250.0


def test_sayfa_yenilenince_cerezle_giris_korunur_cikista_iptal_olur():
    import ekran_hesap
    hesap.kayit_ol("elif@ornek.com", "Elif", SIFRE, SIFRE, True)
    at = uygulama("pano")
    _giris(at, "elif@ornek.com", SIFRE)
    at.run()
    jeton = at.session_state.oturum_jetonu
    assert jeton and at.session_state._cerez is None                                   # çerez tarayıcıya yazıldı

    eski = ekran_hesap._cerez_oku
    ekran_hesap._cerez_oku = lambda: jeton                                             # yenileme: yeni oturum + çerez
    try:
        yeni = uygulama("pano")
        assert not yeni.exception and yeni.session_state.kullanici["ad"] == "Elif"
        assert yeni.session_state.ekran == "pano" and "Hoş geldiniz" not in _metin(yeni)
        yeni.query_params["ekran"] = "hesap"
        yeni.run()
        _dugme(yeni, "🚪 Çıkış yap").click()
        yeni.run()
        assert yeni.session_state.kullanici is None
        tekrar = uygulama("pano")                                                      # çerez kalsa da geçersiz
        assert tekrar.session_state.kullanici is None and "Hoş geldiniz" in _metin(tekrar)
    finally:
        ekran_hesap._cerez_oku = eski


def test_cikis_ve_hesap_silme():
    k = hesap.kayit_ol("fatma@ornek.com", "Fatma", SIFRE, SIFRE, True)
    at = uygulama("hesap")
    _giris(at, "fatma@ornek.com", SIFRE)
    at.run()
    assert at.session_state.ekran == "hesap" and "fatma@ornek.com" in _metin(at)
    _dugme(at, "🚪 Çıkış yap").click()
    at.run()
    assert not at.exception and at.session_state.kullanici is None and at.session_state.ekran == "karsilama"

    at = uygulama("hesap")
    _giris(at, "fatma@ornek.com", SIFRE)
    at.run()
    at.text_input(key="silme_sifre").input(SIFRE)
    at.text_input(key="silme_onay").input("sil")
    _dugme(at, "🗑️ Hesabımı kalıcı olarak sil").click()
    at.run()
    assert "SİL yazın" in _metin(at) and at.session_state.kullanici is not None
    at.text_input(key="silme_onay").input("SİL")
    _dugme(at, "🗑️ Hesabımı kalıcı olarak sil").click()
    at.run()
    assert not at.exception and at.session_state.kullanici is None
    try:
        hesap.giris_yap("fatma@ornek.com", SIFRE)
        raise AssertionError("silinen hesapla giriş yapılabildi")
    except ValueError:
        pass
    assert hesap.verileri_yukle(k.id) == ([], [], [])


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
