# -*- coding: utf-8 -*-
"""
Üretken Kadın — Çekirdek üretim modülü

Üreticinin doğal anlatımını alır, Gemini'ye gönderir ve iki kanallı pazarlama
içeriği döndürür (Instagram gönderisi + Shopier ürün açıklaması).

Terminalden denemek için:
    python src/uret.py
"""

import json
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import types

import prompts

load_dotenv()

# Kullanilacak modeller (.env veya Streamlit secrets ile degistirilebilir).
# Secim, kendi orneklerimizle yaptigimiz karsilastirmaya dayanir (15.09.2026):
#   - MODEL (hizli, varsayilan): 3.5 Flash Lite ~1 sn; klise ve kanal ayrimi 3.6 ile
#     ayni, SEO kapsami daha dusuktu (prompt'taki kelime kurali ile desteklendi).
#   - MODEL_OZENLI: kullanici "Daha ozenli yaz" derse; 3.6 Flash daha yavas ama
#     SEO kapsami daha yuksek.
#   - MODEL_SES: ses -> metin. Sentetik kayit testinde 3.6 Flash konusanin
#     kelimelerini daha iyi korudu (%96/%96); Lite "kendim" -> "kendi" hatasi yapti.
# Google eski modelleri kapatabilir: "404 ... no longer available" hatasinda hata
# mesajinin onerdigi adi ilgili degiskene yazin.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MODEL_OZENLI = os.getenv("GEMINI_MODEL_OZENLI", "gemini-3.6-flash")
MODEL_SES = os.getenv("GEMINI_MODEL_SES", "gemini-3.6-flash")

# Hizli model disindaki (yavas olabilen) modeller icin bekleme siniri, saniye.
# Olcumlerimizde 3.6 Flash yaniti 16-65 sn arasinda degisti; sinir asilirsa istek
# hizli modele yonlendirilir ve kullanici bir dakika beklemez.
OZENLI_ZAMAN_ASIMI_SN = float(os.getenv("GEMINI_OZENLI_ZAMAN_ASIMI_SN", "30"))
SES_ZAMAN_ASIMI_SN = float(os.getenv("GEMINI_SES_ZAMAN_ASIMI_SN", "45"))

# Gemini API 10 sn'den kisa sinirlari "400 INVALID_ARGUMENT" ile reddeder.
_EN_KISA_SINIR_SN = 10.0

# Bu hatalarda istek diger modele bir kez yonlendirilir (yogunluk, kota, kapatilmis
# model, zaman asimi). Sure sunucuda dolarsa API "504 DEADLINE_EXCEEDED" dondurur.
_YEDEGE_GECIS_HATALARI = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                          "404", "NOT_FOUND", "504", "DEADLINE_EXCEEDED", "timed out")


# ---------------------------------------------------------------------------
@dataclass
class Icerik:
    """Üretilen içeriğin iki kanalı."""
    instagram: str
    shopier: str
    ham_yanit: str = ""      # ayrıştırma hatalarını incelemek için
    model: str = ""          # yanıtı fiilen üreten model (yedeğe geçiş görünür olsun)

    def bos_mu(self) -> bool:
        return not (self.instagram.strip() or self.shopier.strip())


# ---------------------------------------------------------------------------
def istemci_olustur() -> genai.Client:
    """API anahtarını okuyup Gemini istemcisini kurar."""
    anahtar = os.getenv("GEMINI_API_KEY")
    if not anahtar or anahtar.startswith("buraya"):
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı.\n"
            "  1) .env.example dosyasını kopyalayıp adını .env yapın\n"
            "  2) https://aistudio.google.com adresinden kendi anahtarınızı alın\n"
            "  3) .env içine GEMINI_API_KEY=... satırını yazın"
        )
    return genai.Client(api_key=anahtar)


