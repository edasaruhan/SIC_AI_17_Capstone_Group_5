# -*- coding: utf-8 -*-
"""
REST API testleri — Gemini'ye istek atmaz (çekirdek fonksiyonlar sahte), anahtar gerektirmez.

    python tests/test_api.py
"""
import contextlib
import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import api_guvenlik as guv  # noqa: E402
import kalite  # noqa: E402
import prompts  # noqa: E402
import takvim  # noqa: E402
import trends  # noqa: E402
import uret  # noqa: E402

ANAHTAR = "uk_test_anahtari_bir"
ANAHTAR_HIZLI = "uk_test_anahtari_iki"
H = {"X-API-Key": ANAHTAR}
ANLATIM = "El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum."
ICERIK = {"anlatim": ANLATIM, "kategori": "Tekstil / El sanatı"}


def istemci(kota: int = 3) -> TestClient:
    ortaklar = guv.anahtarlari_yukle(json.dumps({
        guv.anahtar_ozeti(ANAHTAR): {"ad": "Deneme Kooperatifi", "gunluk_kota": kota,
                                     "dakika_siniri": 100},
        guv.anahtar_ozeti(ANAHTAR_HIZLI): {"ad": "Hızlı Ortak", "gunluk_kota": 100,
                                           "dakika_siniri": 2},
    }))
    return TestClient(api.uygulama_olustur(ortaklar, guv.Sayac()),
                      raise_server_exceptions=False)


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


class SahteKalite:
    def __init__(self, mevcut=True):
        self._mevcut = mevcut

    def mevcut(self):
        return self._mevcut

    def tahmin(self, metin, kategori):
        return {"hazir": True, "olasilik": 0.91, "etiket": "Onaya hazır", "gerekceler": []}


cagrilar = []


def sahte_icerik(**k):
    cagrilar.append(k)
    return uret.Icerik("IG: el yapımı battaniye", "Shopier: el yapımı, hediyelik battaniye",
                       model="sahte-model")


def sahte_trend(kategori, **k):
    return trends.TrendSonucu(kelimeler=["el yapımı", "hediyelik", "el emeği"],
                              kaynak="önbellek", kategori=kategori)


@contextlib.contextmanager
def sahte_cekirdek():
    with yamala(uret, icerik_uret=sahte_icerik), yamala(trends, trend_getir=sahte_trend), \
            yamala(kalite, model_al=lambda: SahteKalite()):
        yield


def kod(yanit) -> str:
    return yanit.json()["hata"]["kod"]


# ---------------------------------------------------------------- kimlik doğrulama
def test_saglik_anahtarsiz_acik():
    r = istemci().get("/saglik")
    assert r.status_code == 200 and r.json() == {"durum": "ok", "surum": api.SURUM}


def test_kok_adres_belgeye_yonlendirir_saglik_kontrolu_gunluge_yazilmaz():
    kayitlar = []

    class Toplayici(logging.Handler):
        def emit(self, record):
            kayitlar.append(record.getMessage())
    c = istemci()
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/docs"
    toplayici = Toplayici()
    api.log.addHandler(toplayici)
    try:
        c.get("/saglik")
        c.get("/docs")
    finally:
        api.log.removeHandler(toplayici)
    assert not any("/saglik" in k for k in kayitlar)
    assert any("/docs 200" in k for k in kayitlar)
    assert "/" not in c.get("/openapi.json").json()["paths"]


def test_anahtar_yok_ve_gecersiz_401():
    c = istemci()
    r = c.post("/v1/icerik", json=ICERIK)
    assert r.status_code == 401 and kod(r) == "anahtar_yok"
    r = c.post("/v1/icerik", json=ICERIK, headers={"X-API-Key": "uk_yanlis"})
    assert r.status_code == 401 and kod(r) == "anahtar_gecersiz"


# ---------------------------------------------------------------- içerik
def test_icerik_basarili_yanit_metrikler_ve_kota_basliklari():
    cagrilar.clear()
    with sahte_cekirdek():
        r = istemci().post("/v1/icerik", json=ICERIK, headers=H)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["instagram"].startswith("IG") and j["model"] == "sahte-model"
    assert j["anahtar_kelimeler"] == ["el yapımı", "hediyelik", "el emeği"]
    assert j["anahtar_kelime_kaynagi"] == "önbellek"
    assert j["metrikler"]["seo_kapsami"] == 2 and j["metrikler"]["anahtar_kelime_sayisi"] == 3
    assert j["kalite"]["hazir"] is True and "yapay zekâ" in j["uyari"]
    assert r.headers["X-Kota-Limit"] == "3" and r.headers["X-Kota-Kalan"] == "2"
    assert cagrilar[-1]["anahtar_kelimeler"] == j["anahtar_kelimeler"]
    assert cagrilar[-1]["ozenli"] is False


