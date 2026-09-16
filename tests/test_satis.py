# -*- coding: utf-8 -*-
"""
satis.py testleri — Gemini'ye istek atmaz (sahte istemci), internet gerektirmez.

    python tests/test_satis.py
"""
import json
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import satis  # noqa: E402
from satis import FiyatGirdisi  # noqa: E402
from takvim import TR  # noqa: E402


class _Yanit:
    def __init__(self, metin):
        self.text = metin


class SahteIstemci:
    """uret._modelle_uret'in çağırdığı client.models.generate_content arayüzü."""
    def __init__(self, yanit):
        self.yanit, self.promptlar = yanit, []
        self.models = self

    def generate_content(self, model, contents, config=None):
        self.promptlar.append((contents, config))
        return _Yanit(self.yanit if isinstance(self.yanit, str) else json.dumps(self.yanit, ensure_ascii=False))


ANLATIM = "El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, tamamen elde örüyorum."


def _hata_bekle(fonk, *arg, **kw):
    try:
        fonk(*arg, **kw)
    except ValueError:
        return
    raise AssertionError("ValueError bekleniyordu")


# ---------------------------------------------------------------- fiyat
def test_fiyat_formulu_ve_yuvarlama():
    g = FiyatGirdisi(malzeme=150, emek_saat=6, saat_ucreti=50, ambalaj=20, komisyon_yuzde=10, kar_yuzde=20)
    d = satis.fiyat_oner(g)
    # maliyet 470 · hedef 564 · ham 564 / 0,9 = 626,67 → 5'in katına yukarı: 630
    assert d.satis_fiyati == 630
    assert (d.komisyon, d.eline_gecen, d.emek_karsiligi, d.malzeme_ambalaj) == (63, 567, 300, 170)
    assert d.kar == 97 and d.gercek_saatlik == round(397 / 6, 2)
    assert satis.fiyat_oner(FiyatGirdisi(150, 6, 50, 20, 0, 10, 20, yuvarlama=0)).satis_fiyati == 626.67


def test_tam_kat_fiyat_yukari_kaymaz_ve_kargo_eklenir():
    # maliyet 100, kâr 0, komisyon 0 → tam 100; kayan nokta hatasıyla 105 olmamalı
    assert satis.fiyat_oner(FiyatGirdisi(60, 2, 20, kar_yuzde=0)).satis_fiyati == 100
    d = satis.fiyat_oner(FiyatGirdisi(60, 2, 20, kargo=45, kar_yuzde=0))
    assert d.satis_fiyati == 145 and d.eline_gecen == 100


def test_mevcut_fiyat_kontrolu_dusuk_fiyati_gosterir():
    g = FiyatGirdisi(malzeme=150, emek_saat=6, saat_ucreti=50, ambalaj=20, komisyon_yuzde=10)
    d = satis.dokum(g, 400)
    assert d.gercek_saatlik == round((360 - 170) / 6, 2) and d.gercek_saatlik < g.saat_ucreti
    assert d.kar < 0


def test_gecersiz_fiyat_girdileri():
    _hata_bekle(satis.fiyat_oner, FiyatGirdisi(10, 1, 10, komisyon_yuzde=100))
    _hata_bekle(satis.fiyat_oner, FiyatGirdisi(-5, 1, 10))
    _hata_bekle(satis.fiyat_oner, FiyatGirdisi(float("nan"), 1, 10))
    _hata_bekle(satis.dokum, FiyatGirdisi(10, 1, 10), -1)
    assert satis.fiyat_oner(FiyatGirdisi(10, 0, 0)).gercek_saatlik is None


# ---------------------------------------------------------------- müşteriye cevap
def test_hazir_cevaplarda_uydurma_bilgi_yok_yer_tutucu_var():
    for ad, metin in satis.HAZIR_CEVAPLAR.items():
        assert "TL" not in metin.replace("[fiyat] TL", "") or "[" in metin, ad
    assert satis.yer_tutucular(satis.HAZIR_CEVAPLAR["🚚 Kargo süresi"]) == [
        "hazırlık süresi", "kargo firması", "teslimat süresi"]


def test_musteri_cevabi_sahte_istemci_ve_kurallar():
    c = SahteIstemci({"cevap": "Merhaba 🌸 Fiyatı [fiyat] TL, [kargo süresi] içinde gönderiyorum."})
    cevap = satis.musteri_cevabi_uret("Merhaba fiyatı ne kadar?", ANLATIM, client=c)
    assert "[fiyat]" in cevap
    prompt, config = c.promptlar[0]
    assert "UYDURMA" in prompt and "Merhaba fiyatı ne kadar?" in prompt and "organik pamuk" in prompt.lower()
    assert config.response_mime_type == "application/json"
    _hata_bekle(satis.musteri_cevabi_uret, "  ", client=c)
    _hata_bekle(satis.musteri_cevabi_uret, "Selam, ne zaman gelir?", client=SahteIstemci({"cevap": ""}))


# ---------------------------------------------------------------- pazaryeri
def test_etiket_denetle_turkce_ve_ingilizce_iddialar():
    kalan, cikan = satis.etiket_denetle(
        ["organic cotton baby blanket", "natural wool", "miracle gift", "#elörgüsü", "şifalı battaniye",
         "  ", "Organic Cotton Baby Blanket"], ANLATIM)
    assert kalan == ["organic cotton baby blanket", "elörgüsü", "Organic Cotton Baby Blanket"]
    assert cikan == ["natural wool", "miracle gift", "şifalı battaniye"]


