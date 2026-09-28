# -*- coding: utf-8 -*-
"""
Üretken Kadın — içerik takvimi

Hazırlanan içeriklerin ne zaman paylaşılacağını planlar, telefonun takvimine
eklenebilen .ics dosyası üretir ve planı dosyaya kaydedip geri yükler.

Neden otomatik paylaşım değil: Instagram'a doğrudan gönderi atmak işletme hesabı,
bağlı Facebook sayfası ve Meta uygulama incelemesi gerektirir. Takvim hatırlatması
bugün, kurulumsuz çalışır: paylaşım saati yaklaşınca telefon hatırlatır, metin
etkinliğin içinde hazırdır.

KVKK: plan yalnızca oturumda tutulur. "Kaydet" dosyası kullanıcının kendi
cihazına iner; sunucuda saklanmaz.

Streamlit'e bağımlı değildir; testlerde doğrudan kullanılır (tests/test_takvim.py).
"""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from itertools import groupby

# Türkiye 2016'dan beri yıl boyu UTC+3 (yaz saati yok). Sabit dilim, sunucunun
# saatinden (Streamlit Cloud: UTC) bağımsız doğru zaman verir ve Windows'ta
# tzdata paketi gerektirmez.
TR = timezone(timedelta(hours=3), "TRT")

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

# Başlangıç önerisi — veriye dayalı bir iddia değildir. Kullanıcıya, kendi
# takipçilerinin aktif olduğu saatleri Instagram istatistiklerinden görüp
# değiştirmesi söylenir.
VARSAYILAN_GUNLER = [1, 3, 5]          # Salı, Perşembe, Cumartesi
VARSAYILAN_SAAT = time(20, 0)
HATIRLATMA_DK = 30

KANALLAR = {
    "instagram": "📱 Instagram gönderisi",
    "story": "🟣 Instagram hikâyesi",
    "whatsapp": "💬 WhatsApp durumu",
    "shopier": "🛍️ Shopier'e ekle",
}

UYGULAMA = "uretken-kadin"
SURUM = 1
MAKS_DOSYA_BAYT = 2_000_000
MAKS_METIN = 6000
MAKS_KAYIT = 500
ICERIK_ALANLARI = ("id", "tarih", "saat", "kategori", "anlatim", "instagram", "shopier")
EK_ANAHTARLARI = ("story", "whatsapp", "hashtag", "reels", "foto")
_ID_DESENI = re.compile(r"[A-Za-z0-9_-]{1,40}")


def yeni_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class PlanOgesi:
    """Takvimdeki tek bir paylaşım."""
    zaman: str                 # ISO 8601, +03:00
    kanal: str                 # KANALLAR anahtarı
    baslik: str
    metin: str = ""            # hatırlatmanın içine konan, paylaşılacak metin
    icerik_id: str = ""        # hangi içerikten geldiği
    tamam: bool = False        # "paylaştım" işaretlendi mi
    id: str = field(default_factory=yeni_id)

    def zaman_dt(self) -> datetime:
        return datetime.fromisoformat(self.zaman).astimezone(TR)


# ---------------------------------------------------------------------------
# Zaman yardımcıları
# ---------------------------------------------------------------------------
def simdi() -> datetime:
    return datetime.now(TR)


def zaman_birlestir(gun: date, saat: time) -> datetime:
    return datetime.combine(gun, saat.replace(second=0, microsecond=0, tzinfo=None),
                            tzinfo=TR)


def tarih_etiketi(zaman: datetime, bugun: date | None = None) -> str:
    """'Yarın · 17 Eylül Perşembe' gibi, üreticinin rahat okuyacağı tarih."""
    zaman = zaman.astimezone(TR)
    bugun = bugun or simdi().date()
    gun = f"{zaman.day} {AYLAR[zaman.month - 1]} {GUNLER[zaman.weekday()]}"
    fark = (zaman.date() - bugun).days
    if fark == 0:
        return f"Bugün · {gun}"
    if fark == 1:
        return f"Yarın · {gun}"
    return gun


def kisa_etiket(zaman: datetime, bugun: date | None = None) -> str:
    """Özet kutuları için kısa biçim: 'Bugün 20:00', 'Yarın 20:00', '17 Eyl 20:00'."""
    zaman = zaman.astimezone(TR)
    bugun = bugun or simdi().date()
    fark = (zaman.date() - bugun).days
    gun = ("Bugün" if fark == 0 else "Yarın" if fark == 1
           else f"{zaman.day} {AYLAR[zaman.month - 1][:3]}")
    return f"{gun} {zaman:%H:%M}"


