# -*- coding: utf-8 -*-
"""
hesap.py testleri — geçici SQLite veritabanıyla; internet ve Neon gerektirmez.

    python tests/test_hesap.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import sqlalchemy as sa  # noqa: E402

import hesap  # noqa: E402
import takvim  # noqa: E402

_KLASOR = tempfile.mkdtemp(prefix="uk_hesap_test_")
SIFRE = "Yumak2026!"


def yeni_motor(ad: str) -> sa.Engine:
    return hesap._motor(f"sqlite:///{(Path(_KLASOR) / f'{ad}.db').as_posix()}")


def _hata(fonk, *arg, icerir: str = "", **kw) -> str:
    try:
        fonk(*arg, **kw)
    except ValueError as e:
        assert icerir in str(e), f"{icerir!r} beklenirken: {e}"
        return str(e)
    raise AssertionError("ValueError bekleniyordu")


def _kayit(m, eposta="ayse@ornek.com", ad="Ayşe"):
    return hesap.kayit_ol(eposta, ad, SIFRE, SIFRE, True, m=m)


# ---------------------------------------------------------------- şifre ve doğrulama
def test_sifre_ozeti_duz_metin_icermez_ve_tuzludur():
    a, b = hesap.sifre_ozeti(SIFRE), hesap.sifre_ozeti(SIFRE)
    assert a != b and SIFRE not in a and a.startswith("scrypt$16384$8$1$")
    assert hesap.sifre_dogru_mu(SIFRE, a) and not hesap.sifre_dogru_mu("yanlis-sifre", a)
    for bozuk in ("", "bcrypt$x", "scrypt$1$2$3$zz$yy", None):
        assert hesap.sifre_dogru_mu(SIFRE, bozuk) is False


def test_eposta_ve_sifre_kurallari():
    assert hesap.eposta_duzelt("  Ayse.Yilmaz@Ornek.COM ") == "ayse.yilmaz@ornek.com"
    for bozuk in ("ayse", "ayse@", "@ornek.com", "ayse@ornek", "a b@ornek.com"):
        _hata(hesap.eposta_duzelt, bozuk, icerir="e-posta")
    _hata(hesap.sifre_kontrol, "kisa1", icerir="en az 8")
    _hata(hesap.sifre_kontrol, "12345678", icerir="kolay tahmin")
    _hata(hesap.sifre_kontrol, "aaaaaaaaab", icerir="kolay tahmin")
    _hata(hesap.sifre_kontrol, "ayseyilmaz", "ayseyilmaz@ornek.com", icerir="e-posta")
    hesap.sifre_kontrol(SIFRE, "ayse@ornek.com")


def test_db_adresi_postgres_donusumu(monkeypatch=None):
    eski = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = "postgres://k:s@ep-ornek.eu-central-1.aws.neon.tech/uk?sslmode=require"
        assert hesap.db_adresi().startswith("postgresql+psycopg://k:s@ep-ornek")
        assert hesap.kalici_mi() is True
    finally:
        if eski is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = eski


# ---------------------------------------------------------------- kayıt ve giriş
def test_kayit_ve_giris():
    m = yeni_motor("kayit")
    k = _kayit(m, eposta="Ayse@Ornek.com")
    assert k.eposta == "ayse@ornek.com" and k.ad == "Ayşe" and len(k.id) == 32
    assert hesap.giris_yap("AYSE@ornek.com", SIFRE, m=m).id == k.id
    _hata(_kayit, m, eposta="ayse@ORNEK.com", icerir="zaten var")
    _hata(hesap.kayit_ol, "fatma@ornek.com", "Fatma", SIFRE, SIFRE, False, m=m, icerir="aydınlatma")
    _hata(hesap.kayit_ol, "fatma@ornek.com", "Fatma", SIFRE, SIFRE + "x", True, m=m, icerir="tutmuyor")
    _hata(hesap.kayit_ol, "fatma@ornek.com", " F ", SIFRE, SIFRE, True, m=m, icerir="Adınızı")
    with m.connect() as b:
        kayitli = b.execute(sa.select(hesap.kullanicilar.c.sifre_ozeti)).scalar_one()
    assert SIFRE not in kayitli


def test_yanlis_sifre_ve_olmayan_hesap_ayni_mesaji_verir():
    m = yeni_motor("mesaj")
    _kayit(m)
    a = _hata(hesap.giris_yap, "ayse@ornek.com", "yanlis-sifre", m=m)
    b = _hata(hesap.giris_yap, "yok@ornek.com", SIFRE, m=m)
    c = _hata(hesap.giris_yap, "gecersiz-eposta", SIFRE, m=m)
    assert a == b == c == hesap.GENEL_GIRIS_HATASI


def test_bes_hatali_denemeden_sonra_kilit_ve_kilidin_acilmasi():
    m = yeni_motor("kilit")
    k = _kayit(m)
    for _ in range(hesap.MAKS_DENEME - 1):
        _hata(hesap.giris_yap, "ayse@ornek.com", "yanlis", m=m, icerir="hatalı")
    _hata(hesap.giris_yap, "ayse@ornek.com", "yanlis", m=m, icerir="dakika sonra")
    _hata(hesap.giris_yap, "ayse@ornek.com", SIFRE, m=m, icerir="dakika sonra")     # doğru şifre de bekler
    with m.begin() as b:                                                             # kilit süresi geçti
        b.execute(hesap.kullanicilar.update().values(
            kilit_bitis=datetime.now(timezone.utc) - timedelta(minutes=1)))
    assert hesap.giris_yap("ayse@ornek.com", SIFRE, m=m).id == k.id
    with m.connect() as b:
        satir = b.execute(sa.select(hesap.kullanicilar)).mappings().first()
    assert satir["hatali_deneme"] == 0 and satir["kilit_bitis"] is None and satir["son_giris"] is not None


def test_basarili_giris_sayaci_sifirlar():
    m = yeni_motor("sayac")
    _kayit(m)
    for _ in range(3):
        _hata(hesap.giris_yap, "ayse@ornek.com", "yanlis", m=m)
    hesap.giris_yap("ayse@ornek.com", SIFRE, m=m)
    for _ in range(hesap.MAKS_DENEME - 1):                      # sayaç sıfırlandığı için 4 hatada kilit yok
        _hata(hesap.giris_yap, "ayse@ornek.com", "yanlis", m=m, icerir="hatalı")


# ---------------------------------------------------------------- veriler
def _icerik(no):
    return {"id": f"ic{no}", "tarih": "2026-09-16", "saat": "10:00", "kategori": "Gıda",
            "anlatim": f"Salça {no} yapıyorum.", "instagram": f"ig {no}", "shopier": f"sh {no}",
            "ekler": {"hashtag": "#salça"}, "fiyat": 180.0 + no}


def test_veriler_kaydedilir_yuklenir_ve_kullanicilar_ayridir():
    m = yeni_motor("veri")
    ayse, fatma = _kayit(m), _kayit(m, eposta="fatma@ornek.com", ad="Fatma")
    plan = [takvim.PlanOgesi(zaman="2026-09-20T20:00:00+03:00", kanal="instagram", baslik="Salça",
                             metin="ig 1", icerik_id="ic1", id="p1")]
    hesap.verileri_kaydet(ayse.id, hesap.belge([_icerik(1), _icerik(2)], plan, ["benim üslubum"]), m=m)
    icerikler, yuklu_plan, uslup = hesap.verileri_yukle(ayse.id, m=m)
    assert [k["id"] for k in icerikler] == ["ic1", "ic2"] and icerikler[0]["fiyat"] == 181.0
    assert yuklu_plan == plan and uslup == ["benim üslubum"]
    assert hesap.verileri_yukle(fatma.id, m=m) == ([], [], [])                     # başkasının verisi görünmez
    hesap.verileri_kaydet(ayse.id, hesap.belge([_icerik(3)], [], None), m=m)       # güncelleme (upsert)
    assert [k["id"] for k in hesap.verileri_yukle(ayse.id, m=m)[0]] == ["ic3"]
    _hata(hesap.verileri_kaydet, ayse.id, "x" * (takvim.MAKS_DOSYA_BAYT + 1), m=m, icerir="çok büyük")


def test_degisiklik_ozeti_zamandan_bagimsiz():
    a = hesap.degisiklik_ozeti([_icerik(1)], [], None)
    assert a == hesap.degisiklik_ozeti([_icerik(1)], [], None)
    assert a != hesap.degisiklik_ozeti([_icerik(1)], [], ["yeni üslup"])
    assert a != hesap.degisiklik_ozeti([{**_icerik(1), "instagram": "düzeltildi"}], [], None)


# ---------------------------------------------------------------- şifre değiştirme, geçici şifre, silme
def test_sifre_degistirme():
    m = yeni_motor("degistir")
    k = _kayit(m)
    _hata(hesap.sifre_degistir, k.id, "yanlis", "YeniSifre42", "YeniSifre42", m=m, icerir="Mevcut şifreniz")
    _hata(hesap.sifre_degistir, k.id, SIFRE, "YeniSifre42", "Baska42xx", m=m, icerir="tutmuyor")
    hesap.sifre_degistir(k.id, SIFRE, "YeniSifre42", "YeniSifre42", m=m)
    _hata(hesap.giris_yap, "ayse@ornek.com", SIFRE, m=m)
    assert hesap.giris_yap("ayse@ornek.com", "YeniSifre42", m=m).id == k.id


def test_gecici_sifre_kilidi_acar():
    m = yeni_motor("gecici")
    k = _kayit(m)
    for _ in range(hesap.MAKS_DENEME):
        _hata(hesap.giris_yap, "ayse@ornek.com", "yanlis", m=m)
    gecici = hesap.gecici_sifre_ata("AYSE@ornek.com", m=m)
    assert len(gecici) >= 12 and hesap.giris_yap("ayse@ornek.com", gecici, m=m).id == k.id
    _hata(hesap.gecici_sifre_ata, "yok@ornek.com", m=m, icerir="kayıtlı hesap yok")


def test_hesap_silme_tum_verileri_kaldirir():
    m = yeni_motor("silme")
    ayse, fatma = _kayit(m), _kayit(m, eposta="fatma@ornek.com", ad="Fatma")
    hesap.verileri_kaydet(ayse.id, hesap.belge([_icerik(1)], [], None), m=m)
    hesap.verileri_kaydet(fatma.id, hesap.belge([_icerik(2)], [], None), m=m)
    _hata(hesap.hesabi_sil, ayse.id, "yanlis", m=m, icerir="Mevcut şifreniz")
    hesap.hesabi_sil(ayse.id, SIFRE, m=m)
    _hata(hesap.giris_yap, "ayse@ornek.com", SIFRE, m=m)
    assert hesap.verileri_yukle(ayse.id, m=m) == ([], [], [])
    assert hesap.kullanici_sayisi(m=m) == 1 and hesap.verileri_yukle(fatma.id, m=m)[0][0]["id"] == "ic2"
    _kayit(m)                                                                      # aynı e-postayla yeniden kayıt olunabilir


# ---------------------------------------------------------------- beni hatırla (oturum jetonları)
def test_oturum_jetonu_ozeti_saklanir_suresi_ve_iptali():
    m = yeni_motor("oturum")
    k = _kayit(m)
    jeton = hesap.oturum_ac(k.id, hatirla=True, m=m)
    with m.connect() as b:
        ozetler = b.execute(sa.select(hesap.oturumlar.c.ozet)).scalars().all()
    assert jeton not in ozetler and len(ozetler) == 1                               # jetonun kendisi saklanmaz
    assert hesap.oturum_dogrula(jeton, m=m).id == k.id
    for gecersiz in (None, "", "uydurma-jeton", "x" * 500):
        assert hesap.oturum_dogrula(gecersiz, m=m) is None

    kisa = hesap.oturum_ac(k.id, hatirla=False, m=m)
    with m.begin() as b:                                                             # kısa oturumun süresi doldu
        b.execute(hesap.oturumlar.update().where(hesap.oturumlar.c.ozet == hesap._jeton_ozeti(kisa))
                  .values(son_kullanma=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert hesap.oturum_dogrula(kisa, m=m) is None and hesap.oturum_dogrula(jeton, m=m) is not None

    hesap.oturum_kapat(jeton, m=m)
    assert hesap.oturum_dogrula(jeton, m=m) is None


def test_sifre_degisince_diger_oturumlar_ve_silmede_hepsi_kapanir():
    m = yeni_motor("oturum_iptal")
    k = _kayit(m)
    bu_cihaz, diger = hesap.oturum_ac(k.id, m=m), hesap.oturum_ac(k.id, m=m)
    hesap.diger_oturumlari_kapat(k.id, bu_cihaz, m=m)
    assert hesap.oturum_dogrula(bu_cihaz, m=m) and hesap.oturum_dogrula(diger, m=m) is None
    gecici = hesap.gecici_sifre_ata("ayse@ornek.com", m=m)                           # geçici şifre de kapatır
    assert hesap.oturum_dogrula(bu_cihaz, m=m) is None
    son = hesap.oturum_ac(k.id, m=m)
    hesap.hesabi_sil(k.id, gecici, m=m)
    assert hesap.oturum_dogrula(son, m=m) is None


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