def test_etsy_ilani_sinirlari_uygulanir():
    uzun_baslik = "Handmade organic cotton baby blanket " * 6
    etiketler = [f"baby gift {i}" for i in range(14)] + ["a very long tag over twenty chars", "natural linen"]
    c = SahteIstemci({"baslik": uzun_baslik, "ozellikler": ["Material: organic cotton yarn"],
                      "aciklama": "Hand knitted.", "etiketler": etiketler, "eksik_bilgiler": ["ölçü"]})
    ilan = satis.pazaryeri_ilani_uret(ANLATIM, "Tekstil / El sanatı", "🌍 Etsy (İngilizce)", client=c)
    assert len(ilan.baslik) <= satis.ETSY_BASLIK and not ilan.baslik.endswith(" ")
    assert len(ilan.etiketler) == 13 and all(len(e) <= 20 for e in ilan.etiketler)
    assert "a very long tag over twenty chars" in ilan.cikarilan_etiketler
    assert "natural linen" in ilan.cikarilan_etiketler            # anlatımda keten/doğal yok
    assert ilan.eksik_bilgiler == ["ölçü"]
    assert "İNGİLİZCE" in c.promptlar[0][0]


def test_trendyol_ilani_ve_hatalar():
    c = SahteIstemci({"baslik": "El Örgüsü Organik Pamuk Bebek Battaniyesi " * 4, "ozellikler": [],
                      "aciklama": "Elde örülür.", "etiketler": ["bebek battaniyesi"], "eksik_bilgiler": []})
    ilan = satis.pazaryeri_ilani_uret(ANLATIM, "Tekstil / El sanatı", "🟠 Trendyol", client=c)
    assert len(ilan.baslik) <= satis.TR_BASLIK and "TÜRKÇE" in c.promptlar[0][0]
    assert "el yapımı" in c.promptlar[0][0]                        # kategori anahtar kelimeleri
    _hata_bekle(satis.pazaryeri_ilani_uret, ANLATIM, "Gıda", "Amazon", client=c)
    _hata_bekle(satis.pazaryeri_ilani_uret, "kısa", "Gıda", "🟠 Trendyol", client=c)
    bos = SahteIstemci({"baslik": "", "aciklama": ""})
    _hata_bekle(satis.pazaryeri_ilani_uret, ANLATIM, "Gıda", "🟠 Trendyol", client=bos)


def test_json_kod_blogu_icinde_gelse_de_okunur():
    c = SahteIstemci('```json\n{"cevap": "Merhaba [fiyat]"}\n```')
    assert satis.musteri_cevabi_uret("Fiyat nedir?", client=c) == "Merhaba [fiyat]"


# ---------------------------------------------------------------- özel günler
def test_yaklasan_ozel_gunler_dogru_tarihler_ve_sira():
    gunler = satis.yaklasan_ozel_gunler(date(2026, 9, 16))
    assert [(g.ad, g.tarih) for g in gunler] == [
        ("Öğretmenler Günü", date(2026, 11, 24)), ("Kasım indirim dönemi", date(2026, 11, 27)),
        ("Yılbaşı", date(2027, 1, 1)), ("Sevgililer Günü", date(2027, 2, 14)),
        ("Dünya Kadınlar Günü", date(2027, 3, 8)), ("Anneler Günü", date(2027, 5, 9)),
        ("Babalar Günü", date(2027, 6, 20)), ("Okulların açılışı", date(2027, 9, 13))]
    assert gunler[-1].yaklasik is True


def test_kasim_indirimi_ayin_bir_cuma_basladigi_yilda():
    # 2024'te 1 Kasım Cuma: dördüncü Perşembe 28 Kasım → 29 Kasım
    kasim = [g for g in satis._yilin_ozel_gunleri(2024) if g.ad == "Kasım indirim dönemi"][0]
    assert kasim.tarih == date(2024, 11, 29)


def test_kampanya_plani_gecmis_hatirlatmalari_atlar():
    gun = satis.OzelGun("Öğretmenler Günü", date(2026, 11, 24), "")
    an = datetime(2026, 11, 18, 9, 0, tzinfo=TR)                   # 10 gün öncesi geçti
    plan = satis.kampanya_plani(gun, "öneri", icerik_id="k1", an=an)
    assert [o.zaman_dt().date() for o in plan] == [date(2026, 11, 21), date(2026, 11, 24)]
    assert all(o.zaman_dt().time() == time(20, 0) and o.icerik_id == "k1" for o in plan)
    assert plan[0].baslik == "Öğretmenler Günü · hatırlatma"


def test_kampanya_onerisi_prompt_kalan_gun_ve_kurallar():
    c = SahteIstemci("**🎯 Kampanya fikri**\nDeneme")
    gun = satis.OzelGun("Anneler Günü", date(2027, 5, 9), "")
    metin = satis.kampanya_onerisi_uret(gun, ANLATIM, "Tekstil / El sanatı", bugun=date(2027, 4, 29), client=c)
    assert metin.startswith("**🎯")
    prompt = c.promptlar[0][0]
    assert "10 gün kaldı" in prompt and "9 Mayıs 2027, Pazar" in prompt and "uydurma indirim" in prompt


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