def test_istekteki_anahtar_kelimeler_trendsi_atlar():
    def cagrilmamali(*a, **k):
        raise AssertionError("Trends çağrılmamalıydı")
    with sahte_cekirdek(), yamala(trends, trend_getir=cagrilmamali):
        r = istemci().post("/v1/icerik", headers=H,
                           json={**ICERIK, "anahtar_kelimeler": ["el yapımı"], "kalite_dahil": False})
    assert r.status_code == 200, r.text
    assert r.json()["anahtar_kelime_kaynagi"] == "istek" and r.json()["kalite"] is None


def test_dogrulama_hatasi_kota_harcamaz_ve_anlatimi_geri_yansitmaz():
    c = istemci(kota=1)
    gizli = "Adım Ayşe Yılmaz, telefonum 0555 000 00 00."
    r = c.post("/v1/icerik", headers=H, json={"anlatim": f"{gizli} {ANLATIM}", "kategori": "Bilinmeyen"})
    assert r.status_code == 422 and kod(r) == "gecersiz_istek"
    assert "Ayşe" not in r.text and "0555" not in r.text
    assert [a["alan"] for a in r.json()["hata"]["ayrintilar"]] == ["kategori"]
    r = c.post("/v1/icerik", headers=H, json={"anlatim": "   kısa   ", "kategori": "Gıda"})
    assert r.status_code == 422 and r.json()["hata"]["ayrintilar"][0]["alan"] == "anlatim"
    r = c.post("/v1/icerik", headers=H, json={**ICERIK, "bilinmeyen_alan": 1})
    assert r.status_code == 422
    with sahte_cekirdek():
        assert c.post("/v1/icerik", headers=H, json=ICERIK).status_code == 200   # kota duruyor


def test_gunluk_kota_dolunca_429():
    c = istemci(kota=2)
    with sahte_cekirdek():
        yanitlar = [c.post("/v1/icerik", headers=H, json=ICERIK) for _ in range(3)]
    assert [y.status_code for y in yanitlar] == [200, 200, 429]
    assert kod(yanitlar[-1]) == "kota_asildi" and int(yanitlar[-1].headers["Retry-After"]) > 0


def test_dakika_siniri_429():
    c = istemci()
    with sahte_cekirdek():
        yanitlar = [c.post("/v1/icerik", headers={"X-API-Key": ANAHTAR_HIZLI}, json=ICERIK)
                    for _ in range(3)]
    assert [y.status_code for y in yanitlar] == [200, 200, 429]
    assert kod(yanitlar[-1]) == "hiz_siniri" and "Retry-After" in yanitlar[-1].headers


def test_model_yogunken_503_ve_kota_iade_edilir():
    def yogun(**k):
        raise Exception("503 UNAVAILABLE")
    c = istemci(kota=1)
    with sahte_cekirdek(), yamala(uret, icerik_uret=yogun):
        r = c.post("/v1/icerik", headers=H, json=ICERIK)
    assert r.status_code == 503 and kod(r) == "model_yogun" and r.headers["Retry-After"] == "30"
    j = c.get("/v1/kullanim", headers=H).json()
    assert j["bugun_kullanilan"] == 0 and j["kalan"] == 1


def test_yapilandirma_hatasi_ic_ayrinti_sizdirmaz():
    def anahtarsiz(**k):
        raise RuntimeError("GEMINI_API_KEY bulunamadı. .env dosyasını oluşturun")
    with sahte_cekirdek(), yamala(uret, icerik_uret=anahtarsiz):
        r = istemci().post("/v1/icerik", headers=H, json=ICERIK)
    assert r.status_code == 500 and kod(r) == "yapilandirma_hatasi"
    assert "GEMINI" not in r.text and ".env" not in r.text


