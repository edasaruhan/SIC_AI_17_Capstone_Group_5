# -*- coding: utf-8 -*-
"""
Üretken Kadın — firmaların API anahtarı başvuruları

  • "Firmalar için API" sayfasındaki form buraya yazar; başvurular hesaplarla aynı veritabanındadır
    (Neon ya da yerel SQLite — hesap.motor()).
  • Anahtar otomatik VERİLMEZ: proje ekibi başvuruyu inceler, uygun görürse api_guvenlik.py ile
    anahtar üretip firmaya iletir. Böylece Gemini kotası ve etik kullanım kontrol altında kalır.
  • Kötüye kullanıma karşı: aynı e-postadan 24 saatte en fazla 3, toplamda 24 saatte en fazla 50 başvuru.
  • Başvuruları yalnızca YONETICI_EPOSTALARI ortam değişkenindeki hesaplar görür (Hesabım sayfası).

Proje ekibi için komut satırı:
    python src/basvuru.py liste
    python src/basvuru.py durum --id <başvuru no> --durum onaylandi
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import sqlalchemy as sa

import hesap

KURUM_TURLERI = ["E-ticaret / pazaryeri", "Kooperatif / birlik", "Belediye / kamu kurumu",
                 "Sivil toplum / vakıf", "Girişimcilik programı / kuluçka", "Diğer"]
AYLIK_HACIMLER = ["100'den az", "100 – 1.000", "1.000 – 10.000", "10.000'den fazla", "Henüz bilmiyorum"]
DURUMLAR = {"yeni": "🆕 Yeni", "gorusuluyor": "💬 Görüşülüyor", "onaylandi": "✅ Onaylandı",
            "reddedildi": "✖️ Reddedildi"}
EPOSTA_GUNLUK_SINIR, GENEL_GUNLUK_SINIR = 3, 50
_WEB = re.compile(r"^(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?$", re.IGNORECASE)

_metadata = sa.MetaData()
basvurular = sa.Table(
    "api_basvurulari", _metadata,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("olusturma", sa.DateTime(timezone=True), nullable=False),
    sa.Column("kurum", sa.String(120), nullable=False),
    sa.Column("kurum_turu", sa.String(60), nullable=False),
    sa.Column("yetkili", sa.String(80), nullable=False),
    sa.Column("eposta", sa.String(254), nullable=False, index=True),
    sa.Column("web", sa.String(200)),
    sa.Column("amac", sa.Text, nullable=False),
    sa.Column("aylik_hacim", sa.String(40), nullable=False),
    sa.Column("kvkk_onay", sa.DateTime(timezone=True), nullable=False),
    sa.Column("durum", sa.String(20), nullable=False, default="yeni"),
)
_HAZIR: set[int] = set()


@dataclass(frozen=True)
class Basvuru:
    id: str
    olusturma: datetime
    kurum: str
    kurum_turu: str
    yetkili: str
    eposta: str
    web: str
    amac: str
    aylik_hacim: str
    durum: str


def _m(m: sa.Engine | None) -> sa.Engine:
    m = m or hesap.motor()
    if id(m) not in _HAZIR:
        _metadata.create_all(m)
        _HAZIR.add(id(m))
    return m


def _metin(deger: str, alan: str, en_az: int, en_fazla: int) -> str:
    deger = " ".join((deger or "").split())
    if len(deger) < en_az:
        raise ValueError(f"{alan} alanını doldurun" + (f" (en az {en_az} karakter)." if en_az > 2 else "."))
    return deger[:en_fazla]


def basvuru_yap(kurum: str, kurum_turu: str, yetkili: str, eposta: str, web: str, amac: str,
                aylik_hacim: str, kvkk_onay: bool, m: sa.Engine | None = None) -> str:
    """Başvuruyu kaydeder, başvuru numarasını (ilk 8 karakter) döndürür. Hatalı girdide ValueError."""
    if not kvkk_onay:
        raise ValueError("Devam etmek için aydınlatma metnini onaylayın.")
    kurum = _metin(kurum, "Kurum adı", 2, 120)
    yetkili = _metin(yetkili, "Yetkili adı", 2, 80)
    eposta = hesap.eposta_duzelt(eposta)
    amac = (amac or "").strip()
    if len(amac) < 30:
        raise ValueError("Kullanım amacınızı biraz daha açık yazın (en az 30 karakter).")
    amac = amac[:2000]
    web = (web or "").strip()[:200]
    if web and not _WEB.match(web):
        raise ValueError("Web sitesi adresi geçerli görünmüyor (ör. www.ornek.com).")
    if kurum_turu not in KURUM_TURLERI:
        raise ValueError("Kurum türünü seçin.")
    if aylik_hacim not in AYLIK_HACIMLER:
        raise ValueError("Tahmini kullanım miktarını seçin.")

    simdi = hesap._simdi()
    m = _m(m)
    with m.begin() as b:
        dun = simdi - timedelta(hours=24)
        say = sa.select(sa.func.count()).select_from(basvurular).where(basvurular.c.olusturma > dun)
        if b.execute(say.where(basvurular.c.eposta == eposta)).scalar_one() >= EPOSTA_GUNLUK_SINIR:
            raise ValueError("Bu e-postayla bugün zaten başvuru yapılmış; ekibimiz en kısa sürede dönecek.")
        if b.execute(say).scalar_one() >= GENEL_GUNLUK_SINIR:
            raise ValueError("Şu an çok fazla başvuru var; lütfen yarın tekrar deneyin.")
        kimlik = uuid.uuid4().hex
        b.execute(basvurular.insert().values(
            id=kimlik, olusturma=simdi, kurum=kurum, kurum_turu=kurum_turu, yetkili=yetkili, eposta=eposta,
            web=web or None, amac=amac, aylik_hacim=aylik_hacim, kvkk_onay=simdi, durum="yeni"))
    return kimlik[:8].upper()


def liste(m: sa.Engine | None = None) -> list[Basvuru]:
    with _m(m).connect() as b:
        satirlar = b.execute(sa.select(basvurular).order_by(basvurular.c.olusturma.desc())).mappings().all()
    return [Basvuru(s["id"], hesap._utc(s["olusturma"]), s["kurum"], s["kurum_turu"], s["yetkili"],
                    s["eposta"], s["web"] or "", s["amac"], s["aylik_hacim"], s["durum"]) for s in satirlar]


def _kimlikle(b, kimlik: str) -> str:
    kimlik = (kimlik or "").strip().lower()
    if len(kimlik) < 8:
        raise ValueError("Başvuru numarası en az 8 karakter olmalı.")
    idler = b.execute(sa.select(basvurular.c.id).where(basvurular.c.id.like(kimlik + "%"))).scalars().all()
    if len(idler) != 1:
        raise ValueError("Başvuru bulunamadı.")
    return idler[0]


def durum_degistir(kimlik: str, durum: str, m: sa.Engine | None = None) -> None:
    if durum not in DURUMLAR:
        raise ValueError(f"Durum şunlardan biri olmalı: {', '.join(DURUMLAR)}")
    with _m(m).begin() as b:
        b.execute(basvurular.update().where(basvurular.c.id == _kimlikle(b, kimlik)).values(durum=durum))


def sil(kimlik: str, m: sa.Engine | None = None) -> None:
    """KVKK: işi biten ya da silinmesi istenen başvuruyu kalıcı olarak siler."""
    with _m(m).begin() as b:
        b.execute(basvurular.delete().where(basvurular.c.id == _kimlikle(b, kimlik)))


def yonetici_mi(eposta: str | None) -> bool:
    """Başvuruları görebilecek hesaplar: YONETICI_EPOSTALARI (virgülle ayrılmış; kodda e-posta tutulmaz)."""
    yoneticiler = {e.strip().lower() for e in os.getenv("YONETICI_EPOSTALARI", "").split(",") if e.strip()}
    return bool(eposta) and eposta.lower() in yoneticiler


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv
    load_dotenv(hesap.KOK / ".env")
    ayr = argparse.ArgumentParser(description="Üretken Kadın API başvuruları")
    alt = ayr.add_subparsers(dest="komut", required=True)
    alt.add_parser("liste", help="Başvuruları listele")
    d = alt.add_parser("durum", help="Başvurunun durumunu değiştir")
    d.add_argument("--id", required=True)
    d.add_argument("--durum", required=True, choices=list(DURUMLAR))
    arg = ayr.parse_args(argv)
    if arg.komut == "liste":
        for x in liste():
            print(f"[{x.id[:8].upper()}] {x.olusturma:%d.%m.%Y} {DURUMLAR[x.durum]} · {x.kurum} ({x.kurum_turu}) · "
                  f"{x.yetkili} <{x.eposta}> · {x.aylik_hacim}\n    {x.amac}")
    else:
        durum_degistir(arg.id, arg.durum)
        print("Güncellendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
