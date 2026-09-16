# -*- coding: utf-8 -*-
"""
Üretken Kadın — kullanıcı hesapları ve kalıcı veriler

  • E-posta + şifre ile kayıt ve giriş. Şifre düz metin SAKLANMAZ: hashlib.scrypt özeti tutulur
    (N=2^14, r=8, p=1, kullanıcı başına 16 baytlık rastgele tuz); karşılaştırma sabit sürelidir.
  • Kaba kuvvete karşı: aynı hesaba art arda 5 hatalı denemeden sonra 15 dakika kilit.
    Kayıtlı olmayan e-postada da aynı mesaj ve benzer süre: hesabın varlığı anlaşılmaz.
  • İçerikler, paylaşım takvimi, ton profili ve fiyatlar tek bir JSON belgesi olarak saklanır;
    biçim takvim.disa_aktar / ice_aktar ile aynıdır (aynı doğrulama kuralları). Fotoğraf ve ses saklanmaz.
  • Veritabanı: DATABASE_URL (Neon Postgres) tanımlıysa o; değilse yerel SQLite dosyası
    (geliştirme ve testler için — Render'da kalıcı değildir). SQLAlchemy Core ile aynı kod ikisinde çalışır.
  • KVKK m.11: kullanıcı verilerini indirebilir, hesabını tüm verileriyle kalıcı olarak silebilir.

Proje ekibi için komut satırı (şifresini unutan kullanıcıya geçici şifre):
    python src/hesap.py gecici-sifre --eposta ornek@alan.com
    python src/hesap.py sayi
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa

import takvim

KOK = Path(__file__).resolve().parent.parent
MAKS_DENEME = 5
KILIT_SURESI = timedelta(minutes=15)
SIFRE_EN_AZ, SIFRE_EN_FAZLA = 8, 128
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
_EPOSTA = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)*\.[^@\s.]{2,}$")
_ZAYIF_SIFRELER = {"12345678", "123456789", "1234567890", "password", "password1", "qwerty123",
                   "11111111", "abcdefgh", "sifre123", "şifre123", "parola123", "asdfghjk"}
GENEL_GIRIS_HATASI = "E-posta ya da şifre hatalı."

metadata = sa.MetaData()
kullanicilar = sa.Table(
    "kullanicilar", metadata,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("eposta", sa.String(254), nullable=False, unique=True),
    sa.Column("ad", sa.String(60), nullable=False),
    sa.Column("sifre_ozeti", sa.String(200), nullable=False),
    sa.Column("olusturma", sa.DateTime(timezone=True), nullable=False),
    sa.Column("kvkk_onay", sa.DateTime(timezone=True), nullable=False),
    sa.Column("son_giris", sa.DateTime(timezone=True)),
    sa.Column("hatali_deneme", sa.Integer, nullable=False, default=0),
    sa.Column("kilit_bitis", sa.DateTime(timezone=True)),
)
kullanici_verileri = sa.Table(
    "kullanici_verileri", metadata,
    sa.Column("kullanici_id", sa.String(32), sa.ForeignKey("kullanicilar.id", ondelete="CASCADE"),
              primary_key=True),
    sa.Column("belge", sa.Text, nullable=False),
    sa.Column("guncelleme", sa.DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class Kullanici:
    id: str
    eposta: str
    ad: str
    olusturma: datetime


# ---------------------------------------------------------------------------
# Veritabanı bağlantısı
# ---------------------------------------------------------------------------
def db_adresi() -> str:
    adres = os.getenv("DATABASE_URL", "").strip()
    if not adres:
        yol = Path(os.getenv("HESAP_DB_YOLU") or (KOK / "data" / "yerel.db"))
        yol.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{yol.as_posix()}"
    if adres.startswith("postgres://"):
        adres = "postgresql://" + adres[len("postgres://"):]
    if adres.startswith("postgresql://"):
        adres = "postgresql+psycopg://" + adres[len("postgresql://"):]
    return adres


def kalici_mi() -> bool:
    """Neon gibi dış bir veritabanı mı kullanılıyor? (Yerel SQLite Render'da yeniden kurulumda silinir.)"""
    return not db_adresi().startswith("sqlite")


@lru_cache(maxsize=8)
def _motor(adres: str) -> sa.Engine:
    if adres.startswith("sqlite"):
        motor = sa.create_engine(adres, connect_args={"check_same_thread": False})

        @sa.event.listens_for(motor, "connect")
        def _yabanci_anahtarlar(baglanti, _kayit):
            baglanti.execute("PRAGMA foreign_keys=ON")
    else:
        # Neon: kullanılmayınca uyur; pre_ping kopmuş bağlantıyı yeniler. Render'da bellek az: küçük havuz.
        motor = sa.create_engine(adres, pool_pre_ping=True, pool_size=2, max_overflow=2, pool_recycle=280)
    metadata.create_all(motor)
    return motor


def motor() -> sa.Engine:
    return _motor(db_adresi())


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def _utc(deger: datetime | None) -> datetime | None:
    """SQLite saat dilimini saklamaz; okunan zamanı UTC olarak yorumla."""
    if deger is None:
        return None
    return deger if deger.tzinfo else deger.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Şifre ve doğrulama
# ---------------------------------------------------------------------------
def sifre_ozeti(sifre: str) -> str:
    tuz = secrets.token_bytes(16)
    ozet = hashlib.scrypt(sifre.encode("utf-8"), salt=tuz, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${tuz.hex()}${ozet.hex()}"


def sifre_dogru_mu(sifre: str, kayitli: str) -> bool:
    try:
        ad, n, r, p, tuz, ozet = kayitli.split("$")
        if ad != "scrypt":
            return False
        beklenen = bytes.fromhex(ozet)
        hesap = hashlib.scrypt(sifre.encode("utf-8"), salt=bytes.fromhex(tuz), n=int(n), r=int(r),
                               p=int(p), dklen=len(beklenen))
        return hmac.compare_digest(hesap, beklenen)
    except (ValueError, TypeError, AttributeError):
        return False


@lru_cache(maxsize=1)
def _sahte_ozet() -> str:
    return sifre_ozeti(secrets.token_urlsafe(12))


def eposta_duzelt(eposta: str) -> str:
    eposta = (eposta or "").strip().lower()
    if len(eposta) > 254 or not _EPOSTA.match(eposta):
        raise ValueError("Geçerli bir e-posta adresi yazın.")
    return eposta


def sifre_kontrol(sifre: str, eposta: str = "") -> None:
    if not sifre or len(sifre) < SIFRE_EN_AZ:
        raise ValueError(f"Şifre en az {SIFRE_EN_AZ} karakter olmalı.")
    if len(sifre) > SIFRE_EN_FAZLA:
        raise ValueError(f"Şifre en fazla {SIFRE_EN_FAZLA} karakter olabilir.")
    if sifre.lower() in _ZAYIF_SIFRELER or len(set(sifre)) < 4:
        raise ValueError("Bu şifre çok kolay tahmin edilir; harf ve rakam karışık, daha güçlü bir şifre seçin.")
    if eposta and sifre.lower() in (eposta.lower(), eposta.split("@")[0].lower()):
        raise ValueError("Şifre e-posta adresinizle aynı olmamalı.")


def _kullanici(satir) -> Kullanici:
    return Kullanici(satir["id"], satir["eposta"], satir["ad"], _utc(satir["olusturma"]))


# ---------------------------------------------------------------------------
# Kayıt, giriş, şifre
# ---------------------------------------------------------------------------
def kayit_ol(eposta: str, ad: str, sifre: str, sifre_tekrar: str, kvkk_onay: bool,
             m: sa.Engine | None = None) -> Kullanici:
    if not kvkk_onay:
        raise ValueError("Devam etmek için aydınlatma metnini onaylayın.")
    eposta = eposta_duzelt(eposta)
    ad = " ".join((ad or "").split())[:60]
    if len(ad) < 2:
        raise ValueError("Adınızı yazın (en az 2 harf).")
    if sifre != sifre_tekrar:
        raise ValueError("Şifreler birbirini tutmuyor.")
    sifre_kontrol(sifre, eposta)
    simdi = _simdi()
    kayit = {"id": uuid.uuid4().hex, "eposta": eposta, "ad": ad, "sifre_ozeti": sifre_ozeti(sifre),
             "olusturma": simdi, "kvkk_onay": simdi, "son_giris": simdi, "hatali_deneme": 0}
    try:
        with (m or motor()).begin() as b:
            b.execute(kullanicilar.insert().values(**kayit))
    except sa.exc.IntegrityError:
        raise ValueError("Bu e-posta ile bir hesap zaten var. Giriş yapmayı deneyin.") from None
    return Kullanici(kayit["id"], eposta, ad, simdi)


def giris_yap(eposta: str, sifre: str, m: sa.Engine | None = None) -> Kullanici:
    try:
        eposta = eposta_duzelt(eposta)
    except ValueError:
        raise ValueError(GENEL_GIRIS_HATASI) from None
    simdi, hata, sonuc = _simdi(), None, None
    with (m or motor()).begin() as b:                       # hatalı deneme sayacı işlensin diye
        satir = b.execute(sa.select(kullanicilar).where(kullanicilar.c.eposta == eposta)).mappings().first()
        if satir is None:
            sifre_dogru_mu(sifre or "", _sahte_ozet())      # süre farkından hesap varlığı anlaşılmasın
            hata = GENEL_GIRIS_HATASI
        elif _utc(satir["kilit_bitis"]) and _utc(satir["kilit_bitis"]) > simdi:
            dakika = int((_utc(satir["kilit_bitis"]) - simdi).total_seconds() // 60) + 1
            hata = f"Çok fazla hatalı deneme yapıldı. {dakika} dakika sonra tekrar deneyin."
        elif not sifre_dogru_mu(sifre or "", satir["sifre_ozeti"]):
            deneme = satir["hatali_deneme"] + 1
            kilitle = deneme >= MAKS_DENEME
            b.execute(kullanicilar.update().where(kullanicilar.c.id == satir["id"]).values(
                hatali_deneme=0 if kilitle else deneme, kilit_bitis=simdi + KILIT_SURESI if kilitle else None))
            hata = (f"Çok fazla hatalı deneme yapıldı. {KILIT_SURESI.seconds // 60} dakika sonra tekrar deneyin."
                    if kilitle else GENEL_GIRIS_HATASI)
        else:
            b.execute(kullanicilar.update().where(kullanicilar.c.id == satir["id"]).values(
                hatali_deneme=0, kilit_bitis=None, son_giris=simdi))
            sonuc = _kullanici(satir)
    if hata:
        raise ValueError(hata)
    return sonuc


def _sifreyi_dogrula(b, kullanici_id: str, sifre: str):
    satir = b.execute(sa.select(kullanicilar).where(kullanicilar.c.id == kullanici_id)).mappings().first()
    if satir is None:
        raise ValueError("Hesap bulunamadı.")
    if not sifre_dogru_mu(sifre or "", satir["sifre_ozeti"]):
        raise ValueError("Mevcut şifreniz hatalı.")
    return satir


def sifre_degistir(kullanici_id: str, eski: str, yeni: str, yeni_tekrar: str,
                   m: sa.Engine | None = None) -> None:
    with (m or motor()).begin() as b:
        satir = _sifreyi_dogrula(b, kullanici_id, eski)
        if yeni != yeni_tekrar:
            raise ValueError("Yeni şifreler birbirini tutmuyor.")
        sifre_kontrol(yeni, satir["eposta"])
        b.execute(kullanicilar.update().where(kullanicilar.c.id == kullanici_id).values(
            sifre_ozeti=sifre_ozeti(yeni)))


def gecici_sifre_ata(eposta: str, m: sa.Engine | None = None) -> str:
    """Proje ekibi için: şifresini unutan kullanıcıya geçici şifre (bir kez gösterilir)."""
    eposta = eposta_duzelt(eposta)
    gecici = secrets.token_urlsafe(9)
    with (m or motor()).begin() as b:
        sonuc = b.execute(kullanicilar.update().where(kullanicilar.c.eposta == eposta).values(
            sifre_ozeti=sifre_ozeti(gecici), hatali_deneme=0, kilit_bitis=None))
        if sonuc.rowcount == 0:
            raise ValueError("Bu e-posta ile kayıtlı hesap yok.")
    return gecici


def hesabi_sil(kullanici_id: str, sifre: str, m: sa.Engine | None = None) -> None:
    """KVKK m.11: hesabı ve tüm verilerini kalıcı olarak siler."""
    with (m or motor()).begin() as b:
        _sifreyi_dogrula(b, kullanici_id, sifre)
        b.execute(kullanici_verileri.delete().where(kullanici_verileri.c.kullanici_id == kullanici_id))
        b.execute(kullanicilar.delete().where(kullanicilar.c.id == kullanici_id))


def kullanici_sayisi(m: sa.Engine | None = None) -> int:
    with (m or motor()).connect() as b:
        return b.execute(sa.select(sa.func.count()).select_from(kullanicilar)).scalar_one()


# ---------------------------------------------------------------------------
# Kalıcı veriler
# ---------------------------------------------------------------------------
_OZET_ANI = datetime(2000, 1, 1, tzinfo=takvim.TR)


def belge(gecmis: list[dict], plan: list, uslup: list[str] | None) -> str:
    return takvim.disa_aktar(gecmis, plan, uslup)


def degisiklik_ozeti(gecmis: list[dict], plan: list, uslup: list[str] | None) -> str:
    """Kaydetme zamanından bağımsız özet: yalnızca içerik değişince farklıdır (gereksiz yazma olmasın)."""
    return hashlib.sha256(takvim.disa_aktar(gecmis, plan, uslup, an=_OZET_ANI).encode("utf-8")).hexdigest()


def verileri_kaydet(kullanici_id: str, belge_metni: str, m: sa.Engine | None = None) -> None:
    if len(belge_metni.encode("utf-8")) > takvim.MAKS_DOSYA_BAYT:
        raise ValueError("Kaydedilecek veri çok büyük; bazı eski içerikleri silin.")
    simdi = _simdi()
    with (m or motor()).begin() as b:
        sonuc = b.execute(kullanici_verileri.update().where(kullanici_verileri.c.kullanici_id == kullanici_id)
                          .values(belge=belge_metni, guncelleme=simdi))
        if sonuc.rowcount == 0:
            b.execute(kullanici_verileri.insert().values(kullanici_id=kullanici_id, belge=belge_metni,
                                                         guncelleme=simdi))


def verileri_yukle(kullanici_id: str, m: sa.Engine | None = None) -> tuple[list[dict], list, list[str]]:
    with (m or motor()).connect() as b:
        metin = b.execute(sa.select(kullanici_verileri.c.belge)
                          .where(kullanici_verileri.c.kullanici_id == kullanici_id)).scalar_one_or_none()
    if not metin:
        return [], [], []
    icerikler, plan, uslup, _ = takvim.ice_aktar(metin)
    return icerikler, plan, uslup


# ---------------------------------------------------------------------------
# Komut satırı (proje ekibi)
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv
    load_dotenv(KOK / ".env")
    ayr = argparse.ArgumentParser(description="Üretken Kadın hesap yönetimi")
    alt = ayr.add_subparsers(dest="komut", required=True)
    g = alt.add_parser("gecici-sifre", help="Şifresini unutan kullanıcıya geçici şifre ata")
    g.add_argument("--eposta", required=True)
    alt.add_parser("sayi", help="Kayıtlı hesap sayısı")
    arg = ayr.parse_args(argv)
    print("Veritabanı:", "kalıcı (DATABASE_URL)" if kalici_mi() else "yerel SQLite")
    if arg.komut == "gecici-sifre":
        print("Geçici şifre (yalnızca şimdi gösterilir; kullanıcıya güvenli yoldan iletin):")
        print("  " + gecici_sifre_ata(arg.eposta))
        print("Kullanıcı giriş yaptıktan sonra Hesabım sayfasından şifresini değiştirmeli.")
    elif arg.komut == "sayi":
        print("Kayıtlı hesap:", kullanici_sayisi())
    return 0


if __name__ == "__main__":
    sys.exit(main())