# ---------------------------------------------------------------- diğer uç noktalar
def test_format_hashtag_reels_ve_gecersiz_bicim():
    c, alinan = istemci(), {}

    def sahte_ek(**k):
        alinan.update(k)
        return "#elörgüsü #bebekbattaniyesi"
    with yamala(uret, ek_format_uret=sahte_ek, reels_uret=lambda **k: "**plan**"):
        r = c.post("/v1/format", headers=H, json={**ICERIK, "bicim": "hashtag"})
        assert r.status_code == 200 and r.json()["metin"] == "#elörgüsü #bebekbattaniyesi"
        assert alinan["bicim"] == "hashtag" and alinan["trends_kullan"] is True
        r = c.post("/v1/format", headers=H, json={**ICERIK, "bicim": "reels"})
        assert r.status_code == 200 and r.json()["metin"] == "**plan**"
    r = c.post("/v1/format", headers=H, json={**ICERIK, "bicim": "tiktok"})
    assert r.status_code == 422


def test_kalite_kotadan_dusmez_model_yoksa_503():
    c = istemci()
    govde = {"metin": "Anneannemden öğrendiğim desenle elde örüyorum.", "kategori": "Gıda"}
    with yamala(kalite, model_al=lambda: SahteKalite()):
        r = c.post("/v1/kalite", headers=H, json=govde)
    assert r.status_code == 200 and r.json()["hazir"] is True
    assert "hikaye_ipucu" in r.json()["oznitelikler"] and r.headers["X-Kota-Kalan"] == "3"
    with yamala(kalite, model_al=lambda: SahteKalite(mevcut=False)):
        r = c.post("/v1/kalite", headers=H, json=govde)
    assert r.status_code == 503 and kod(r) == "kalite_modeli_yok"


def test_anahtar_kelimeler():
    c = istemci()
    with yamala(trends, trend_getir=sahte_trend):
        r = c.get("/v1/anahtar-kelimeler", headers=H, params={"kategori": "Gıda", "adet": 3})
    assert r.status_code == 200 and r.json()["kaynak"] == "önbellek"
    assert c.get("/v1/anahtar-kelimeler", headers=H, params={"kategori": "Yok"}).status_code == 422


def test_transkript_riza_tur_boyut_ve_basari():
    c, alinan = istemci(kota=1), {}
    ses = b"RIFF" + b"\x00" * 100
    r = c.post("/v1/transkript", headers=H, files={"ses": ("a.wav", ses, "audio/wav")},
               data={"acik_riza": "false"})
    assert r.status_code == 400 and kod(r) == "riza_gerekli"
    r = c.post("/v1/transkript", headers=H, files={"ses": ("a.txt", b"x", "text/plain")},
               data={"acik_riza": "true"})
    assert r.status_code == 415
    with yamala(api, MAKS_SES_BAYT=50):
        r = c.post("/v1/transkript", headers=H, files={"ses": ("a.wav", ses, "audio/wav")},
                   data={"acik_riza": "true"})
    assert r.status_code == 413

    def sahte_ses(veri, tur):
        alinan.update(tur=tur, boyut=len(veri))
        return "Keçe patik yapıyorum."
    with yamala(uret, sesten_metne=sahte_ses):
        r = c.post("/v1/transkript", headers=H, files={"ses": ("a.mp3", ses, "audio/mpeg")},
                   data={"acik_riza": "true"})
    # rıza/tür/boyut hataları kotadan düşmedi: kota=1 ile başarılı çağrı yapılabildi
    assert r.status_code == 200, r.text
    assert r.json()["metin"] == "Keçe patik yapıyorum." and alinan == {"tur": "audio/mp3", "boyut": 104}


