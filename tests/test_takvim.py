# -*- coding: utf-8 -*-
"""
takvim.py testleri — API anahtarı ve internet gerektirmez.

    python -m pytest tests          (pytest kuruluysa)
    python tests/test_takvim.py     (pytest olmadan)
"""
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import takvim  # noqa: E402
from takvim import TR, PlanOgesi  # noqa: E402

# 15 Eylül 2026 Salı, 18:00 (Türkiye)
AN = datetime(2026, 9, 15, 18, 0, tzinfo=TR)


def _icerik(no: int) -> dict:
    return {"id": f"ic{no}", "tarih": "2026-09-15", "saat": "18:00",
            "kategori": "Gıda", "anlatim": f"Ürün {no}. Ayrıntı.",
            "instagram": f"ig {no}", "shopier": f"sh {no}", "ekler": {}}


def _ics_satirlari(ics: bytes) -> list[str]:
    """Katlanmış satırları açar (RFC 5545 unfolding)."""
    return ics.decode("utf-8").replace("\r\n ", "").split("\r\n")


# ---------------------------------------------------------------- planlama
def test_sonraki_zamanlar_secilen_gunlere_yerlesir():
    z = takvim.sonraki_zamanlar([1, 3, 5], time(20, 0), 3, baslangic=AN)
    assert [x.date() for x in z] == [date(2026, 9, 15), date(2026, 9, 17), date(2026, 9, 19)]
    assert all(x.hour == 20 and x.tzinfo is not None for x in z)


def test_hatirlatmasi_gecmiste_kalacak_saat_secilmez():
    # 19:45'te 20:00 seçilirse 30 dk'lık hatırlatma geçmişte kalır → sıradaki Perşembe
    z = takvim.sonraki_zamanlar([1, 3], time(20, 0), 1,
                                baslangic=datetime(2026, 9, 15, 19, 45, tzinfo=TR))
    assert z[0].date() == date(2026, 9, 17)


def test_dolu_gune_ikinci_gonderi_konmaz():
    z = takvim.sonraki_zamanlar([1, 3], time(20, 0), 2, baslangic=AN,
                                dolu_gunler={date(2026, 9, 15)})
    assert [x.date() for x in z] == [date(2026, 9, 17), date(2026, 9, 22)]


def test_bos_gun_listesi_hata_verir():
    try:
        takvim.sonraki_zamanlar([], time(20, 0), 1, baslangic=AN)
        assert False, "ValueError bekleniyordu"
    except ValueError:
        pass


def test_sunucu_utc_olsa_da_turkiye_saati_kullanilir():
    # UTC 21:30 = TR 00:30 (ertesi gün). Gün hesabı TR'ye göre yapılmalı.
    utc = datetime(2026, 9, 15, 21, 30, tzinfo=timezone.utc)
    z = takvim.sonraki_zamanlar([2], time(20, 0), 1, baslangic=utc)
    assert z[0].date() == date(2026, 9, 16) and z[0].utcoffset() == timedelta(hours=3)


def test_plan_oner_en_eski_icerigi_once_ve_yalniz_planlanmamislari_yerlestirir():
    icerikler = [_icerik(3), _icerik(2), _icerik(1)]          # arayüz sırası: en yeni başta
    mevcut = [PlanOgesi(zaman=datetime(2026, 9, 15, 20, tzinfo=TR).isoformat(),
                        kanal="instagram", baslik="x", icerik_id="ic2")]
    yeni = takvim.plan_oner(icerikler, mevcut, [1, 3, 5], time(20, 0), baslangic=AN)
    assert [o.icerik_id for o in yeni] == ["ic1", "ic3"]
    # 15 Eylül dolu olduğu için ilk öneri Perşembe
    assert [o.zaman_dt().date() for o in yeni] == [date(2026, 9, 17), date(2026, 9, 19)]
    assert yeni[0].metin == "ig 1" and yeni[0].baslik == "Ürün 1"


def test_ayir_ve_siradaki():
    p = [PlanOgesi(zaman=(AN - timedelta(days=1)).isoformat(), kanal="instagram", baslik="gecen"),
         PlanOgesi(zaman=(AN + timedelta(days=2)).isoformat(), kanal="story", baslik="sonra"),
         PlanOgesi(zaman=(AN + timedelta(hours=1)).isoformat(), kanal="instagram", baslik="yakin"),
         PlanOgesi(zaman=(AN + timedelta(days=9)).isoformat(), kanal="instagram", baslik="uzak"),
         PlanOgesi(zaman=(AN - timedelta(days=2)).isoformat(), kanal="instagram", baslik="ok",
                   tamam=True)]
    g = takvim.ayir(p, AN)
    assert [o.baslik for o in g["yaklasan"]] == ["yakin", "sonra", "uzak"]
    assert [o.baslik for o in g["gecen"]] == ["gecen"]
    assert [o.baslik for o in g["tamam"]] == ["ok"]
    assert takvim.siradaki(p, AN).baslik == "yakin"
    assert [o.baslik for o in takvim.onumuzdeki_gunler(p, 7, AN)] == ["yakin", "sonra"]


