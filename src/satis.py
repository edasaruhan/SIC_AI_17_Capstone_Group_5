# -*- coding: utf-8 -*-
"""
Üretken Kadın — satış araçları

  • Fiyat hesaplayıcı : emeği de sayan, komisyonu ve kargoyu içeren şeffaf formül (yapay zekâ yok)
  • Müşteriye cevap   : hazır cevap şablonları (yapay zekâ yok) + mesaja özel cevap taslağı (Gemini)
  • Pazaryeri ilanı   : Trendyol / Hepsiburada / Etsy (İngilizce) biçiminde ilan + çeviri (Gemini)
  • Özel günler       : kurala göre hesaplanan günler (yapay zekâ yok) + kampanya önerisi (Gemini)

Komisyon ve vergi oranları bilerek koda gömülmedi: platformlar oranları sık değiştirir ve
kategoriye göre farklıdır; kullanıcı kendi sözleşmesindeki oranı girer.
Yapay zekâ kullanmayan kısımlar internete bağımlı değildir (tests/test_satis.py).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import prompts
import takvim
import uret


# ---------------------------------------------------------------------------
# Fiyat hesaplayıcı
# ---------------------------------------------------------------------------
@dataclass
class FiyatGirdisi:
    malzeme: float                 # bir ürünün malzeme maliyeti (TL)
    emek_saat: float               # bir ürüne harcanan süre (saat)
    saat_ucreti: float             # emeğinize biçtiğiniz saatlik ücret (TL)
    ambalaj: float = 0.0           # kutu, etiket, kurdele (TL)
    kargo: float = 0.0             # kargoyu siz ödüyorsanız (TL); alıcı ödüyorsa 0
    komisyon_yuzde: float = 0.0    # platform + ödeme komisyonu toplamı (%)
    kar_yuzde: float = 20.0        # maliyetin üstüne eklenecek kâr (%)
    yuvarlama: int = 5             # fiyat bu tutarın katına yukarı yuvarlanır (0: yuvarlanmaz)


@dataclass
class FiyatDokumu:
    satis_fiyati: float
    malzeme_ambalaj: float
    emek_karsiligi: float
    komisyon: float
    kargo: float
    kar: float                     # emek karşılığı ödendikten sonra kalan
    eline_gecen: float             # satış fiyatı − komisyon − kargo
    gercek_saatlik: float | None   # (eline geçen − malzeme − ambalaj) / emek saati


def _dogrula(g: FiyatGirdisi) -> None:
    alanlar = {"Malzeme": g.malzeme, "Emek süresi": g.emek_saat, "Saatlik ücret": g.saat_ucreti,
               "Ambalaj": g.ambalaj, "Kargo": g.kargo, "Komisyon": g.komisyon_yuzde,
               "Kâr oranı": g.kar_yuzde}
    for ad, deger in alanlar.items():
        if deger is None or not math.isfinite(deger) or deger < 0:
            raise ValueError(f"{ad} 0 ya da daha büyük bir sayı olmalı.")
    if g.komisyon_yuzde >= 100:
        raise ValueError("Komisyon %100'den küçük olmalı.")


def dokum(g: FiyatGirdisi, satis_fiyati: float) -> FiyatDokumu:
    """Verilen satış fiyatında paranın nereye gittiğini hesaplar (mevcut fiyatı kontrol için)."""
    _dogrula(g)
    if satis_fiyati is None or not math.isfinite(satis_fiyati) or satis_fiyati < 0:
        raise ValueError("Satış fiyatı 0 ya da daha büyük olmalı.")
    malzeme_ambalaj = g.malzeme + g.ambalaj
    emek = g.emek_saat * g.saat_ucreti
    komisyon = satis_fiyati * g.komisyon_yuzde / 100
    eline_gecen = satis_fiyati - komisyon - g.kargo
    saatlik = (eline_gecen - malzeme_ambalaj) / g.emek_saat if g.emek_saat > 0 else None
    return FiyatDokumu(
        satis_fiyati=round(satis_fiyati, 2), malzeme_ambalaj=round(malzeme_ambalaj, 2),
        emek_karsiligi=round(emek, 2), komisyon=round(komisyon, 2), kargo=round(g.kargo, 2),
        kar=round(eline_gecen - malzeme_ambalaj - emek, 2), eline_gecen=round(eline_gecen, 2),
        gercek_saatlik=None if saatlik is None else round(saatlik, 2))


def fiyat_oner(g: FiyatGirdisi) -> FiyatDokumu:
    """
    Komisyon ve kargo düşüldükten sonra elinize maliyet + kâr kalacak satış fiyatı:
        P − P·komisyon − kargo = (malzeme + ambalaj + emek) · (1 + kâr)
        P = [(malzeme + ambalaj + emek) · (1 + kâr) + kargo] / (1 − komisyon)
    P sonra `yuvarlama` tutarının katına YUKARI yuvarlanır; kâr azalmaz.
    """
    _dogrula(g)
    maliyet = g.malzeme + g.ambalaj + g.emek_saat * g.saat_ucreti
    ham = (maliyet * (1 + g.kar_yuzde / 100) + g.kargo) / (1 - g.komisyon_yuzde / 100)
    if g.yuvarlama and g.yuvarlama > 0:
        fiyat = math.ceil(round(ham / g.yuvarlama, 6)) * g.yuvarlama
    else:
        fiyat = round(ham, 2)
    return dokum(g, fiyat)


# ---------------------------------------------------------------------------
# Müşteriye cevap
# ---------------------------------------------------------------------------
HAZIR_CEVAPLAR = {
    "💰 Fiyat sorusu":
        "Merhaba, ilginiz için çok teşekkür ederim 🌸 [ürün adı] fiyatı [fiyat] TL. Tamamen elde, "
        "sipariş üzerine hazırlıyorum. Sipariş vermek isterseniz size nasıl ulaştırabileceğimi yazabilirim.",
    "🚚 Kargo süresi":
        "Merhaba 🌸 Siparişinizi [hazırlık süresi] içinde hazırlayıp [kargo firması] ile gönderiyorum. "
        "Kargoya verdikten sonra teslimat genellikle [teslimat süresi] sürüyor. Kargoya verdiğimde takip "
        "numarasını size ileteceğim.",
    "🎨 Özel sipariş / renk":
        "Merhaba, ne güzel bir fikir 🌸 [istenen renk ya da ölçü] ile hazırlayabilirim. Özel siparişlerde "
        "hazırlık süresi [süre], fiyatı [fiyat] TL oluyor. Uygunsa ayrıntıları birlikte netleştirelim.",
    "📦 Elimde hazır yok":
        "Merhaba, ilginiz için teşekkür ederim 🌸 Şu an elimde hazır yok ama sipariş üzerine [süre] içinde "
        "hazırlayabilirim. İsterseniz sizin için sıraya alayım.",
    "↩️ İade / değişim":
        "Merhaba 🌸 Yaşadığınız durum için üzgünüm. İade ve değişim koşullarım şöyle: [iade ve değişim "
        "koşullarınız]. Ürünün fotoğrafını gönderebilirseniz en kısa sürede birlikte çözelim.",
    "🤝 Pazarlık":
        "Merhaba, ilginiz için çok teşekkür ederim 🌸 Fiyatı malzemeyi ve harcadığım emeği hesaplayarak "
        "belirliyorum, bu yüzden [fiyat] TL'nin altına inemiyorum. İsterseniz [daha uygun bir seçenek] "
        "önerebilirim.",
    "⭐ Teşekkür ve yorum rica":
        "Merhaba 🌸 Siparişinizin elinize ulaştığını umuyorum. Beğendiyseniz kısa bir yorum ya da fotoğrafla "
        "paylaşmanız benim gibi küçük üreticiler için çok değerli. Tekrar teşekkür ederim!",
}
TONLAR = {"🌸 Samimi": "samimi ve sıcak", "👔 Resmi": "kibar ve resmi"}
_YER_TUTUCU = re.compile(r"\[([^\[\]\n]{1,40})\]")


def yer_tutucular(metin: str) -> list[str]:
    """Metindeki [köşeli parantezli] doldurulacak yerleri sırasıyla, tekrarsız döndürür."""
    return list(dict.fromkeys(m.strip() for m in _YER_TUTUCU.findall(metin or "")))


def musteri_cevabi_uret(mesaj: str, urun_bilgisi: str = "", ton: str = "🌸 Samimi",
                        ozenli: bool = False, client=None) -> str:
    mesaj = (mesaj or "").strip()
    if len(mesaj) < 3:
        raise ValueError("Müşterinin mesajını yapıştırın.")
    prompt = prompts.musteri_cevabi(mesaj[:2000], (urun_bilgisi or "").strip()[:3000],
                                    TONLAR.get(ton, "samimi ve sıcak"))
    cevap = str(uret.json_coz(uret.metin_uret(prompt, ozenli=ozenli, json_yanit=True,
                                              client=client)).get("cevap", "")).strip()
    if not cevap:
        raise ValueError("Cevap hazırlanamadı, tekrar deneyin.")
    return cevap


# ---------------------------------------------------------------------------
# Pazaryeri ilanı ve çeviri
# ---------------------------------------------------------------------------
PLATFORMLAR = {"🟠 Trendyol": "tr", "🟧 Hepsiburada": "tr", "🌍 Etsy (İngilizce)": "en"}
TR_BASLIK = 100
ETSY_BASLIK = 140
ETSY_ETIKET_ADET = 13
ETSY_ETIKET_UZUNLUK = 20
# İngilizce etiketteki iddia → anlatımda geçmesi gereken Türkçe kök (hashtag süzgeciyle aynı mantık)
_EN_KANIT = {"organic": "organik", "natural": "doğal", "cotton": "pamuk", "wool": "yün",
             "silk": "ipek", "silver": "gümüş", "gold": "altın", "leather": "deri", "linen": "keten",
             "bamboo": "bambu", "vegan": "vegan", "gluten": "glutensiz"}
_EN_YASAK = ("miracle", "cure", "healing", "guarantee", "medical")


@dataclass
class Ilan:
    platform: str
    baslik: str
    ozellikler: list[str]
    aciklama: str
    etiketler: list[str]
    eksik_bilgiler: list[str]
    cikarilan_etiketler: list[str]


def _liste(deger) -> list:
    return deger if isinstance(deger, list) else []


def etiket_denetle(etiketler: list, anlatim: str) -> tuple[list[str], list[str]]:
    """
    Pazaryeri etiketlerini hashtag süzgeciyle aynı kurala göre süzer: iddia/klişe içerenler
    ve anlatımda geçmeyen malzeme/özellik iddiaları (Türkçe ya da İngilizce) çıkarılır.
    Döndürür: (kalan etiketler, çıkarılanlar).
    """
    kaynak = uret._tr_kucuk(anlatim or "")
    kalan, cikan = [], []
    for ham in etiketler:
        etiket = " ".join(str(ham).split()).strip("#,.;: ")
        if not etiket:
            continue
        kucuk = uret._tr_kucuk(etiket)
        bitisik = kucuk.replace(" ", "")
        uygun = (not any(y in bitisik for y in uret._YASAK_HASHTAG_KOKLERI)
                 and all(k in kaynak for k in uret._KANIT_ISTEYEN_KOKLER if k in bitisik)
                 and not any(y in kucuk for y in _EN_YASAK)
                 and all(tr in kaynak for en, tr in _EN_KANIT.items() if en in kucuk))
        (kalan if uygun else cikan).append(etiket)
    return list(dict.fromkeys(kalan)), list(dict.fromkeys(cikan))


def _kisalt(metin: str, sinir: int) -> str:
    metin = " ".join((metin or "").split())
    if len(metin) <= sinir:
        return metin
    return (metin[:sinir].rsplit(" ", 1)[0] or metin[:sinir]).rstrip(" ,.;:-")


def pazaryeri_ilani_uret(anlatim: str, kategori: str, platform: str, ozenli: bool = False,
                         client=None) -> Ilan:
    if platform not in PLATFORMLAR:
        raise ValueError(f"Bilinmeyen platform: {platform}")
    anlatim = (anlatim or "").strip()
    if len(anlatim.split()) < 5:
        raise ValueError("Ürününüzü birkaç cümleyle anlatın.")
    dil = PLATFORMLAR[platform]
    ad = platform.split(" ", 1)[1]
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori) if dil == "tr" else None
    veri = uret.json_coz(uret.metin_uret(
        prompts.pazaryeri_ilani(anlatim[:4000], kategori, ad, dil, kelimeler),
        ozenli=ozenli, json_yanit=True, client=client))

    baslik = _kisalt(str(veri.get("baslik", "")), ETSY_BASLIK if dil == "en" else TR_BASLIK)
    aciklama = str(veri.get("aciklama", "")).strip()
    if not baslik or not aciklama:
        raise ValueError("İlan hazırlanamadı, tekrar deneyin.")
    etiketler, cikan = etiket_denetle(_liste(veri.get("etiketler")), anlatim)
    if dil == "en":                      # Etsy sınırları: en fazla 13 etiket, her biri ≤ 20 karakter
        cikan += [e for e in etiketler if len(e) > ETSY_ETIKET_UZUNLUK]
        etiketler = [e for e in etiketler if len(e) <= ETSY_ETIKET_UZUNLUK][:ETSY_ETIKET_ADET]
    else:
        etiketler = etiketler[:15]
    return Ilan(
        platform=platform, baslik=baslik,
        ozellikler=[str(x).strip() for x in _liste(veri.get("ozellikler")) if str(x).strip()][:10],
        aciklama=aciklama, etiketler=etiketler,
        eksik_bilgiler=[str(x).strip() for x in _liste(veri.get("eksik_bilgiler")) if str(x).strip()][:8],
        cikarilan_etiketler=cikan)


def cevir(metin: str, hedef_dil: str = "İngilizce", client=None) -> str:
    metin = (metin or "").strip()
    if not metin:
        raise ValueError("Çevrilecek metni yazın.")
    sonuc = uret.metin_uret(prompts.ceviri(metin[:5000], hedef_dil), client=client).strip()
    if not sonuc:
        raise ValueError("Çeviri yapılamadı, tekrar deneyin.")
    return sonuc


# ---------------------------------------------------------------------------
# Özel günler ve kampanya
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OzelGun:
    ad: str
    tarih: date
    aciklama: str
    yaklasik: bool = False


def _ayin_ninci_gunu(yil: int, ay: int, hafta_gunu: int, n: int) -> date:
    """Ayın n'inci belirli hafta günü (hafta_gunu: 0 = Pazartesi … 6 = Pazar)."""
    ilk = date(yil, ay, 1)
    return ilk + timedelta(days=(hafta_gunu - ilk.weekday()) % 7 + 7 * (n - 1))