def baslik_uret(anlatim: str, uzunluk: int = 48) -> str:
    """Anlatımın ilk cümlesinden kısa bir başlık ('El örgüsü bebek battaniyesi yapıyorum')."""
    tek = " ".join((anlatim or "").split())
    ilk = re.split(r"[.!?]", tek, maxsplit=1)[0].strip() or tek
    if len(ilk) <= uzunluk:
        return ilk
    kesik = ilk[:uzunluk].rsplit(" ", 1)[0] or ilk[:uzunluk]
    return kesik.rstrip(".,;:") + "…"


# ---------------------------------------------------------------------------
# Planlama
# ---------------------------------------------------------------------------
def sonraki_zamanlar(gunler: list[int], saat: time, adet: int,
                     baslangic: datetime | None = None,
                     dolu_gunler: set[date] | None = None,
                     en_fazla_gun: int = 120) -> list[datetime]:
    """
    Seçilen hafta günlerinde, verilen saatte, sıradaki `adet` boş zamanı döndürür.

    Aynı güne ikinci gönderi konmaz (dolu_gunler). Hatırlatması şimdiden önce
    kalacak kadar yakın bir saat seçilmez.
    """
    if not gunler:
        raise ValueError("En az bir gün seçin.")
    if adet <= 0:
        return []
    baslangic = (baslangic or simdi()).astimezone(TR)
    dolu = set(dolu_gunler or ())
    sonuc: list[datetime] = []
    for i in range(en_fazla_gun):
        gun = baslangic.date() + timedelta(days=i)
        if gun.weekday() not in gunler or gun in dolu:
            continue
        aday = zaman_birlestir(gun, saat)
        if aday < baslangic + timedelta(minutes=HATIRLATMA_DK):
            continue
        sonuc.append(aday)
        dolu.add(gun)
        if len(sonuc) >= adet:
            break
    return sonuc


def dolu_gunler(plan: list[PlanOgesi], kanal: str = "instagram") -> set[date]:
    return {o.zaman_dt().date() for o in plan if o.kanal == kanal}


def planlanmamis(icerikler: list[dict], plan: list[PlanOgesi],
                 kanal: str = "instagram") -> list[dict]:
    planli = {o.icerik_id for o in plan if o.kanal == kanal}
    return [k for k in icerikler if k.get("id") and k["id"] not in planli]


def plan_oner(icerikler: list[dict], plan: list[PlanOgesi], gunler: list[int],
              saat: time, baslangic: datetime | None = None) -> list[PlanOgesi]:
    """
    Henüz Instagram'a planlanmamış içerikleri sıradaki boş günlere yerleştirir.

    icerikler arayüzdeki geçmiş sırasıyla gelir (en yeni başta); en eski içerik
    önce paylaşılsın diye ters çevrilir. Mevcut planı değiştirmez, yeni öğeleri döndürür.
    """
    bekleyen = list(reversed(planlanmamis(icerikler, plan)))
    zamanlar = sonraki_zamanlar(gunler, saat, len(bekleyen), baslangic, dolu_gunler(plan))
    return [PlanOgesi(zaman=z.isoformat(), kanal="instagram",
                      baslik=baslik_uret(k.get("anlatim", "")),
                      metin=k.get("instagram", ""), icerik_id=k["id"])
            for k, z in zip(bekleyen, zamanlar)]


def sirali(plan: list[PlanOgesi]) -> list[PlanOgesi]:
    return sorted(plan, key=lambda o: o.zaman_dt())


def siradaki(plan: list[PlanOgesi], an: datetime | None = None) -> PlanOgesi | None:
    an = an or simdi()
    return next((o for o in sirali(plan) if not o.tamam and o.zaman_dt() >= an), None)


def ayir(plan: list[PlanOgesi], an: datetime | None = None) -> dict[str, list[PlanOgesi]]:
    """Planı üç gruba ayırır: yaklaşan, zamanı geçen (paylaşılmamış), paylaşılan."""
    an = an or simdi()
    gruplar = {"yaklasan": [], "gecen": [], "tamam": []}
    for o in sirali(plan):
        if o.tamam:
            gruplar["tamam"].append(o)
        elif o.zaman_dt() >= an:
            gruplar["yaklasan"].append(o)
        else:
            gruplar["gecen"].append(o)
    return gruplar


