# -*- coding: utf-8 -*-
"""
Üretken Kadın API — iş ortağı anahtarları, günlük kota ve dakikalık hız sınırı

Anahtarlar düz metin olarak SAKLANMAZ; yalnızca SHA-256 özeti tutulur. Anahtarın
kendisi oluşturulduğu anda bir kez gösterilir:

    python src/api_guvenlik.py yeni --ad "Kooperatif A" --kota 500 --dakika 30
    python src/api_guvenlik.py liste
    python src/api_guvenlik.py sil --ad "Kooperatif A"

Anahtar kaynağı (öncelik sırasıyla):
  1. API_ANAHTARLARI ortam değişkeni (JSON) — bulut ortamı (Render, Cloud Run) için
  2. api_anahtarlari.json dosyası (proje kökü, .gitignore'da) — yerel geliştirme için

Sayaçlar bellekte tutulur: tek süreçte doğrudur, sunucu yeniden başlayınca sıfırlanır
ve birden çok süreç/sunucu arasında paylaşılmaz. Bu yüzden API tek işçiyle çalışır;
ölçeklenirken sayaçlar Redis gibi paylaşılan bir depoya taşınmalıdır (bkz. API.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from takvim import TR   # günlük kota Türkiye saatiyle gece yarısı sıfırlanır

ONEK = "uk_"
DOSYA = Path(__file__).resolve().parent.parent / "api_anahtarlari.json"
VARSAYILAN_KOTA = 500
VARSAYILAN_DAKIKA = 30
_OZET_DESENI = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class IsOrtagi:
    ad: str
    gunluk_kota: int
    dakika_siniri: int
    anahtar_ozeti: str


def anahtar_ozeti(anahtar: str) -> str:
    return hashlib.sha256(anahtar.encode("utf-8")).hexdigest()


def yeni_anahtar() -> str:
    return ONEK + secrets.token_urlsafe(32)


def anahtarlari_yukle(ham: str | None = None, dosya: Path = DOSYA) -> dict[str, IsOrtagi]:
    """
    {özet: IsOrtagi} döndürür. Biçim:
        {"<sha256 özeti>": {"ad": "Kooperatif A", "gunluk_kota": 500, "dakika_siniri": 30}}

    Bozuk yapılandırmada ValueError yükselir: sunucu yanlış ayarla sessizce açılmasın.
    """
    if ham is None:
        ham = os.getenv("API_ANAHTARLARI")
        if ham is None and dosya.exists():
            ham = dosya.read_text(encoding="utf-8")
    if not ham or not ham.strip():
        return {}
    try:
        veri = json.loads(ham)
    except json.JSONDecodeError as hata:
        raise ValueError("API anahtar yapılandırması geçerli JSON değil.") from hata
    if not isinstance(veri, dict):
        raise ValueError("API anahtar yapılandırması bir JSON nesnesi olmalı.")
    ortaklar = {}
    for ozet, bilgi in veri.items():
        if not (isinstance(ozet, str) and _OZET_DESENI.fullmatch(ozet)):
            raise ValueError("Geçersiz anahtar özeti (64 karakterlik SHA-256 bekleniyor).")
        if not isinstance(bilgi, dict) or not str(bilgi.get("ad", "")).strip():
            raise ValueError("Her anahtarın bir 'ad' alanı olmalı.")
        kota = int(bilgi.get("gunluk_kota", VARSAYILAN_KOTA))
        dakika = int(bilgi.get("dakika_siniri", VARSAYILAN_DAKIKA))
        if kota < 0 or dakika < 1:
            raise ValueError("Kota 0 veya üstü, dakika sınırı 1 veya üstü olmalı.")
        ortaklar[ozet] = IsOrtagi(ad=str(bilgi["ad"]).strip(), gunluk_kota=kota,
                                  dakika_siniri=dakika, anahtar_ozeti=ozet)
    return ortaklar


# ---------------------------------------------------------------------------
# Kota ve hız sınırı
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KotaSonucu:
    izin: bool
    limit: int
    kalan: int
    yeniden_dene_sn: int = 0
    neden: str = ""            # "gunluk" | "dakika"


class Sayac:
    """
    İş ortağı başına: günlük kota (Türkiye gece yarısı sıfırlanır) ve kayan 60 sn'lik
    hız sınırı. Her istek hız sınırına sayılır; yalnızca maliyeti olan istekler
    (yapay zekâ çağıranlar) günlük kotadan düşer.
    """

    def __init__(self, saat=time.monotonic, simdi=lambda: datetime.now(TR)):
        self._kilit = threading.Lock()
        self._gunluk: dict[str, tuple] = {}          # özet → (tarih, kullanılan)
        self._pencere: dict[str, deque] = {}         # özet → istek zamanları
        self._saat, self._simdi = saat, simdi

    def _bugunku(self, ortak: IsOrtagi) -> tuple:
        bugun = self._simdi().date()
        tarih, kullanilan = self._gunluk.get(ortak.anahtar_ozeti, (bugun, 0))
        return bugun, (kullanilan if tarih == bugun else 0)

    def dene(self, ortak: IsOrtagi, maliyet: int = 1) -> KotaSonucu:
        with self._kilit:
            an, t = self._simdi(), self._saat()
            bugun, kullanilan = self._bugunku(ortak)
            pencere = self._pencere.setdefault(ortak.anahtar_ozeti, deque())
            while pencere and t - pencere[0] >= 60:
                pencere.popleft()
            kalan = max(ortak.gunluk_kota - kullanilan, 0)

            if len(pencere) >= ortak.dakika_siniri:
                bekle = max(1, int(60 - (t - pencere[0])) + 1)
                return KotaSonucu(False, ortak.gunluk_kota, kalan, bekle, "dakika")
            if maliyet and kullanilan + maliyet > ortak.gunluk_kota:
                yarin = datetime.combine(bugun + timedelta(days=1), datetime.min.time(),
                                         tzinfo=TR)
                bekle = max(1, int((yarin - an).total_seconds()))
                return KotaSonucu(False, ortak.gunluk_kota, kalan, bekle, "gunluk")

            pencere.append(t)
            self._gunluk[ortak.anahtar_ozeti] = (bugun, kullanilan + maliyet)
            return KotaSonucu(True, ortak.gunluk_kota, kalan - maliyet)

    def iade(self, ortak: IsOrtagi, maliyet: int = 1) -> None:
        """Bizden kaynaklı hatada (model yoğun vb.) harcanan kota geri verilir."""
        with self._kilit:
            bugun, kullanilan = self._bugunku(ortak)
            self._gunluk[ortak.anahtar_ozeti] = (bugun, max(kullanilan - maliyet, 0))

    def kullanilan(self, ortak: IsOrtagi) -> int:
        with self._kilit:
            return self._bugunku(ortak)[1]

    def sifirlanma(self) -> datetime:
        return datetime.combine(self._simdi().date() + timedelta(days=1),
                                datetime.min.time(), tzinfo=TR)


# ---------------------------------------------------------------------------
# Komut satırı: anahtar oluştur / listele / sil (api_anahtarlari.json)
# ---------------------------------------------------------------------------
def _dosya_oku(dosya: Path) -> dict:
    return json.loads(dosya.read_text(encoding="utf-8")) if dosya.exists() else {}


def _dosya_yaz(dosya: Path, veri: dict) -> None:
    dosya.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None, dosya: Path = DOSYA) -> int:
    ayr = argparse.ArgumentParser(description="Üretken Kadın API anahtar yönetimi")
    alt = ayr.add_subparsers(dest="komut", required=True)
    y = alt.add_parser("yeni", help="Yeni iş ortağı anahtarı oluştur")
    y.add_argument("--ad", required=True)
    y.add_argument("--kota", type=int, default=VARSAYILAN_KOTA, help="Günlük istek kotası")
    y.add_argument("--dakika", type=int, default=VARSAYILAN_DAKIKA, help="Dakikalık istek sınırı")
    alt.add_parser("liste", help="İş ortaklarını listele")
    s = alt.add_parser("sil", help="İş ortağının anahtar(lar)ını iptal et")
    s.add_argument("--ad", required=True)
    arg = ayr.parse_args(argv)

    veri = _dosya_oku(dosya)
    if arg.komut == "yeni":
        anahtar = yeni_anahtar()
        veri[anahtar_ozeti(anahtar)] = {"ad": arg.ad, "gunluk_kota": arg.kota,
                                        "dakika_siniri": arg.dakika}
        anahtarlari_yukle(json.dumps(veri))          # yazmadan önce doğrula
        _dosya_yaz(dosya, veri)
        print(f"İş ortağı: {arg.ad} · günlük kota {arg.kota} · dakikada {arg.dakika}")
        print("\nAPI ANAHTARI (yalnızca şimdi gösterilir; güvenli bir kanaldan iletin):")
        print(f"  {anahtar}\n")
        print(f"Kaydedildi: {dosya.name} (yalnızca özeti).")
        print("Bulut ortamı için API_ANAHTARLARI değişkenine şu JSON'u yazın:")
        print(json.dumps(veri, ensure_ascii=False))
    elif arg.komut == "liste":
        if not veri:
            print("Kayıtlı iş ortağı yok.")
        for ozet, b in veri.items():
            print(f"- {b['ad']} · kota {b.get('gunluk_kota')} · dakika "
                  f"{b.get('dakika_siniri')} · özet {ozet[:10]}…")
    elif arg.komut == "sil":
        kalan = {o: b for o, b in veri.items() if b.get("ad") != arg.ad}
        silinen = len(veri) - len(kalan)
        _dosya_yaz(dosya, kalan)
        print(f"{silinen} anahtar iptal edildi." if silinen else "Bu adla anahtar yok.")
        if silinen:
            print("Bulut ortamındaysa API_ANAHTARLARI değişkenini de güncelleyin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
