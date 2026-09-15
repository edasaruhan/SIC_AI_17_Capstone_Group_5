# -*- coding: utf-8 -*-
"""
Üretken Kadın — iş ortakları için REST API (FastAPI)

Streamlit arayüzüyle aynı çekirdeği kullanır (uret, prompts, kalite, trends, takvim).
E-ticaret platformları, kooperatif ağları ve pazaryeri entegrasyonları içindir.

Yerelde çalıştırma:
    uvicorn api:app --app-dir src --reload        → http://127.0.0.1:8000/docs

İş ortağı rehberi, kota, hata kodları ve yayına alma: API.md
"""

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, Query, Request, Response, Security, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

import api_guvenlik as guv
import kalite
import prompts
import takvim
import trends
import uret

SURUM = "1.0.0"
MAKS_GOVDE_BAYT = 12 * 1024 * 1024
MAKS_SES_BAYT = 10 * 1024 * 1024
# Gemini'nin desteklediği ses türleri; tarayıcı/istemci takma adları eşlenir.
SES_TURLERI = {
    "audio/wav": "audio/wav", "audio/x-wav": "audio/wav", "audio/wave": "audio/wav",
    "audio/mpeg": "audio/mp3", "audio/mp3": "audio/mp3",
    "audio/aiff": "audio/aiff", "audio/x-aiff": "audio/aiff",
    "audio/aac": "audio/aac", "audio/ogg": "audio/ogg",
    "audio/flac": "audio/flac", "audio/x-flac": "audio/flac",
}
YZ_UYARISI = ("Bu içerik yapay zekâ ile üretildi; yayımlanmadan önce üretici tarafından "
              "okunup onaylanmalıdır.")
KALITE_NOTU = ("Kalite modeli prototip etiketli veriyle eğitilmiştir; kesin karar değil, "
               "gözden geçirme önceliği için ön filtredir.")
ORNEK_ANLATIM = ("El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, "
                 "tamamen elde örüyorum. Bir tanesi yaklaşık üç günümü alıyor.")

log = logging.getLogger("uretken_kadin.api")
if not log.handlers:
    _isleyici = logging.StreamHandler()
    _isleyici.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_isleyici)
    log.setLevel(logging.INFO)
    log.propagate = False

# Tek kaynak: kategoriler ve kanallar çekirdek modüllerden gelir.
Kategori = Literal[tuple(prompts.KATEGORI_KELIMELERI)]
Kanal = Literal[tuple(takvim.KANALLAR)]
KisaMetin = Annotated[str, Field(max_length=1000)]