def gune_gore(ogeler: list[PlanOgesi]) -> list[tuple[date, list[PlanOgesi]]]:
    return [(g, list(o)) for g, o in groupby(sirali(ogeler), key=lambda o: o.zaman_dt().date())]


def onumuzdeki_gunler(plan: list[PlanOgesi], gun: int = 7,
                      an: datetime | None = None) -> list[PlanOgesi]:
    an = an or simdi()
    return [o for o in ayir(plan, an)["yaklasan"] if o.zaman_dt() < an + timedelta(days=gun)]


# ---------------------------------------------------------------------------
# Takvim dosyası (.ics — RFC 5545)
# ---------------------------------------------------------------------------
def _ics_metin(s: str) -> str:
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n"))


def _katla(satir: str) -> str:
    """RFC 5545: satır 75 baytı geçmesin; devam satırı boşlukla başlar. UTF-8 harf bölünmez."""
    if len(satir.encode("utf-8")) <= 75:
        return satir
    parcalar, simdiki, sinir = [], "", 75
    for harf in satir:
        if len((simdiki + harf).encode("utf-8")) > sinir:
            parcalar.append(simdiki)
            simdiki, sinir = harf, 74       # devam satırındaki boşluk da sayılır
        else:
            simdiki += harf
    parcalar.append(simdiki)
    return "\r\n ".join(parcalar)