def modelleri_yenile() -> None:
    """
    Model adlarını ortam değişkenlerinden yeniden okur.

    Model adları import anında okunur; Streamlit secrets ise ortam değişkenlerine
    import'tan SONRA yazılır. app.py secrets'ı yükledikten sonra bunu çağırır.
    """
    global MODEL, MODEL_OZENLI, MODEL_SES, OZENLI_ZAMAN_ASIMI_SN, SES_ZAMAN_ASIMI_SN
    MODEL = os.getenv("GEMINI_MODEL", MODEL)
    MODEL_OZENLI = os.getenv("GEMINI_MODEL_OZENLI", MODEL_OZENLI)
    MODEL_SES = os.getenv("GEMINI_MODEL_SES", MODEL_SES)
    OZENLI_ZAMAN_ASIMI_SN = float(os.getenv("GEMINI_OZENLI_ZAMAN_ASIMI_SN",
                                            OZENLI_ZAMAN_ASIMI_SN))
    SES_ZAMAN_ASIMI_SN = float(os.getenv("GEMINI_SES_ZAMAN_ASIMI_SN", SES_ZAMAN_ASIMI_SN))


def model_sec(ozenli: bool = False) -> str:
    """Kullanıcının tercihine göre metin modeli: hızlı (varsayılan) ya da özenli."""
    return MODEL_OZENLI if ozenli else MODEL


def _gecici_hata_mi(hata: Exception) -> bool:
    """Yoğunluk, kota, kapatılmış model ve zaman aşımı geçicidir; diğer model denenebilir."""
    return ("Timeout" in type(hata).__name__
            or any(k in str(hata) for k in _YEDEGE_GECIS_HATALARI))


def _modelle_uret(client: genai.Client, birincil: str, contents,
                  yedek_model: bool = True,
                  zaman_asimi_sn: float | None = None,
                  json_yanit: bool = False) -> tuple[str, str]:
    """
    İsteği birincil modele gönderir; geçici bir hata olursa diğer modeli bir kez dener.

    Döndürür: (yanıt metni, yanıtı üreten model). Yedeğe geçiş üreticinin boş ekranla
    kalmaması içindir; ölçüm tekrarlanabilir kalsın diye toplu testte kapatılır.
    Kalıcı hatalar (ör. geçersiz istek) yedeğe geçmeden olduğu gibi yükselir.

    zaman_asimi_sn: hızlı model (MODEL) DIŞINDAKİ her denemeye uygulanır. Böylece yavaş
    model hem birincil hem yedek olarak kullanıcıyı sınırsız bekletemez.
    """
    adaylar = [birincil]
    if yedek_model:
        adaylar += [m for m in (MODEL, MODEL_OZENLI) if m != birincil]
    son_hata = None
    for model in dict.fromkeys(adaylar):
        ayarlar = {}
        if zaman_asimi_sn and model != MODEL:
            sinir_ms = int(max(zaman_asimi_sn, _EN_KISA_SINIR_SN) * 1000)
            ayarlar["http_options"] = types.HttpOptions(timeout=sinir_ms)
        if json_yanit:
            ayarlar["response_mime_type"] = "application/json"
        config = types.GenerateContentConfig(**ayarlar) if ayarlar else None
        try:
            yanit = client.models.generate_content(model=model, contents=contents,
                                                   config=config)
            return (yanit.text or "").strip(), model
        except Exception as hata:
            son_hata = hata
            if not _gecici_hata_mi(hata):
                raise
    raise son_hata