def test_takvim_ics_utc_donusumu_ve_kotadan_dusmez():
    c = istemci(kota=1)
    oge = {"zaman": "2026-09-17T20:00:00", "kanal": "instagram", "baslik": "Bebek battaniyesi",
           "metin": "Üç günümü alıyor."}
    r = c.post("/v1/takvim.ics", headers=H, json={"ogeler": [oge]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "DTSTART:20260917T170000Z" in r.text and "BEGIN:VEVENT" in r.text
    assert "attachment" in r.headers["content-disposition"] and r.headers["X-Kota-Kalan"] == "1"
    assert c.post("/v1/takvim.ics", headers=H, json={"ogeler": []}).status_code == 422
    assert c.post("/v1/takvim.ics", headers=H,
                  json={"ogeler": [{**oge, "kanal": "tiktok"}]}).status_code == 422


def test_kullanim():
    c = istemci(kota=5)
    with sahte_cekirdek():
        c.post("/v1/icerik", headers=H, json=ICERIK)
    j = c.get("/v1/kullanim", headers=H).json()
    assert (j["is_ortagi"], j["bugun_kullanilan"], j["kalan"]) == ("Deneme Kooperatifi", 1, 4)
    assert datetime.fromisoformat(j["sifirlanma"]).utcoffset().total_seconds() == 3 * 3600


# ---------------------------------------------------------------- güvenlik ve işletim
def test_gunlukte_anlatim_ve_anahtar_yer_almaz():
    kayitlar = []

    class Toplayici(logging.Handler):
        def emit(self, record):
            kayitlar.append(record.getMessage())
    toplayici = Toplayici()
    api.log.addHandler(toplayici)
    try:
        with sahte_cekirdek():
            istemci().post("/v1/icerik", headers=H, json=ICERIK)
    finally:
        api.log.removeHandler(toplayici)
    birlesik = "\n".join(kayitlar)
    assert "/v1/icerik 200" in birlesik and "Deneme Kooperatifi" in birlesik
    assert "battaniyesi" not in birlesik and ANAHTAR not in birlesik


def test_buyuk_govde_413():
    with yamala(api, MAKS_GOVDE_BAYT=100):
        r = istemci().post("/v1/icerik", headers={**H, "Content-Type": "application/json"},
                           content=json.dumps({**ICERIK, "anlatim": ANLATIM * 5}).encode())
    assert r.status_code == 413 and kod(r) == "istek_cok_buyuk"


def test_openapi_semasi_ve_kategori_tek_kaynak():
    r = istemci().get("/openapi.json")
    assert r.status_code == 200
    sema = r.json()
    kategori = sema["components"]["schemas"]["IcerikIstegi"]["properties"]["kategori"]
    assert kategori["enum"] == list(prompts.KATEGORI_KELIMELERI)
    assert "X-API-Key" in json.dumps(sema["components"]["securitySchemes"])


def test_anahtar_duz_metin_saklanmaz_bozuk_yapilandirma_reddedilir():
    a = guv.yeni_anahtar()
    assert a.startswith("uk_") and len(a) > 40 and a != guv.yeni_anahtar()
    assert guv.anahtarlari_yukle("") == {}
    for bozuk in ("[]", "{bozuk", json.dumps({"kisa": {"ad": "x"}}),
                  json.dumps({"a" * 64: {"ad": " "}}),
                  json.dumps({"a" * 64: {"ad": "x", "dakika_siniri": 0}})):
        try:
            guv.anahtarlari_yukle(bozuk)
            assert False, f"ValueError bekleniyordu: {bozuk}"
        except ValueError:
            pass


def test_sayac_kayan_pencere_gun_donumu_ve_maliyetsiz_istek():
    saat, an = [0.0], [datetime(2026, 9, 15, 23, 59, tzinfo=takvim.TR)]
    s = guv.Sayac(saat=lambda: saat[0], simdi=lambda: an[0])
    o = guv.IsOrtagi("x", gunluk_kota=2, dakika_siniri=2, anahtar_ozeti="a" * 64)
    assert s.dene(o).izin and s.dene(o).izin
    r = s.dene(o)
    assert not r.izin and r.neden == "dakika"
    saat[0] = 61.0
    r = s.dene(o)
    assert not r.izin and r.neden == "gunluk" and r.yeniden_dene_sn == 60
    an[0], saat[0] = datetime(2026, 9, 16, 0, 0, 1, tzinfo=takvim.TR), 130.0
    r = s.dene(o)
    assert r.izin and r.kalan == 1
    assert s.dene(o, maliyet=0).izin and s.kullanilan(o) == 1


def test_komut_satiri_anahtar_olusturur_ve_iptal_eder():
    with tempfile.TemporaryDirectory() as klasor:
        dosya = Path(klasor) / "anahtarlar.json"
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            guv.main(["yeni", "--ad", "Kooperatif A", "--kota", "50"], dosya=dosya)
        anahtar = next(s.strip() for s in cikti.getvalue().splitlines()
                       if s.strip().startswith("uk_"))
        icerik = dosya.read_text(encoding="utf-8")
        assert anahtar not in icerik and "Kooperatif A" in icerik
        ortak = guv.anahtarlari_yukle(icerik)[guv.anahtar_ozeti(anahtar)]
        assert (ortak.ad, ortak.gunluk_kota) == ("Kooperatif A", 50)
        with contextlib.redirect_stdout(io.StringIO()):
            guv.main(["sil", "--ad", "Kooperatif A"], dosya=dosya)
        assert json.loads(dosya.read_text(encoding="utf-8")) == {}


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