def _utc(zaman: datetime) -> str:
    return zaman.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics_olustur(ogeler: list[PlanOgesi], hatirlatma_dk: int = HATIRLATMA_DK,
                olusturma: datetime | None = None) -> bytes:
    """Telefon/Google takvimine eklenebilen etkinlikler; her biri paylaşımdan önce hatırlatır."""
    damga = _utc(olusturma or simdi())
    satirlar = ["BEGIN:VCALENDAR", "VERSION:2.0",
                "PRODID:-//Uretken Kadin//Icerik Takvimi//TR",
                "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                "X-WR-CALNAME:" + _ics_metin("Üretken Kadın paylaşımlarım")]
    for o in sirali(ogeler):
        bas = o.zaman_dt()
        etiket = KANALLAR.get(o.kanal, o.kanal)
        aciklama = (f"{o.metin.strip()}\n\n" if o.metin.strip() else "") + \
            "Metni kopyalayıp paylaşın. — Üretken Kadın"
        satirlar += [
            "BEGIN:VEVENT",
            f"UID:{o.id}@{UYGULAMA}",
            f"DTSTAMP:{damga}",
            f"DTSTART:{_utc(bas)}",
            f"DTEND:{_utc(bas + timedelta(minutes=15))}",
            "SUMMARY:" + _ics_metin(f"{etiket}: {o.baslik}"),
            "DESCRIPTION:" + _ics_metin(aciklama),
            "BEGIN:VALARM", "ACTION:DISPLAY",
            "DESCRIPTION:" + _ics_metin(f"Paylaşım zamanı yaklaştı: {o.baslik}"),
            f"TRIGGER:-PT{int(hatirlatma_dk)}M",
            "END:VALARM", "END:VEVENT",
        ]
    satirlar.append("END:VCALENDAR")
    return ("\r\n".join(_katla(s) for s in satirlar) + "\r\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Kaydet / yükle (JSON)
# ---------------------------------------------------------------------------
def disa_aktar(icerikler: list[dict], plan: list[PlanOgesi],
               uslup_ornekleri: list[str] | None = None,
               an: datetime | None = None) -> str:
    veri = {
        "uygulama": UYGULAMA,
        "surum": SURUM,
        "kaydedilme": (an or simdi()).isoformat(timespec="seconds"),
        "icerikler": [{**{a: k.get(a, "") for a in ICERIK_ALANLARI},
                       "fiyat": _fiyat(k.get("fiyat")),
                       "ekler": dict(k.get("ekler") or {})} for k in icerikler],
        "plan": [asdict(o) for o in plan],
        "uslup_ornekleri": list(uslup_ornekleri or []),
    }
    return json.dumps(veri, ensure_ascii=False, indent=2)


def _fiyat(deger) -> float | None:
    """Kaydedilen ürün fiyatı: pozitif, makul bir sayı değilse yok sayılır."""
    if isinstance(deger, bool) or not isinstance(deger, (int, float)):
        return None
    return float(deger) if math.isfinite(deger) and 0 < deger <= 10_000_000 else None


def _liste(deger) -> list:
    return deger if isinstance(deger, list) else []


def _metin(sozluk: dict, anahtar: str) -> str:
    deger = sozluk.get(anahtar, "")
    return deger[:MAKS_METIN] if isinstance(deger, str) else ""


def _gecerli_id(deger) -> bool:
    return isinstance(deger, str) and bool(_ID_DESENI.fullmatch(deger))


def ice_aktar(veri: bytes | str) -> tuple[list[dict], list[PlanOgesi], list[str], list[str]]:
    """
    Kayıt dosyasını okur ve doğrular.

    Döndürür: (içerikler, plan, üslup örnekleri, uyarılar). Dosya bu uygulamaya ait
    değilse ValueError. Bozuk tek tek kayıtlar atlanır ve uyarıda sayılır.
    Kimlikler widget anahtarı ve takvim UID'si olarak kullanıldığı için doğrulanır.
    """
    hatali = "Bu bir Üretken Kadın kayıt dosyası değil."
    if isinstance(veri, bytes):
        if len(veri) > MAKS_DOSYA_BAYT:
            raise ValueError("Dosya çok büyük.")
        try:
            veri = veri.decode("utf-8-sig")
        except UnicodeDecodeError as hata:
            raise ValueError(hatali) from hata
    try:
        ham = json.loads(veri)
    except json.JSONDecodeError as hata:
        raise ValueError(hatali) from hata
    if not isinstance(ham, dict) or ham.get("uygulama") != UYGULAMA:
        raise ValueError(hatali)
    surum = ham.get("surum")
    if not isinstance(surum, int) or isinstance(surum, bool) or surum > SURUM:
        raise ValueError("Bu dosya uygulamanın başka bir sürümüyle kaydedilmiş.")

    atlanan = 0
    icerikler = []
    for k in _liste(ham.get("icerikler"))[:MAKS_KAYIT]:
        if not isinstance(k, dict) or not (_metin(k, "instagram") or _metin(k, "shopier")):
            atlanan += 1
            continue
        kayit = {a: _metin(k, a) for a in ICERIK_ALANLARI}
        if not _gecerli_id(kayit["id"]):
            kayit["id"] = yeni_id()
        ekler = k.get("ekler") if isinstance(k.get("ekler"), dict) else {}
        kayit["ekler"] = {a: _metin(ekler, a) for a in EK_ANAHTARLARI if _metin(ekler, a)}
        kayit["fiyat"] = _fiyat(k.get("fiyat"))
        icerikler.append(kayit)

    plan = []
    for o in _liste(ham.get("plan"))[:MAKS_KAYIT]:
        try:
            zaman = datetime.fromisoformat(o["zaman"])
            if zaman.tzinfo is None:
                zaman = zaman.replace(tzinfo=TR)
            if o["kanal"] not in KANALLAR:
                raise ValueError
            plan.append(PlanOgesi(
                zaman=zaman.astimezone(TR).isoformat(), kanal=o["kanal"],
                baslik=_metin(o, "baslik")[:120], metin=_metin(o, "metin"),
                icerik_id=_metin(o, "icerik_id")[:40], tamam=o.get("tamam") is True,
                id=o["id"] if _gecerli_id(o.get("id")) else yeni_id()))
        except (KeyError, TypeError, ValueError, AttributeError):
            atlanan += 1

    uslup = [s[:MAKS_METIN] for s in _liste(ham.get("uslup_ornekleri"))
             if isinstance(s, str) and s.strip()][:3]
    uyarilar = [f"{atlanan} kayıt okunamadı ve atlandı."] if atlanan else []
    return icerikler, plan, uslup, uyarilar


def birlestir(mevcut: list, yeni: list) -> tuple[list, int]:
    """Kimliği zaten olanları atlayarak ekler; aynı dosyayı iki kez yüklemek çift kayıt yapmaz."""
    kimlik = lambda x: x["id"] if isinstance(x, dict) else x.id
    var = {kimlik(x) for x in mevcut}
    eklenecek = [x for x in yeni if kimlik(x) not in var]
    return mevcut + eklenecek, len(eklenecek)
