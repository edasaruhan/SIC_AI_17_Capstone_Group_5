# -*- coding: utf-8 -*-
"""
Üretken Kadın — Çekirdek üretim modülü

Üreticinin doğal anlatımını alır, Gemini'ye gönderir ve iki kanallı pazarlama
içeriği döndürür (Instagram gönderisi + Shopier ürün açıklaması).

Terminalden denemek için:
    python src/uret.py
"""

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai

import prompts

load_dotenv()

# Kullanilacak model. Google zaman zaman eski modelleri yeni kullanicilara kapatiyor;
# "404 ... no longer available" hatasi alirsaniz hata mesajinin onerdigi model adini
# buraya yazin. Model adi .env icinden de GEMINI_MODEL ile degistirilebilir.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


# ---------------------------------------------------------------------------
@dataclass
class Icerik:
    """Üretilen içeriğin iki kanalı."""
    instagram: str
    shopier: str
    ham_yanit: str = ""      # ayrıştırma hatalarını incelemek için

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


# ---------------------------------------------------------------------------
def icerik_uret(anlatim: str,
                kategori: str = "Tekstil / El sanatı",
                ton: str = "sıcak ve samimi",
                teknik: str = "few_shot",
                anahtar_kelimeler: list[str] | None = None,
                uslup_ornekleri: list[str] | None = None,
                client: genai.Client | None = None) -> Icerik:
    """
    Üreticinin anlatımından pazarlama içeriği üretir.

    teknik           : "zero_shot" | "few_shot" | "chain_of_thought"
                       (rapordaki prompt karşılaştırması için üçü de kullanılabilir)
    uslup_ornekleri  : üreticinin kendi yazdığı metinler — verilirse model bu
                       üslubu taklit eder ("Ton Profilim" özelliği)
    """
    if not anlatim or not anlatim.strip():
        raise ValueError("Anlatım boş olamaz.")

    # Kategoriye ait varsayılan kelimeler (A4'te pytrends ile değişecek)
    if anahtar_kelimeler is None:
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
    yanit = client.models.generate_content(model=MODEL, contents=prompt)
    metin = (yanit.text or "").strip()

    ig, sh = _ayristir(metin)
    return Icerik(instagram=ig, shopier=sh, ham_yanit=metin)


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