# ---------------------------------------------------------------------------
def icerik_uret(anlatim: str,
                kategori: str = "Tekstil / El sanatı",
                ton: str = "sıcak ve samimi",
                teknik: str = "few_shot",
                anahtar_kelimeler: list[str] | None = None,
                uslup_ornekleri: list[str] | None = None,
                trends_kullan: bool = True,
                ozenli: bool = False,
                yedek_model: bool = True,
                client: genai.Client | None = None) -> Icerik:
    """
    Üreticinin anlatımından pazarlama içeriği üretir.

    teknik           : "zero_shot" | "few_shot" | "chain_of_thought"
                       (rapordaki prompt karşılaştırması için üçü de kullanılabilir)
    uslup_ornekleri  : üreticinin kendi yazdığı metinler — verilirse model bu
                       üslubu taklit eder ("Ton Profilim" özelliği)
    trends_kullan    : anahtar_kelimeler verilmediyse Google Trends'ten canlı
                       çekilsin mi? (kapatınca prompts'taki sabit liste kullanılır —
                       toplu testte tekrarlanabilirlik için False verilir)
    ozenli           : True ise daha yavaş ama daha özenli model (MODEL_OZENLI)
    yedek_model      : model geçici hata verirse diğer modele geçilsin mi?
                       (toplu testte False — ölçülen model değişmesin)
    """
    if not anlatim or not anlatim.strip():
        raise ValueError("Anlatım boş olamaz.")

    # Anahtar kelimeler: önce Google Trends (canlı arama davranışı), olmazsa sabit
    # kategori listesi. trends modülü her hata durumunda kendi içinde varsayılana
    # düştüğü için burada ayrıca try/except gerekmez.
    if anahtar_kelimeler is None:
        if trends_kullan:
            import trends
            anahtar_kelimeler = trends.anahtar_kelimeler(kategori)
        else:
            anahtar_kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])

    prompt_uret = {
        "zero_shot": prompts.zero_shot,
        "few_shot": prompts.few_shot,
        "chain_of_thought": prompts.chain_of_thought,
    }.get(teknik)
    if prompt_uret is None:
        raise ValueError(f"Bilinmeyen teknik: {teknik}")

    prompt = prompt_uret(anlatim=anlatim, kategori=kategori, ton=ton,
                         anahtar_kelimeler=anahtar_kelimeler,
                         uslup_ornekleri=uslup_ornekleri)

    client = client or istemci_olustur()
    metin, kullanilan = _modelle_uret(client, model_sec(ozenli), prompt, yedek_model,
                                      zaman_asimi_sn=OZENLI_ZAMAN_ASIMI_SN)

    ig, sh = _ayristir(metin)
    return Icerik(instagram=ig, shopier=sh, ham_yanit=metin, model=kullanilan)


# ---------------------------------------------------------------------------
def _ayristir(metin: str) -> tuple[str, str]:
    """[INSTAGRAM] ve [SHOPIER] etiketlerine göre yanıtı ikiye böler."""
    ig = _etiket_yakala(metin, "INSTAGRAM", "SHOPIER")
    sh = _etiket_yakala(metin, "SHOPIER", None)

    # Model etiketleri yazmadıysa: metni ortadan bölmek yerine tamamını
    # Instagram'a koyup durumu görünür bırakıyoruz (sessiz hata olmasın).
    if not ig and not sh:
        return metin, ""
    return ig, sh


def _etiket_yakala(metin: str, bas: str, son: str | None) -> str:
    desen = rf"\[{bas}\](.*?)" + (rf"\[{son}\]" if son else r"$")
    eslesme = re.search(desen, metin, re.DOTALL | re.IGNORECASE)
    return eslesme.group(1).strip() if eslesme else ""


# ---------------------------------------------------------------------------
def sesten_metne(ses_baytlari: bytes, mime_turu: str = "audio/wav",
                 client: genai.Client | None = None) -> str:
    """
    Üreticinin sesli anlatımını metne çevirir.

    Gemini sesi doğrudan işleyebildiği için ayrı bir STT servisi gerekmez.
    Konuşanın kendi kelimeleri korunur — metin güzelleştirilmez (bkz. SES_TALIMATI).
    Doğruluk hızdan önemli olduğu için MODEL_SES (varsayılan: özenli model) kullanılır.
    """
    if not ses_baytlari:
        raise ValueError("Ses kaydı boş.")

    client = client or istemci_olustur()
    metin, _ = _modelle_uret(client, MODEL_SES, [
        types.Part.from_bytes(data=ses_baytlari, mime_type=mime_turu),
        prompts.SES_TALIMATI,
    ], zaman_asimi_sn=SES_ZAMAN_ASIMI_SN)
    return metin


def reels_uret(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
               uslup_ornekleri: list[str] | None = None, ozenli: bool = False,
               client: genai.Client | None = None) -> str:
    """Telefonla çekilebilecek 20-30 sn'lik Reels/TikTok çekim planı (Markdown)."""
    prompt = prompts.reels_senaryosu(anlatim=anlatim, kategori=kategori, ton=ton,
                                     uslup_ornekleri=uslup_ornekleri)
    client = client or istemci_olustur()
    return _modelle_uret(client, model_sec(ozenli), prompt,
                         zaman_asimi_sn=OZENLI_ZAMAN_ASIMI_SN)[0]


