# -*- coding: utf-8 -*-
"""
Üretken Kadın — Kalite modeli için etiketli PROTOTİP veri seti üreteci

Neden var: "Data Prep & Model Exploration" dökümanı, içerik-kalite
sınıflandırıcısının "temsili/prototip bir veri seti üzerinde" eğitildiğini açıkça
belirtir; canlı saha etiketleri henüz yoktur. Bu betik, o prototip veri setini
ŞEFFAF ve YENİDEN ÜRETİLEBİLİR biçimde oluşturur.

Sınıflar:
  - "yüksek" (onaya hazır): somut, öykülü, ölçülü, SEO'ya değen, klişesiz.
  - "düşük" (revizyon gerek): klişe/abartı yüklü, aşırı pazarlamacı, çok kısa
    ya da jenerik-kurumsal.

GERÇEKÇİLİK İÇİN sınırda örnekler de katılır:
  - "yüksek-kusurlu": genelde iyi ama tek bir klişe/hype barındıran (yine de onaylanan)
  - "düşük-makul": öykü+SEO var ama aşırı pazarlamacı/kurumsal (yine de revizyon gerek)
Bu örtüşme, modelin %100 değil gerçekçi (bir miktar hatalı) metrikler vermesini
sağlar — tıpkı insan etiketlemesindeki belirsizlik gibi. Etiketler kurgusaldır ama
etiket MANTIĞI dürüsttür; saha pilotunda gerçek insan etiketleriyle değişecektir.

Kullanım:
    python src/kalite_veri_uret.py            # data/kalite_etiketli.csv yazar
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import prompts
from kalite import ABARTI_KALIPLARI, DUYGU_KALIPLARI

_KOK = Path(__file__).resolve().parent.parent
CIKTI = _KOK / "data" / "kalite_etiketli.csv"

RASTGELE_TOHUM = 42

# ---------------------------------------------------------------------------
# Ürün havuzu — 4 kategori. Her ürün: (ad, malzeme, süreç, süre, öykü, kime).
# ---------------------------------------------------------------------------
URUNLER = {
    "Tekstil / El sanatı": [
        ("bebek battaniyesi", "organik pamuk ipliği", "tamamen elde örüyorum",
         "üç günümü alıyor", "anneannemden öğrendiğim desenle", "yeni doğan hediyesi arayanlar"),
        ("ekmek torbası", "keten kumaş", "kendim dikiyorum",
         "bir saatte bitiyor", "ekmeği bayatlatmasın diye", "doğal saklama sevenler"),
        ("keçe bebek patiği", "doğal boyalı yün keçe", "elde dikiyorum",
         "bir günde bir çift", "kızımın ilk patiğinden esinlenerek", "bebek hediyesi arayanlar"),
        ("örgü atkı", "yumuşak merinos yünü", "şişle örüyorum",
         "iki günümü alıyor", "kışın üşüyen boyunlar için", "sıcak tutan aksesuar sevenler"),
        ("nakışlı yastık kılıfı", "pamuklu kumaş", "iğne oyasıyla işliyorum",
         "beş gün sürüyor", "annemin çeyizindeki motiflerle", "el işi dekor sevenler"),
    ],
    "Gıda": [
        ("domates salçası", "kendi bahçemizin domatesi", "güneşte kurutuyorum",
         "bir hafta sürüyor", "sadece domates ve tuz katıyorum", "katkısız ürün arayanlar"),
        ("tarhana", "domates biber soğan ve yoğurt", "geleneksel yöntemle mayalıyorum",
         "yirmi gün sürüyor", "köyümüzün usulüyle", "kış hazırlığı yapanlar"),
        ("vişne reçeli", "bahçemizin vişnesi", "bakır kazanda pişiriyorum",
         "bir günümü alıyor", "şeker dışında hiçbir şey katmadan", "kahvaltılık doğal reçel sevenler"),
        ("ev makarnası", "köy yumurtası ve un", "elde açıp kesiyorum",
         "yarım gün sürüyor", "babaannemin açtığı gibi", "el yapımı erişte sevenler"),
        ("kuru kayısı marmelatı", "Malatya kayısısı", "düşük ateşte kaynatıyorum",
         "birkaç saatte", "hiç koruyucu katmadan", "doğal tatlı arayanlar"),
    ],
    "Takı / Aksesuar": [
        ("gümüş kolye", "925 ayar gümüş tel", "tel sarma tekniğiyle yapıyorum",
         "bir günümü alıyor", "her biri tek olsun diye", "özel tasarım takı sevenler"),
        ("makrome bileklik", "pamuk ip ve doğal taş", "elde örüyorum",
         "bir saatte", "denizde bile takılabilsin diye", "yazlık aksesuar arayanlar"),
        ("boncuk küpe", "cam boncuk ve pirinç", "tek tek diziyorum",
         "yarım günde", "renkleri kendim eşleştirerek", "renkli takı sevenler"),
        ("deri anahtarlık", "hakiki dana derisi", "kesip elde dikiyorum",
         "bir saatte", "dayanıklı olsun diye", "sade hediye arayanlar"),
    ],
    "Tasarım / Dekorasyon": [
        ("ahşap kesme tahtası", "ceviz ve kayın ağacı", "gıdaya uygun yağla cilalıyorum",
         "iki günümü alıyor", "isteyene isim yazarak", "mutfak hediyesi arayanlar"),
        ("kuru çiçek panosu", "kendim topladığım çiçekler", "kurutup çerçeveliyorum",
         "bir hafta sürüyor", "elimdeki çiçeğe göre her biri farklı", "doğal dekor sevenler"),
        ("beton saksı", "beyaz çimento", "kalıba döküp zımparalıyorum",
         "iki günde", "sukulentlerime yakışsın diye", "modern dekor sevenler"),
        ("makrome duvar süsü", "doğal pamuk ip", "düğüm düğüm örüyorum",
         "üç günümü alıyor", "boş duvarlar canlansın diye", "bohem dekor sevenler"),
    ],
}

IYI_ACILIS = [
    "{ad} yapıyorum.", "Elimden {ad} çıkıyor.", "{ad} hazırlıyorum.",
    "Uzun zamandır {ad} yapıyorum.", "Bu {ad} bana ait.",
    "Sizlere {ad} hazırladım.", "Yeni bir {ad} daha hazır.",
]

MALZEME_KALIP = [
    "{malzeme} kullanıyorum, {surec}.",
    "{surec}; {malzeme} tercih ediyorum.",
    "Malzeme olarak {malzeme} seçtim ve {surec}.",
]

SUREC_KALIP = [
    "{hikaye} çalışıyorum; bir tanesi {sure}.",
    "Bir tanesi {sure}, {hikaye} yapıyorum.",
    "{hikaye}; her biri {sure}.",
]

JENERIK_KURUMSAL = [
    "Kaliteli ürünlerimizle hizmetinizdeyiz.",
    "Müşteri memnuniyeti önceliğimizdir.",
    "Sizler için özenle seçilmiş ürünler.",
    "En uygun fiyatlarla sizlerle.",
    "Ürün gamımızı keşfedin.",
    "Siparişleriniz özenle hazırlanır.",
]


def _seo_serpistir(kategori: str, adet: int) -> list[str]:
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    return random.sample(kelimeler, min(adet, len(kelimeler)))


def _hashtagler(kategori: str) -> str:
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    etiketler = ["#" + k.replace(" ", "") for k in random.sample(
        kelimeler, min(3, len(kelimeler)))]
    return " ".join(etiketler)


# ---------------------------------------------------------------------------
def iyi_metin(urun: tuple, kategori: str, kusurlu: bool = False) -> str:
    """Somut, öykülü, ölçülü, SEO'ya değen bir 'yüksek' örnek.

    kusurlu=True ise gerçekçilik için TEK bir klişe/hype eklenir (yine yüksek).
    """
    ad, malzeme, surec, sure, hikaye, kime = urun
    cumleler = [random.choice(IYI_ACILIS).format(ad=ad)]

    # detayların bir kısmını rastgele dahil et (çeşitlilik → dedup'a dayanıklılık)
    if random.random() < 0.9:
        cumleler.append(random.choice(MALZEME_KALIP).format(
            malzeme=malzeme, surec=surec))
    if random.random() < 0.85:
        cumleler.append(random.choice(SUREC_KALIP).format(
            hikaye=hikaye.capitalize(), sure=sure))

    seo = _seo_serpistir(kategori, random.choice([1, 2, 3]))
    if seo and random.random() < 0.8:
        cumleler.append(f"{kime.capitalize()} için uygundur "
                        f"({', '.join(seo)}).")

    if kusurlu:
        bozan = random.choice(prompts.KLISE_KALIPLARI + DUYGU_KALIPLARI[:6])
        cumleler.append(f"{bozan.capitalize()}.")

    metin = " ".join(cumleler)
    if random.random() < 0.35:
        metin += "\n" + _hashtagler(kategori)
    return metin


def kotu_metin(urun: tuple, kategori: str, stil: str) -> str:
    """Projenin kaçınmak istediği kalıpları taşıyan bir 'düşük' örnek."""
    ad, malzeme, surec, sure, hikaye, kime = urun

    if stil == "klise":
        klise = random.sample(prompts.KLISE_KALIPLARI, 3)
        return (f"{ad.capitalize()} — {klise[0]}. Her biri {klise[1]}, "
                f"{klise[2]}. Sevgiyle hazırlandı, göz nuru.")

    if stil == "abarti":
        ab = random.sample(ABARTI_KALIPLARI, 3)
        return (f"Dünyanın {ab[0]} {ad}! {ab[1].capitalize()}, {ab[2]}. "
                f"Kalitesiyle rakipsiz, kesinlikle pişman olmayacaksınız.")

    if stil == "hype":
        h = random.sample(DUYGU_KALIPLARI, 4)
        return (f"{h[0].capitalize()} {ad}! {h[1].capitalize()}, {h[2]}! "
                f"{h[3].capitalize()} — stoklar tükenmeden sipariş verin!")

    if stil == "kisa":
        return random.choice([f"{ad.capitalize()} satılık.",
                              f"{ad.capitalize()} var.",
                              f"Uygun fiyata {ad}."])

    if stil == "makul":
        # SINIRDA: öykü+SEO var ama aşırı pazarlamacı/kurumsal → yine de revizyon
        seo = _seo_serpistir(kategori, 2)
        h = random.choice(DUYGU_KALIPLARI)
        return (f"{ad.capitalize()} ({', '.join(seo)}). {malzeme.capitalize()} ile "
                f"{surec}. {h.capitalize()}! " + random.choice(JENERIK_KURUMSAL))

    # jenerik-kurumsal (öykü/SEO yok, soğuk dil)
    return f"{ad.capitalize()}. " + " ".join(random.sample(JENERIK_KURUMSAL, 2))


# ---------------------------------------------------------------------------
def veri_uret() -> list[dict]:
    random.seed(RASTGELE_TOHUM)
    satirlar: list[dict] = []
    sid = 0

    for kategori, urunler in URUNLER.items():
        for urun in urunler:
            # 14 temiz-iyi + 2 kusurlu-iyi = 16 yüksek
            for _ in range(14):
                sid += 1
                satirlar.append({"id": sid, "kategori": kategori,
                                 "metin": iyi_metin(urun, kategori),
                                 "kalite_1_5": random.choice([4, 4, 5, 5, 5]),
                                 "hedef": 1})
            for _ in range(2):
                sid += 1
                satirlar.append({"id": sid, "kategori": kategori,
                                 "metin": iyi_metin(urun, kategori, kusurlu=True),
                                 "kalite_1_5": 4, "hedef": 1})

            # 8 belirgin-kötü + 2 makul-kötü = 10 düşük
            for stil in ["klise", "abarti", "hype", "kisa",
                         "klise", "abarti", "hype", "jenerik"]:
                sid += 1
                satirlar.append({"id": sid, "kategori": kategori,
                                 "metin": kotu_metin(urun, kategori, stil),
                                 "kalite_1_5": random.choice([1, 2, 2, 3]),
                                 "hedef": 0})
            for _ in range(2):
                sid += 1
                satirlar.append({"id": sid, "kategori": kategori,
                                 "metin": kotu_metin(urun, kategori, "makul"),
                                 "kalite_1_5": 3, "hedef": 0})

    random.shuffle(satirlar)
    return satirlar


def main() -> None:
    satirlar = veri_uret()
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8-sig", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=["id", "kategori", "metin",
                                               "kalite_1_5", "hedef"])
        yazici.writeheader()
        yazici.writerows(satirlar)

    yuksek = sum(1 for s in satirlar if s["hedef"] == 1)
    dusuk = len(satirlar) - yuksek
    print(f"Yazıldı: {CIKTI.relative_to(_KOK)}")
    print(f"Toplam {len(satirlar)} örnek  ·  yüksek: {yuksek}  ·  düşük: {dusuk}")


if __name__ == "__main__":
    main()
