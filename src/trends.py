# -*- coding: utf-8 -*-
"""
Üretken Kadın — Google Trends (SEO anahtar kelime) entegrasyonu

Amaç: Prompt'a enjekte edilen anahtar kelimeleri artık ELLE sabitlemek yerine,
Google Trends'ten (Türkiye, ücretsiz "ilgi zaman içinde" + "ilgili sorgular")
gerçek arama davranışıyla beslemek. Bu, projenin SEO vaadinin çekirdeğidir
(bkz. Concept Note — Veri Kaynakları / Bölüm B tech-stack: pytrends).

Tasarım ilkeleri:
  1. ASLA çökmez. Ağ yok, kota doldu (429), Trends boş döndü — her durumda
     prompts.KATEGORI_KELIMELERI içindeki güvenli varsayılana düşer.
  2. Önbellekli. Trends kotası düşüktür ve Google sık sık 429 döndürür; sonuçlar
     data/trends_onbellek.json içinde saklanır (varsayılan 7 gün taze sayılır).
  3. Şeffaf. Kelimelerin nereden geldiği (trends / önbellek / varsayılan)
     TrendSonucu.kaynak alanında döner; arayüz bunu kullanıcıya gösterir.

Not: Google Trends yalnızca 0-100 GÖRELİ ilgi verir, mutlak hacim vermez
(Veri Araştırması §3.1). Bu yüzden Trends yönlendirici olarak kullanılır;
kelimeler varsayılanlarla harmanlanıp tekilleştirilir, tek karar kaynağı sayılmaz.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import prompts

# Proje kökü (bu dosya src/ içinde)
_KOK = Path(__file__).resolve().parent.parent
ONBELLEK_YOLU = _KOK / "data" / "trends_onbellek.json"

ONBELLEK_TAZELIK_GUN = 7        # bundan eski önbellek kaydı yenilenir
ULKE = "TR"
ZAMAN_ARALIGI = "today 12-m"    # son 12 ay
ISTEK_DENEME = 2                # 429/ağ hatasında toplam deneme sayısı


# ---------------------------------------------------------------------------
@dataclass
class TrendSonucu:
    """Bir kategori için toplanan SEO anahtar kelimeleri ve kaynağı."""
    kelimeler: list[str]
    kaynak: str                 # "trends" | "önbellek" | "varsayılan"
    kategori: str
    ayrinti: dict = field(default_factory=dict)   # {kelime: göreli_ilgi} vb.

    def trendten_mi(self) -> bool:
        return self.kaynak in ("trends", "önbellek")


# ---------------------------------------------------------------------------
# Önbellek okuma / yazma
# ---------------------------------------------------------------------------
def _onbellek_oku() -> dict:
    if not ONBELLEK_YOLU.exists():
        return {}
    try:
        return json.loads(ONBELLEK_YOLU.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _onbellek_yaz(veri: dict) -> None:
    try:
        ONBELLEK_YOLU.parent.mkdir(parents=True, exist_ok=True)
        ONBELLEK_YOLU.write_text(json.dumps(veri, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    except Exception:
        pass        # önbellek yazılamazsa sessiz geç — akışı bozmaz


def _taze_mi(kayit: dict) -> bool:
    try:
        damga = datetime.fromisoformat(kayit["zaman"])
    except Exception:
        return False
    return datetime.now() - damga < timedelta(days=ONBELLEK_TAZELIK_GUN)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _tohumlari_bul(kategori: str, ek_tohumlar: list[str] | None) -> list[str]:
    """Trends'e sorulacak başlangıç (seed) kelimeleri."""
    tohumlar = list(prompts.KATEGORI_KELIMELERI.get(kategori, []))
    if ek_tohumlar:
        tohumlar = ek_tohumlar + tohumlar
    # tekilleştir, sırayı koru
    return list(dict.fromkeys(t.strip() for t in tohumlar if t and t.strip()))


def _harmanla(trends_kelimeleri: list[str], varsayilan: list[str],
              adet: int) -> list[str]:
    """Trends'ten gelen + varsayılan kelimeleri tekilleştirip kırpar."""
    birlesik = list(dict.fromkeys([*trends_kelimeleri, *varsayilan]))
    return birlesik[:adet]