def foto_rehberi_uret(anlatim: str, kategori: str, ozenli: bool = False,
                      client: genai.Client | None = None) -> str:
    """Ürüne özel, telefonla uygulanabilir fotoğraf çekim rehberi (Markdown)."""
    prompt = prompts.foto_rehberi(anlatim=anlatim, kategori=kategori)
    client = client or istemci_olustur()
    return _modelle_uret(client, model_sec(ozenli), prompt,
                         zaman_asimi_sn=OZENLI_ZAMAN_ASIMI_SN)[0]


def ek_format_uret(anlatim: str, kategori: str, bicim: str,
                   uslup_ornekleri: list[str] | None = None,
                   trends_kullan: bool = True, ozenli: bool = False,
                   client: genai.Client | None = None) -> str:
    """
    Ek formatlar (Markdown): "story" (3 karelik hikâye), "whatsapp" (durum + müşteri
    mesajı), "hashtag" (gruplanmış hashtag seti; arama kelimeleriyle beslenir).
    """
    if bicim not in prompts.EK_BICIMLER:
        raise ValueError(f"Bilinmeyen biçim: {bicim}")
    if not anlatim or not anlatim.strip():
        raise ValueError("Anlatım boş olamaz.")
    kelimeler = None
    if bicim == "hashtag":
        if trends_kullan:
            import trends
            kelimeler = trends.anahtar_kelimeler(kategori)
        else:
            kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    prompt = prompts.ek_format(anlatim=anlatim, kategori=kategori, bicim=bicim,
                               anahtar_kelimeler=kelimeler,
                               uslup_ornekleri=uslup_ornekleri)
    client = client or istemci_olustur()
    metin = _modelle_uret(client, model_sec(ozenli), prompt,
                          zaman_asimi_sn=OZENLI_ZAMAN_ASIMI_SN)[0]
    if bicim == "hashtag":
        metin, _ = hashtag_denetle(metin, anlatim)
    return metin


# Hashtag'de geçip anlatımda geçmiyorsa üründe olmayan bir özelliği iddia eden kökler.
_KANIT_ISTEYEN_KOKLER = ("organik", "doğal", "katkı", "kumaş", "ipek", "gümüş", "altın",
                         "deri", "yün", "pamuk", "keten", "bambu", "vegan", "glutensiz")
# Anlatımda geçse bile hashtag yapılmayan iddia ve klişe kökleri.
_YASAK_HASHTAG_KOKLERI = ("mucize", "şifa", "garanti", "eniyi", "göznuru", "sevgiyle",
                          "birebir", "tedavi")