def _yilin_ozel_gunleri(yil: int) -> list[OzelGun]:
    # Dini bayramlar ay takvimine göre her yıl kaydığı için buraya bilerek konmadı;
    # kullanıcı "kendi özel gününü" ekleyebilir.
    return [
        OzelGun("Yılbaşı", date(yil, 1, 1), "Yeni yıl hediyeleri; siparişler Aralık başında yoğunlaşır."),
        OzelGun("Sevgililer Günü", date(yil, 2, 14), "Sevdiklere küçük, kişisel hediyeler."),
        OzelGun("Dünya Kadınlar Günü", date(yil, 3, 8), "Kadın emeğini görünür kılmak için anlamlı bir gün."),
        OzelGun("Anneler Günü", _ayin_ninci_gunu(yil, 5, 6, 2),
                "Mayıs'ın 2. Pazarı; el emeği hediyelerin en yoğun dönemi."),
        OzelGun("Babalar Günü", _ayin_ninci_gunu(yil, 6, 6, 3), "Haziran'ın 3. Pazarı."),
        OzelGun("Okulların açılışı", _ayin_ninci_gunu(yil, 9, 0, 2),
                "Eylül ortası; kesin tarih her yıl Millî Eğitim Bakanlığınca açıklanır.", yaklasik=True),
        OzelGun("Öğretmenler Günü", date(yil, 11, 24), "Öğretmenlere küçük, kişisel teşekkür hediyeleri."),
        OzelGun("Kasım indirim dönemi", _ayin_ninci_gunu(yil, 11, 3, 4) + timedelta(days=1),
                "Kasım'ın dördüncü Perşembesinin ertesi günü; alışverişin yoğunlaştığı dönem."),
    ]