def test_tarih_etiketi_ve_baslik():
    assert takvim.tarih_etiketi(AN, AN.date()) == "Bugün · 15 Eylül Salı"
    assert takvim.tarih_etiketi(AN + timedelta(days=1), AN.date()) == "Yarın · 16 Eylül Çarşamba"
    assert takvim.kisa_etiket(AN + timedelta(hours=2), AN.date()) == "Bugün 20:00"
    assert takvim.kisa_etiket(AN + timedelta(days=2), AN.date()) == "17 Eyl 18:00"
    assert takvim.baslik_uret("El örgüsü bebek battaniyesi yapıyorum. Organik pamuk.") == \
        "El örgüsü bebek battaniyesi yapıyorum"
    uzun = takvim.baslik_uret("kelime " * 30)
    assert len(uzun) <= 49 and uzun.endswith("…")


# ---------------------------------------------------------------- .ics
def test_ics_gecerli_yapi_utc_zaman_ve_hatirlatma():
    o = PlanOgesi(zaman=datetime(2026, 9, 17, 20, 0, tzinfo=TR).isoformat(),
                  kanal="instagram", baslik="Bebek battaniyesi", metin="Üç günümü alıyor.",
                  id="abc123")
    ics = takvim.ics_olustur([o], olusturma=AN)
    satirlar = _ics_satirlari(ics)
    assert satirlar[0] == "BEGIN:VCALENDAR" and satirlar[-2] == "END:VCALENDAR"
    assert "DTSTART:20260917T170000Z" in satirlar            # TR 20:00 = UTC 17:00
    assert "DTEND:20260917T171500Z" in satirlar
    assert "TRIGGER:-PT30M" in satirlar
    assert "UID:abc123@uretken-kadin" in satirlar
    assert satirlar.count("BEGIN:VEVENT") == satirlar.count("END:VEVENT") == 1


def test_ics_ozel_karakterler_kacislanir_ve_uzun_satirlar_katlanir():
    metin = "Satır 1, virgül; noktalı\nSatır 2 \\ ters bölü " + "ğüşıöç🧶 " * 40
    o = PlanOgesi(zaman=AN.isoformat(), kanal="story", baslik="Başlık, virgüllü",
                  metin=metin)
    ics = takvim.ics_olustur([o], olusturma=AN)
    ham = ics.decode("utf-8")
    # Her fiziksel satır en fazla 75 bayt (UTF-8 harfler bölünmeden)
    assert all(len(s.encode("utf-8")) <= 75 for s in ham.split("\r\n"))
    aciklama = next(s for s in _ics_satirlari(ics) if s.startswith("DESCRIPTION:Satır"))
    assert "Satır 1\\, virgül\\; noktalı\\nSatır 2 \\\\ ters bölü" in aciklama
    assert "ğüşıöç🧶" in aciklama
    assert "SUMMARY:🟣 Instagram hikâyesi: Başlık\\, virgüllü" in _ics_satirlari(ics)


# ---------------------------------------------------------------- kaydet / yükle
def test_disa_ve_ice_aktarma_kayipsiz():
    icerikler = [{**_icerik(1), "ekler": {"hashtag": "#a #b"}}]
    plan = [PlanOgesi(zaman=AN.isoformat(), kanal="whatsapp", baslik="b", metin="m",
                      icerik_id="ic1", tamam=True, id="p1")]
    dosya = takvim.disa_aktar(icerikler, plan, ["benim üslubum"], an=AN)
    ic, pl, us, uy = takvim.ice_aktar(dosya.encode("utf-8"))
    assert ic == icerikler and pl == plan and us == ["benim üslubum"] and uy == []


def test_yabanci_ve_yeni_surum_dosyalari_reddedilir():
    for bozuk in (b"merhaba", json.dumps({"uygulama": "baska"}).encode(),
                  json.dumps({"uygulama": "uretken-kadin", "surum": 99}).encode(),
                  json.dumps(["liste"]).encode(), b"\xff\xfe\x00"):
        try:
            takvim.ice_aktar(bozuk)
            assert False, f"ValueError bekleniyordu: {bozuk[:20]!r}"
        except ValueError:
            pass


def test_bozuk_kayitlar_atlanir_ve_kimlikler_temizlenir():
    veri = {"uygulama": "uretken-kadin", "surum": 1,
            "icerikler": [{"id": "<script>", "instagram": "ig", "anlatim": 5},
                          {"instagram": ""}, "metin"],
            "plan": [{"zaman": "2026-09-17T20:00:00", "kanal": "instagram", "baslik": "x",
                      "tamam": "evet", "id": "iyi_id"},
                     {"zaman": "dun", "kanal": "instagram"},
                     {"zaman": "2026-09-17T20:00:00+03:00", "kanal": "tiktok"},
                     None],
            "uslup_ornekleri": ["a", 3, "", "b", "c", "d"]}
    ic, pl, us, uy = takvim.ice_aktar(json.dumps(veri))
    assert len(ic) == 1 and ic[0]["id"] != "<script>" and ic[0]["anlatim"] == ""
    assert len(pl) == 1 and pl[0].id == "iyi_id" and pl[0].tamam is False
    assert pl[0].zaman_dt().utcoffset() == timedelta(hours=3)   # saat dilimi yoksa TR
    assert us == ["a", "b", "c"]
    assert uy == ["5 kayıt okunamadı ve atlandı."]


def test_birlestir_ayni_dosya_iki_kez_yuklenince_cift_kayit_olmaz():
    a = [_icerik(1)]
    birlesik, eklenen = takvim.birlestir(a, [_icerik(1), _icerik(2)])
    assert [k["id"] for k in birlesik] == ["ic1", "ic2"] and eklenen == 1
    p = [PlanOgesi(zaman=AN.isoformat(), kanal="instagram", baslik="x", id="p1")]
    _, eklenen = takvim.birlestir(p, list(p))
    assert eklenen == 0


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