def _tr_kucuk(metin: str) -> str:
    """Türkçe küçük harf: 'İ' → 'i', 'I' → 'ı' (str.lower bunları bozar)."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


def hashtag_denetle(metin: str, anlatim: str) -> tuple[str, list[str]]:
    """
    Hashtag'leri etik kurallara göre deterministik olarak süzer.

    Prompt kuralları olasılıksaldır: canlı testte kumaş olmayan bir ürüne #doğalkumaş,
    yasak klişeden #elemekgöznuru üretildi. Bu süzgeç iddia/klişe köklerini her zaman,
    malzeme/özellik köklerini ise anlatımda geçmiyorsa çıkarır.
    Döndürür: (temiz metin, çıkarılan etiketler).
    """
    kaynak = _tr_kucuk(anlatim)
    cikan: list[str] = []

    def suz(eslesme: re.Match) -> str:
        etiket = _tr_kucuk(eslesme.group(0))
        uygun = (not any(y in etiket for y in _YASAK_HASHTAG_KOKLERI)
                 and all(k in kaynak for k in _KANIT_ISTEYEN_KOKLER if k in etiket))
        if uygun:
            return eslesme.group(0)
        cikan.append(eslesme.group(0))
        return ""

    temiz = re.sub(r"#\w+", suz, metin)
    temiz = "\n".join(re.sub(r"[ \t]{2,}", " ", s).strip() for s in temiz.splitlines())
    return temiz, list(dict.fromkeys(cikan))


def metin_uret(contents, ozenli: bool = False, json_yanit: bool = False,
               client: genai.Client | None = None) -> str:
    """
    Görsel stüdyosu ve satış araçları için ortak model çağrısı: model seçimi, süre sınırı
    ve yedeğe geçiş içerik üretimiyle aynı kurallara uyar. contents metin ya da
    [Part, metin] listesi (fotoğraf) olabilir.
    """
    client = client or istemci_olustur()
    return _modelle_uret(client, model_sec(ozenli), contents, json_yanit=json_yanit,
                         zaman_asimi_sn=OZENLI_ZAMAN_ASIMI_SN)[0]


def json_coz(metin: str) -> dict:
    """Model JSON yanıtını okur; kod bloğu işaretlerini temizler. Okunamazsa ValueError."""
    temiz = re.sub(r"^```(?:json)?\s*|\s*```$", "", (metin or "").strip())
    try:
        veri = json.loads(temiz)
    except json.JSONDecodeError:
        eslesme = re.search(r"\{.*\}", temiz, re.DOTALL)
        if not eslesme:
            raise ValueError("Yanıt okunamadı, tekrar deneyin.") from None
        veri = json.loads(eslesme.group(0))
    if not isinstance(veri, dict):
        raise ValueError("Yanıt beklenen biçimde değil, tekrar deneyin.")
    return veri


def seo_kapsami(metin: str, anahtar_kelimeler: list[str]) -> int:
    """Üretilen metinde kaç anahtar kelimenin geçtiğini sayar (KPI ölçümü)."""
    kucuk = metin.lower()
    return sum(1 for k in anahtar_kelimeler if k.lower() in kucuk)


def klise_sayisi(metin: str) -> int:
    """
    Metinde kaç klişe/dolgu kalıbı geçtiğini sayar.

    Kalite göstergesi: DÜŞÜK olması iyidir. Prompt iyileştirmesinin (A3) etkisini
    ölçmek için kullanılır — v1 ve v2 çıktıları bu sayıyla karşılaştırılır.
    """
    kucuk = metin.lower()
    return sum(1 for k in prompts.KLISE_KALIPLARI if k in kucuk)


def kanal_benzerligi(metin_a: str, metin_b: str) -> float:
    """
    İki kanalın ne kadar benzediğini 0-1 arası ölçer (Jaccard benzerliği).

    Kalite göstergesi: DÜŞÜK olması iyidir. Instagram ve Shopier farklı işlere
    hizmet ettiği için aynı cümleleri tekrarlamamaları beklenir.
    """
    ayikla = lambda m: {k.strip(".,!?;:#").lower()
                        for k in m.split() if len(k) > 3 and not k.startswith("#")}
    a, b = ayikla(metin_a), ayikla(metin_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ornek = ("El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği "
             "kullanıyorum, tamamen elde örüyorum. Bir tanesi yaklaşık üç günümü "
             "alıyor. Anneannemden öğrendiğim bir desen kullanıyorum.")

    print("=" * 70)
    print("ÜRETKEN KADIN — çekirdek test")
    print("=" * 70)
    print(f"\nGİRDİ:\n{ornek}\n")

    try:
        sonuc = icerik_uret(ornek, kategori="Tekstil / El sanatı", teknik="few_shot")
    except Exception as hata:
        print(f"HATA: {hata}")
        raise SystemExit(1)

    print("-" * 70)
    print("INSTAGRAM:\n" + sonuc.instagram)
    print("-" * 70)
    print("SHOPIER:\n" + sonuc.shopier)
    print("-" * 70)

    kelimeler = prompts.KATEGORI_KELIMELERI["Tekstil / El sanatı"]
    kapsam = seo_kapsami(sonuc.instagram + " " + sonuc.shopier, kelimeler)
    print(f"SEO kapsamı: {kapsam}/{len(kelimeler)} anahtar kelime kullanıldı")
    print(f"Model: {sonuc.model}")