# ---------------------------------------------------------------------------
# İstek / yanıt şemaları
# ---------------------------------------------------------------------------
class _Istek(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class IcerikIstegi(_Istek):
    anlatim: str = Field(min_length=20, max_length=4000, examples=[ORNEK_ANLATIM],
                         description="Üreticinin kendi anlatımı. Sesli anlatım için önce "
                                     "/v1/transkript. Ad, telefon, adres göndermeyin.")
    kategori: Kategori
    ozenli: bool = Field(False, description="Daha yavaş ama daha özenli model")
    uslup_ornekleri: list[KisaMetin] = Field(
        default_factory=list, max_length=3,
        description="Üreticinin daha önce yazdığı metinler; içerik bu üslupla yazılır")
    anahtar_kelimeler: list[Annotated[str, Field(min_length=2, max_length=60)]] | None = Field(
        None, max_length=10,
        description="Verilmezse Google Trends'ten (7 gün önbellekli) çekilir")
    trends_kullan: bool = Field(True, description="False ise sabit kategori kelimeleri kullanılır")
    kalite_dahil: bool = Field(True, description="Yanıta kalite ön filtresi eklensin mi")


class Metrikler(BaseModel):
    seo_kapsami: int = Field(description="Metinlerde geçen anahtar kelime sayısı")
    anahtar_kelime_sayisi: int
    klise_sayisi: int = Field(description="Klişe kalıp sayısı; düşük olması iyidir")
    kanal_benzerligi: float = Field(description="Instagram ve Shopier metinlerinin benzerliği "
                                                "(0-1); düşük olması iyidir")


class KaliteSonucu(BaseModel):
    hazir: bool | None = Field(description="True: onaya hazır, False: gözden geçirilmeli")
    olasilik: float | None
    etiket: str
    gerekceler: list[str]


class IcerikYaniti(BaseModel):
    instagram: str
    shopier: str
    model: str = Field(description="Yanıtı fiilen üreten model")
    anahtar_kelimeler: list[str]
    anahtar_kelime_kaynagi: str = Field(description="istek | trends | önbellek | varsayılan | sabit")
    metrikler: Metrikler
    kalite: KaliteSonucu | None
    uyari: str


class FormatIstegi(_Istek):
    anlatim: str = Field(min_length=20, max_length=4000, examples=[ORNEK_ANLATIM])
    kategori: Kategori
    bicim: Literal["story", "whatsapp", "hashtag", "reels", "foto"] = Field(
        description="story: 3 karelik hikâye · whatsapp: durum + müşteri mesajı · hashtag: "
                    "süzgeçten geçmiş hashtag seti · reels: video çekim planı · foto: "
                    "fotoğraf rehberi")
    ozenli: bool = False
    uslup_ornekleri: list[KisaMetin] = Field(default_factory=list, max_length=3)
    trends_kullan: bool = Field(True, description="Hashtag setinde arama kelimeleri kullanılsın mı")


class FormatYaniti(BaseModel):
    bicim: str
    metin: str = Field(description="Markdown")
    uyari: str


class KaliteIstegi(_Istek):
    metin: str = Field(min_length=1, max_length=8000)
    kategori: Kategori


class KaliteYaniti(KaliteSonucu):
    oznitelikler: dict[str, float]
    aciklama: str


class AnahtarKelimeYaniti(BaseModel):
    kategori: str
    kelimeler: list[str]
    kaynak: str = Field(description="trends | önbellek | varsayılan")


class TranskriptYaniti(BaseModel):
    metin: str
    uyari: str


class TakvimOgesi(_Istek):
    zaman: datetime = Field(description="ISO 8601. Saat dilimi yoksa Türkiye saati (UTC+3)")
    kanal: Kanal
    baslik: str = Field(min_length=1, max_length=120)
    metin: str = Field("", max_length=6000, description="Hatırlatmanın içine konacak metin")


class TakvimIstegi(_Istek):
    ogeler: list[TakvimOgesi] = Field(min_length=1, max_length=100)
    hatirlatma_dk: int = Field(takvim.HATIRLATMA_DK, ge=0, le=1440)


class KullanimYaniti(BaseModel):
    is_ortagi: str
    gunluk_kota: int
    bugun_kullanilan: int
    kalan: int
    dakika_siniri: int
    sifirlanma: datetime


class SaglikYaniti(BaseModel):
    durum: str
    surum: str


class HataAyrintisi(BaseModel):
    kod: str
    mesaj: str


class HataYaniti(BaseModel):
    hata: HataAyrintisi


HATALAR = {
    401: {"model": HataYaniti, "description": "API anahtarı yok ya da geçersiz"},
    422: {"model": HataYaniti, "description": "İstek doğrulanamadı"},
    429: {"model": HataYaniti, "description": "Günlük kota ya da dakikalık sınır aşıldı"},
    503: {"model": HataYaniti, "description": "Yapay zekâ modeli geçici olarak yoğun"},
}


class ApiHatasi(Exception):
    def __init__(self, durum: int, kod: str, mesaj: str, basliklar: dict | None = None):
        super().__init__(mesaj)
        self.durum, self.kod, self.mesaj, self.basliklar = durum, kod, mesaj, basliklar or {}


def _hata_yaniti(durum: int, kod: str, mesaj: str, basliklar: dict | None = None,
                 ayrintilar: list | None = None) -> JSONResponse:
    govde = {"hata": {"kod": kod, "mesaj": mesaj}}
    if ayrintilar:
        govde["hata"]["ayrintilar"] = ayrintilar
    return JSONResponse(govde, status_code=durum, headers=basliklar)


def _kalite_tahmini(metin: str, kategori: str) -> KaliteSonucu | None:
    try:
        model = kalite.model_al()
        return KaliteSonucu(**model.tahmin(metin, kategori)) if model.mevcut() else None
    except Exception as hata:              # ön filtre yoksa içerik yine döner
        log.warning("kalite tahmini atlandı: %s", type(hata).__name__)
        return None


def _kalite_isit() -> None:
    """Kalite modeli ilk kullanımda eğitilir (birkaç sn); ilk isteği bekletmemek için."""
    try:
        kalite.model_al()
    except Exception as hata:
        log.warning("kalite modeli ön yüklenemedi: %s", type(hata).__name__)


ACIKLAMA = """
Üretici kadınların kendi anlatımını **Instagram gönderisi + Shopier açıklamasına**,
hikâye / WhatsApp / hashtag formatlarına ve paylaşım takvimine çeviren API.

- **Kimlik doğrulama:** her istekte `X-API-Key` başlığı (sağ üstteki *Authorize*).
- **Kota:** yapay zekâ çağıran uç noktalar günlük kotadan düşer; tüm istekler dakikalık
  sınıra tabidir. Yanıt başlıkları `X-Kota-Limit`, `X-Kota-Kalan`; aşımda `429` + `Retry-After`.
- **İnsan onayı:** üretilen her içerik yayımlanmadan önce üretici tarafından onaylanmalıdır.
- **KVKK:** istek gövdeleri (anlatım, ses) sunucuda saklanmaz ve günlüğe yazılmaz; üretim
  için Google Gemini API'ye iletilir (yurt dışına aktarım). Ayrıntı: API.md
"""

ETIKETLER = [
    {"name": "İçerik", "description": "Yapay zekâ ile metin üretimi (günlük kotadan düşer)"},
    {"name": "Analiz", "description": "Kalite ön filtresi ve arama kelimeleri (kotadan düşmez)"},
    {"name": "Ses", "description": "Sesli anlatımı yazıya dökme (açık rıza gerekir)"},
    {"name": "Takvim", "description": "Telefon takvimine eklenen .ics dosyası"},
    {"name": "Hesap", "description": "Kota kullanımı"},
    {"name": "Sistem", "description": "Sağlık kontrolü"},
]

_anahtar_basligi = APIKeyHeader(name="X-API-Key", auto_error=False,
                                description="İş ortağı API anahtarı")


# ---------------------------------------------------------------------------
def uygulama_olustur(anahtarlar: dict[str, guv.IsOrtagi] | None = None,
                     sayac: guv.Sayac | None = None) -> FastAPI:
    """Anahtarlar ve sayaç dışarıdan verilebilir (testler); verilmezse ortamdan okunur."""
    anahtarlar = guv.anahtarlari_yukle() if anahtarlar is None else anahtarlar
    sayac = sayac or guv.Sayac()
    if not anahtarlar:
        log.warning("Tanımlı API anahtarı yok: /v1 uç noktaları 401 döndürür (bkz. API.md).")

    @asynccontextmanager
    async def yasam(_app: FastAPI):
        if os.getenv("API_KALITE_ONYUKLE", "1") == "1":
            threading.Thread(target=_kalite_isit, daemon=True).start()
        yield

    app = FastAPI(title="Üretken Kadın API", version=SURUM, description=ACIKLAMA,
                  openapi_tags=ETIKETLER, lifespan=yasam)

    kaynaklar = [k.strip() for k in os.getenv("API_CORS_KAYNAKLARI", "").split(",") if k.strip()]
    if kaynaklar:
        app.add_middleware(CORSMiddleware, allow_origins=kaynaklar,
                           allow_methods=["GET", "POST"],
                           allow_headers=["X-API-Key", "Content-Type"],
                           expose_headers=["X-Kota-Limit", "X-Kota-Kalan", "Retry-After"])

    @app.middleware("http")
    async def boyut_ve_gunluk(request: Request, call_next):
        uzunluk = request.headers.get("content-length", "")
        if uzunluk.isdigit() and int(uzunluk) > MAKS_GOVDE_BAYT:
            return _hata_yaniti(413, "istek_cok_buyuk", "İstek gövdesi çok büyük.")
        baslangic = time.perf_counter()
        yanit = await call_next(request)
        # Gövde (anlatım, ses) ve anahtar ASLA günlüğe yazılmaz — KVKK veri minimizasyonu.
        log.info("%s %s %s ortak=%s %.0fms", request.method, request.url.path,
                 yanit.status_code, getattr(request.state, "is_ortagi", "-"),
                 (time.perf_counter() - baslangic) * 1000)
        return yanit

    @app.exception_handler(ApiHatasi)
    async def _api_hatasi(_request: Request, hata: ApiHatasi):
        return _hata_yaniti(hata.durum, hata.kod, hata.mesaj, hata.basliklar)

    @app.exception_handler(RequestValidationError)
    async def _dogrulama_hatasi(_request: Request, hata: RequestValidationError):
        # Pydantic hatalarındaki "input" alanı gönderilen anlatımı geri yansıtır; eklenmez.
        ayrintilar = [{"alan": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]),
                       "mesaj": e["msg"]} for e in hata.errors()]
        return _hata_yaniti(422, "gecersiz_istek", "İstek doğrulanamadı.", ayrintilar=ayrintilar)

    @app.exception_handler(Exception)
    async def _beklenmeyen(_request: Request, hata: Exception):
        log.error("beklenmeyen hata: %s", type(hata).__name__)
        return _hata_yaniti(500, "sunucu_hatasi", "Beklenmeyen bir hata oluştu.")

    # --- yardımcılar ------------------------------------------------------
    def dogrula(request: Request,
                anahtar: str | None = Security(_anahtar_basligi)) -> guv.IsOrtagi:
        if not anahtar:
            raise ApiHatasi(401, "anahtar_yok", "X-API-Key başlığı gerekli.")
        ortak = anahtarlar.get(guv.anahtar_ozeti(anahtar))
        if ortak is None:
            raise ApiHatasi(401, "anahtar_gecersiz", "API anahtarı geçersiz ya da iptal edilmiş.")
        request.state.is_ortagi = ortak.ad
        return ortak

    def harca(ortak: guv.IsOrtagi, response: Response, maliyet: int = 1) -> dict:
        """Doğrulamadan SONRA çağrılır: geçersiz istekler kotadan düşmez."""
        sonuc = sayac.dene(ortak, maliyet)
        basliklar = {"X-Kota-Limit": str(sonuc.limit), "X-Kota-Kalan": str(sonuc.kalan)}
        if not sonuc.izin:
            basliklar["Retry-After"] = str(sonuc.yeniden_dene_sn)
            if sonuc.neden == "gunluk":
                raise ApiHatasi(429, "kota_asildi", "Günlük kotanız doldu; Türkiye saatiyle "
                                                    "gece yarısı yenilenir.", basliklar)
            raise ApiHatasi(429, "hiz_siniri", "Dakikalık istek sınırını aştınız; biraz "
                                               "bekleyip tekrar deneyin.", basliklar)
        response.headers.update(basliklar)
        return basliklar

    def model_cagir(ortak: guv.IsOrtagi, fonk, maliyet: int = 1):
        """Çekirdek hatalarını iş ortağına anlamlı ve iç ayrıntı sızdırmayan kodlara çevirir."""
        try:
            return fonk()
        except ApiHatasi:
            raise
        except ValueError as hata:
            sayac.iade(ortak, maliyet)
            raise ApiHatasi(422, "gecersiz_istek", str(hata)) from None
        except Exception as hata:
            sayac.iade(ortak, maliyet)             # bizden kaynaklı: kota geri verilir
            log.warning("model çağrısı başarısız: %s", type(hata).__name__)
            if isinstance(hata, RuntimeError) and "GEMINI_API_KEY" in str(hata):
                raise ApiHatasi(500, "yapilandirma_hatasi", "Sunucu yapılandırması eksik.") from None
            if uret._gecici_hata_mi(hata):
                raise ApiHatasi(503, "model_yogun", "Yapay zekâ modeli şu an yoğun; biraz sonra "
                                                    "tekrar deneyin.", {"Retry-After": "30"}) from None
            raise ApiHatasi(502, "model_hatasi", "İçerik üretilemedi; tekrar deneyin.") from None

    # --- uç noktalar ------------------------------------------------------
    @app.get("/saglik", tags=["Sistem"], response_model=SaglikYaniti, summary="Sunucu ayakta mı?")
    def saglik():
        return SaglikYaniti(durum="ok", surum=SURUM)

    @app.post("/v1/icerik", tags=["İçerik"], response_model=IcerikYaniti, responses=HATALAR,
              summary="Anlatımdan Instagram gönderisi + Shopier açıklaması")
    def icerik(istek: IcerikIstegi, response: Response,
               ortak: guv.IsOrtagi = Depends(dogrula)):
        harca(ortak, response)

        def calistir():
            if istek.anahtar_kelimeler is not None:
                kelimeler, kaynak = list(istek.anahtar_kelimeler), "istek"
            elif istek.trends_kullan:
                trend = trends.trend_getir(istek.kategori)
                kelimeler, kaynak = list(trend.kelimeler), trend.kaynak
            else:
                kelimeler, kaynak = list(prompts.KATEGORI_KELIMELERI[istek.kategori]), "sabit"
            sonuc = uret.icerik_uret(anlatim=istek.anlatim, kategori=istek.kategori,
                                     anahtar_kelimeler=kelimeler, ozenli=istek.ozenli,
                                     uslup_ornekleri=istek.uslup_ornekleri or None)
            if sonuc.bos_mu():
                raise RuntimeError("boş yanıt")
            return sonuc, kelimeler, kaynak

        sonuc, kelimeler, kaynak = model_cagir(ortak, calistir)
        birlesik = f"{sonuc.instagram} {sonuc.shopier}"
        return IcerikYaniti(
            instagram=sonuc.instagram, shopier=sonuc.shopier, model=sonuc.model,
            anahtar_kelimeler=kelimeler, anahtar_kelime_kaynagi=kaynak,
            metrikler=Metrikler(
                seo_kapsami=uret.seo_kapsami(birlesik, kelimeler),
                anahtar_kelime_sayisi=len(kelimeler),
                klise_sayisi=uret.klise_sayisi(birlesik),
                kanal_benzerligi=round(uret.kanal_benzerligi(sonuc.instagram, sonuc.shopier), 3)),
            kalite=_kalite_tahmini(birlesik, istek.kategori) if istek.kalite_dahil else None,
            uyari=YZ_UYARISI)

    @app.post("/v1/format", tags=["İçerik"], response_model=FormatYaniti, responses=HATALAR,
              summary="Hikâye, WhatsApp, hashtag seti, video planı ya da fotoğraf rehberi")
    def format_uret(istek: FormatIstegi, response: Response,
                    ortak: guv.IsOrtagi = Depends(dogrula)):
        harca(ortak, response)
        uslup = istek.uslup_ornekleri or None

        def calistir():
            if istek.bicim == "reels":
                return uret.reels_uret(anlatim=istek.anlatim, kategori=istek.kategori,
                                       uslup_ornekleri=uslup, ozenli=istek.ozenli)
            if istek.bicim == "foto":
                return uret.foto_rehberi_uret(anlatim=istek.anlatim, kategori=istek.kategori,
                                              ozenli=istek.ozenli)
            return uret.ek_format_uret(anlatim=istek.anlatim, kategori=istek.kategori,
                                       bicim=istek.bicim, uslup_ornekleri=uslup,
                                       trends_kullan=istek.trends_kullan, ozenli=istek.ozenli)

        return FormatYaniti(bicim=istek.bicim, metin=model_cagir(ortak, calistir),
                            uyari=YZ_UYARISI)

    @app.post("/v1/kalite", tags=["Analiz"], response_model=KaliteYaniti, responses=HATALAR,
              summary="Hazır bir metnin kalite ön filtresi (onaya hazır mı?)")
    def kalite_olc(istek: KaliteIstegi, response: Response,
                   ortak: guv.IsOrtagi = Depends(dogrula)):
        harca(ortak, response, maliyet=0)
        model = kalite.model_al()
        if not model.mevcut():
            raise ApiHatasi(503, "kalite_modeli_yok", "Kalite modeli bu sunucuda kullanılamıyor.")
        return KaliteYaniti(**model.tahmin(istek.metin, istek.kategori),
                            oznitelikler=kalite.sayisal_oznitelikler(istek.metin, istek.kategori),
                            aciklama=KALITE_NOTU)

    @app.get("/v1/anahtar-kelimeler", tags=["Analiz"], response_model=AnahtarKelimeYaniti,
             responses=HATALAR, summary="Kategori için arama kelimeleri (Google Trends)")
    def anahtar_kelimeler(response: Response, kategori: Kategori = Query(),
                          adet: int = Query(6, ge=1, le=15),
                          ortak: guv.IsOrtagi = Depends(dogrula)):
        harca(ortak, response, maliyet=0)
        trend = trends.trend_getir(kategori, adet=adet)
        return AnahtarKelimeYaniti(kategori=kategori, kelimeler=list(trend.kelimeler),
                                   kaynak=trend.kaynak)

    @app.post("/v1/transkript", tags=["Ses"], response_model=TranskriptYaniti,
              responses={**HATALAR, 400: {"model": HataYaniti, "description": "Açık rıza yok"},
                         413: {"model": HataYaniti, "description": "Dosya çok büyük"},
                         415: {"model": HataYaniti, "description": "Desteklenmeyen ses türü"}},
              summary="Sesli anlatımı yazıya döker (konuşanın kelimeleri korunur)")
    def transkript(response: Response,
                   ses: UploadFile = File(description="wav, mp3, aiff, aac, ogg ya da flac; en fazla 10 MB"),
                   acik_riza: bool = Form(description="Konuşan kişiden sesinin yapay zekâ ile "
                                                      "işlenmesi için açık rıza alındı mı? (KVKK)"),
                   ortak: guv.IsOrtagi = Depends(dogrula)):
        if not acik_riza:
            raise ApiHatasi(400, "riza_gerekli", "Ses verisi için konuşan kişinin açık rızası "
                                                 "alınmış olmalı (KVKK); acik_riza=true gönderin.")
        tur = SES_TURLERI.get((ses.content_type or "").split(";")[0].strip().lower())
        if tur is None:
            raise ApiHatasi(415, "desteklenmeyen_ses",
                            "Desteklenen ses türleri: wav, mp3, aiff, aac, ogg, flac.")
        veri = ses.file.read(MAKS_SES_BAYT + 1)
        if len(veri) > MAKS_SES_BAYT:
            raise ApiHatasi(413, "ses_cok_buyuk",
                            f"Ses dosyası en fazla {MAKS_SES_BAYT // (1024 * 1024)} MB olabilir.")
        if not veri:
            raise ApiHatasi(422, "gecersiz_istek", "Ses dosyası boş.")
        harca(ortak, response)
        metin = model_cagir(ortak, lambda: uret.sesten_metne(veri, tur))
        return TranskriptYaniti(metin=metin, uyari="Metin yapay zekâ ile yazıya döküldü; "
                                                   "kullanmadan önce kontrol edin.")

    @app.post("/v1/takvim.ics", tags=["Takvim"], response_class=Response,
              responses={200: {"content": {"text/calendar": {}},
                               "description": "iCalendar dosyası"}, **HATALAR},
              summary="Paylaşım planından telefon takvimine eklenen .ics dosyası")
    def takvim_dosyasi(istek: TakvimIstegi, response: Response,
                       ortak: guv.IsOrtagi = Depends(dogrula)):
        basliklar = harca(ortak, response, maliyet=0)
        ogeler = [takvim.PlanOgesi(
            zaman=(o.zaman if o.zaman.tzinfo else o.zaman.replace(tzinfo=takvim.TR))
            .astimezone(takvim.TR).isoformat(),
            kanal=o.kanal, baslik=o.baslik, metin=o.metin) for o in istek.ogeler]
        return Response(takvim.ics_olustur(ogeler, hatirlatma_dk=istek.hatirlatma_dk),
                        media_type="text/calendar; charset=utf-8",
                        headers={**basliklar, "Content-Disposition":
                                 'attachment; filename="uretken_kadin_takvim.ics"'})

    @app.get("/v1/kullanim", tags=["Hesap"], response_model=KullanimYaniti,
             responses={401: HATALAR[401]}, summary="Bugünkü kota kullanımınız")
    def kullanim(ortak: guv.IsOrtagi = Depends(dogrula)):
        kullanilan = sayac.kullanilan(ortak)
        return KullanimYaniti(is_ortagi=ortak.ad, gunluk_kota=ortak.gunluk_kota,
                              bugun_kullanilan=kullanilan,
                              kalan=max(ortak.gunluk_kota - kullanilan, 0),
                              dakika_siniri=ortak.dakika_siniri,
                              sifirlanma=sayac.sifirlanma())

    return app


app = uygulama_olustur()