def yaklasan_ozel_gunler(bugun: date | None = None, gun_sayisi: int = 365) -> list[OzelGun]:
    bugun = bugun or takvim.simdi().date()
    son = bugun + timedelta(days=gun_sayisi)
    gunler = [g for yil in (bugun.year, bugun.year + 1) for g in _yilin_ozel_gunleri(yil)
              if bugun <= g.tarih <= son]
    return sorted(gunler, key=lambda g: g.tarih)


def tarih_metni(g: OzelGun) -> str:
    return f"{g.tarih.day} {takvim.AYLAR[g.tarih.month - 1]} {g.tarih.year}, {takvim.GUNLER[g.tarih.weekday()]}"


def kampanya_onerisi_uret(gun: OzelGun, anlatim: str, kategori: str, bugun: date | None = None,
                          ozenli: bool = False, client=None) -> str:
    anlatim = (anlatim or "").strip()
    if len(anlatim.split()) < 5:
        raise ValueError("Ürününüzü birkaç cümleyle anlatın.")
    kalan = (gun.tarih - (bugun or takvim.simdi().date())).days
    metin = uret.metin_uret(prompts.kampanya_onerisi(gun.ad, tarih_metni(gun), kalan, anlatim[:4000],
                                                     kategori), ozenli=ozenli, client=client).strip()
    if not metin:
        raise ValueError("Öneri hazırlanamadı, tekrar deneyin.")
    return metin


def kampanya_plani(gun: OzelGun, metin: str, icerik_id: str = "",
                   saat: time = takvim.VARSAYILAN_SAAT,
                   an: datetime | None = None) -> list[takvim.PlanOgesi]:
    """Özel günden 10 ve 3 gün önce ve özel günün kendisi için üç hatırlatma; geçmişte kalan atlanır."""
    an = an or takvim.simdi()
    ogeler = []
    for once, etiket in ((10, "hazırlık duyurusu"), (3, "hatırlatma"), (0, "özel gün paylaşımı")):
        zaman = takvim.zaman_birlestir(gun.tarih - timedelta(days=once), saat)
        if zaman > an:
            ogeler.append(takvim.PlanOgesi(zaman=zaman.isoformat(), kanal="instagram",
                                           baslik=f"{gun.ad} · {etiket}", metin=metin,
                                           icerik_id=icerik_id))
    return ogeler