# ---------------------------------------------------------------------------
# Trends'ten çekme (pytrends). İzole edilmiştir: her hata yakalanır.
# ---------------------------------------------------------------------------
def _trendten_cek(tohumlar: list[str], adet: int) -> tuple[list[str], dict]:
    """
    pytrends ile ilgili sorguları çeker. Dönüş: (kelimeler, ayrıntı).
    Herhangi bir hata (ImportError, ağ, 429, boş sonuç) RuntimeError'a çevrilir;
    çağıran taraf bunu yakalayıp varsayılana düşer.
    """
    try:
        from pytrends.request import TrendReq
    except Exception as e:
        raise RuntimeError(f"pytrends kurulu değil: {e}")

    son_hata = None
    for deneme in range(1, ISTEK_DENEME + 1):
        try:
            py = TrendReq(hl="tr-TR", tz=180, timeout=(4, 10))
            bulunan: dict[str, float] = {}

            # En fazla ilk 3 tohumu sor (kota dostu); ilgili sorguları topla
            for tohum in tohumlar[:3]:
                py.build_payload([tohum], timeframe=ZAMAN_ARALIGI, geo=ULKE)
                ilgili = py.related_queries() or {}
                blok = ilgili.get(tohum) or {}
                for tur in ("top", "rising"):
                    df = blok.get(tur)
                    if df is None or getattr(df, "empty", True):
                        continue
                    for _, satir in df.head(8).iterrows():
                        kelime = str(satir.get("query", "")).strip().lower()
                        deger = float(satir.get("value", 0) or 0)
                        if kelime and len(kelime) <= 40:
                            bulunan[kelime] = max(bulunan.get(kelime, 0.0), deger)
                time.sleep(0.5)     # ardışık istekleri biraz arala

            if not bulunan:
                raise RuntimeError("Trends boş sonuç döndürdü")

            # göreli ilgiye göre sırala
            sirali = sorted(bulunan.items(), key=lambda x: x[1], reverse=True)
            kelimeler = [k for k, _ in sirali][:adet]
            return kelimeler, dict(sirali[:adet])

        except Exception as e:
            son_hata = e
            metin = str(e)
            gecici = any(k in metin for k in ("429", "TooManyRequests", "timeout",
                                              "Max retries", "ResponseError"))
            if gecici and deneme < ISTEK_DENEME:
                time.sleep(3 * deneme)
                continue
            break

    raise RuntimeError(f"Trends çekilemedi: {son_hata}")


# ---------------------------------------------------------------------------
# Genel API
# ---------------------------------------------------------------------------
def trend_getir(kategori: str,
                ek_tohumlar: list[str] | None = None,
                adet: int = 6,
                onbellek: bool = True,
                zorla: bool = False) -> TrendSonucu:
    """
    Bir kategori için SEO anahtar kelimelerini döndürür.

    kategori     : prompts.KATEGORI_KELIMELERI anahtarlarından biri
    ek_tohumlar  : ürün özelinde ek başlangıç kelimeleri (örn. ["bebek battaniyesi"])
    adet         : döndürülecek kelime sayısı
    onbellek     : önbellek okunsun/yazılsın mı
    zorla        : True ise taze önbellek olsa bile Trends'i yeniden sorar
    """
    varsayilan = list(prompts.KATEGORI_KELIMELERI.get(kategori, []))
    anahtar = kategori if not ek_tohumlar else f"{kategori}|{'+'.join(ek_tohumlar)}"

    # 1) Önbellek
    kutu = _onbellek_oku()
    if onbellek and not zorla:
        kayit = kutu.get(anahtar)
        if kayit and _taze_mi(kayit) and kayit.get("kelimeler"):
            return TrendSonucu(kelimeler=kayit["kelimeler"], kaynak="önbellek",
                               kategori=kategori, ayrinti=kayit.get("ayrinti", {}))

    # 2) Canlı Trends
    try:
        tohumlar = _tohumlari_bul(kategori, ek_tohumlar)
        if not tohumlar:
            raise RuntimeError("Tohum kelime yok")
        ham, ayrinti = _trendten_cek(tohumlar, adet)
        kelimeler = _harmanla(ham, varsayilan, adet)

        if onbellek:
            kutu[anahtar] = {"kelimeler": kelimeler, "ayrinti": ayrinti,
                             "zaman": datetime.now().isoformat(timespec="seconds")}
            _onbellek_yaz(kutu)

        return TrendSonucu(kelimeler=kelimeler, kaynak="trends",
                           kategori=kategori, ayrinti=ayrinti)

    # 3) Varsayılana düş — akış asla kesilmez
    except Exception:
        return TrendSonucu(kelimeler=varsayilan[:adet], kaynak="varsayılan",
                           kategori=kategori)


def anahtar_kelimeler(kategori: str,
                      ek_tohumlar: list[str] | None = None,
                      adet: int = 6) -> list[str]:
    """Sade kısayol: yalnızca kelime listesini döndürür (uret.py bunu kullanır)."""
    return trend_getir(kategori, ek_tohumlar=ek_tohumlar, adet=adet).kelimeler


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Trends modülü — hızlı deneme\n" + "=" * 50)
    for kat in prompts.KATEGORI_KELIMELERI:
        s = trend_getir(kat, adet=6)
        print(f"\n{kat}  [{s.kaynak}]")
        print("  " + ", ".join(s.kelimeler))
