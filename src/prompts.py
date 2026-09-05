# -*- coding: utf-8 -*-
"""
Üretken Kadın — Prompt şablonları

Bu dosya, üreticinin doğal anlatımını pazarlama içeriğine çeviren prompt'ları içerir.
Üç teknik ayrı ayrı tanımlanmıştır (capstone raporunda karşılaştırılmak üzere):

    1. zero_shot      : örneksiz, doğrudan talimat  (baseline / karşılaştırma tabanı)
    2. few_shot       : üreticinin kendi üslubundan örneklerle
    3. chain_of_thought: modeli önce düşünmeye, sonra yazmaya yönlendiren

Etik kısıtlar (abartı yasağı, uydurma yasağı) her şablonda ortaktır.
"""

# ---------------------------------------------------------------------------
# Ortak sistem talimatı — etik çerçeve burada tanımlanır
# ---------------------------------------------------------------------------
SISTEM_TALIMATI = """Sen, Türkiye'de evinde el emeğiyle üretim yapan kadın üreticilere
pazarlama içeriği hazırlayan bir asistansın.

MUTLAK KURALLAR:
1. Yalnızca üreticinin sana verdiği bilgiyi kullan. Ürüne olmayan bir özellik,
   malzeme, ölçü veya sertifika EKLEME. Bilmediğin şeyi uydurma.
2. Abartı yapma. "En iyi", "mucize", "birebir", "garanti", "şifalı", "dünyanın en
   kalitelisi" gibi ispatsız iddialar KULLANMA.
3. Sağlık iddiası kurma (özellikle gıda ürünlerinde). Tedavi/iyileştirme ima etme.
4. Üreticinin kendi sesini koru. Kurumsal, soğuk ya da reklam ajansı dili kullanma;
   üretici nasıl anlatıyorsa o sıcaklıkta yaz.
5. Emeği ve üretim sürecini öne çıkar — hikâye, ürünün en değerli parçasıdır.
6. Türkçe yaz. Yabancı kelime kullanma (gerekli değilse).

Ürettiğin içerik, üretici tarafından okunup onaylanacaktır. Onun adına konuşuyorsun;
söylemediği bir şeyi söyleme."""


# ---------------------------------------------------------------------------
# Çıktı biçimi — iki kanal, ayrıştırılabilir olsun diye etiketli
# ---------------------------------------------------------------------------
CIKTI_BICIMI = """Çıktıyı tam olarak aşağıdaki biçimde ver. Etiketleri değiştirme,
başka hiçbir açıklama ekleme:

[INSTAGRAM]
(Instagram gönderisi metni. 2-4 cümle, sıcak ve samimi. Sonunda en fazla 5 hashtag.)

[SHOPIER]
(Ürün sayfası açıklaması. 3-5 cümle. Malzeme, üretim şekli ve kime uygun olduğu
net yazılsın. Arama yapan birinin kullanacağı kelimeler doğal biçimde geçsin.)"""


# ---------------------------------------------------------------------------
# 1) ZERO-SHOT — örnek verilmez (baseline)
# ---------------------------------------------------------------------------
def zero_shot(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
              anahtar_kelimeler: list[str] | None = None) -> str:
    kelime_blogu = _kelime_blogu(anahtar_kelimeler)
    return f"""{SISTEM_TALIMATI}

ÜRÜN KATEGORİSİ: {kategori}
İSTENEN TON: {ton}
{kelime_blogu}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Yukarıdaki anlatımı kullanarak pazarlama içeriği yaz.

{CIKTI_BICIMI}"""


# ---------------------------------------------------------------------------
# 2) FEW-SHOT — üreticinin üslubundan örneklerle
# ---------------------------------------------------------------------------
def few_shot(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
             anahtar_kelimeler: list[str] | None = None,
             ornekler: list[dict] | None = None) -> str:
    """`ornekler`: [{"anlatim": "...", "instagram": "...", "shopier": "..."}, ...]"""
    ornekler = ornekler or VARSAYILAN_ORNEKLER
    kelime_blogu = _kelime_blogu(anahtar_kelimeler)

    ornek_blogu = ""
    for i, o in enumerate(ornekler, 1):
        ornek_blogu += f"""
--- ÖRNEK {i} ---
ÜRETİCİNİN ANLATIMI:
\"\"\"{o['anlatim']}\"\"\"

[INSTAGRAM]
{o['instagram']}

[SHOPIER]
{o['shopier']}
"""

    return f"""{SISTEM_TALIMATI}

Aşağıda, bu üreticinin üslubuna uygun örnekler var. Yeni içeriği YAZARKEN bu
örneklerin tonunu, cümle uzunluğunu ve samimiyet düzeyini taklit et — ama
içeriklerini kopyalama.
{ornek_blogu}
--- ŞİMDİ SIRA SENDE ---
ÜRÜN KATEGORİSİ: {kategori}
İSTENEN TON: {ton}
{kelime_blogu}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

{CIKTI_BICIMI}"""


# ---------------------------------------------------------------------------
# 3) CHAIN-OF-THOUGHT — önce düşün, sonra yaz
# ---------------------------------------------------------------------------
def chain_of_thought(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
                     anahtar_kelimeler: list[str] | None = None) -> str:
    kelime_blogu = _kelime_blogu(anahtar_kelimeler)
    return f"""{SISTEM_TALIMATI}

ÜRÜN KATEGORİSİ: {kategori}
İSTENEN TON: {ton}
{kelime_blogu}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

İçeriği yazmadan ÖNCE, kendi kendine şu adımları düşün (bu düşünceyi çıktıya YAZMA):
  1. Bu üründe alıcıyı asıl etkileyecek tek detay ne? (malzeme mi, emek mi, hikâye mi)
  2. Üretici hangi kelimeleri kendi kullanmış? Onun sözcüklerini koru.
  3. Bu ürünü arayan biri Google'a ne yazar?
  4. Anlatımda OLMAYAN ama yazarken uydurmaya meyledeceğim bir şey var mı? Onu ele.

Bu düşünmeyi yaptıktan sonra, yalnızca son içeriği aşağıdaki biçimde ver.

{CIKTI_BICIMI}"""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _kelime_blogu(anahtar_kelimeler) -> str:
    """SEO kelimeleri varsa prompt'a eklenecek blok (A4 aşamasında beslenecek)."""
    if not anahtar_kelimeler:
        return ""
    kelimeler = ", ".join(anahtar_kelimeler)
    return (f"\nARAMA VERİSİNDEN GELEN ANAHTAR KELİMELER: {kelimeler}\n"
            "Bu kelimeleri metne DOĞAL biçimde yerleştir. Zorlama, listeleme, "
            "art arda dizme. Cümle akışını bozuyorsa kullanma.\n")


# Ton profili için başlangıç örnekleri.
# A3 aşamasında gerçek üreticinin kendi metinleriyle değiştirilecek.
VARSAYILAN_ORNEKLER = [
    {
        "anlatim": "Keçeden bebek patiği yapıyorum. Yün keçe kullanıyorum, "
                   "boyası doğal. Bir çiftini bir günde bitiriyorum.",
        "instagram": "Her ilmeği elimle attığım keçe patikler… Doğal boyalı yün "
                     "keçeden, minik ayaklar için. Bir çifti tam bir günümü alıyor "
                     "ama o minik ayaklara değiyor.\n"
                     "#keçepatik #elemeği #bebekhediyesi",
        "shopier": "El yapımı keçe bebek patiği. Doğal boyalı yün keçeden, tamamen "
                   "elde dikilerek üretilmiştir. Her çift yaklaşık bir günlük emekle "
                   "hazırlanır. Bebek hediyesi arayanlar ve doğal malzeme tercih eden "
                   "anneler için uygundur.",
    },
    {
        "anlatim": "Ev yapımı vişne reçeli. Kendi bahçemizin vişnesi, şeker dışında "
                   "hiçbir şey katmıyorum. 400 gramlık kavanozlarda.",
        "instagram": "Bahçemizin vişnesi, bir de şeker. Başka hiçbir şey yok içinde. "
                     "Kavanozları tek tek dolduruyorum, tam kıvamında.\n"
                     "#evyapımıreçel #vişnereçeli #katkısız",
        "shopier": "Ev yapımı vişne reçeli, 400 g cam kavanozda. Kendi bahçemizde "
                   "yetişen vişnelerden, yalnızca şeker eklenerek geleneksel yöntemle "
                   "pişirilmiştir. Koruyucu, renklendirici veya aroma içermez. "
                   "Kahvaltılık doğal reçel arayanlar için.",
    },
]


# Kategoriye göre kullanılabilecek başlangıç anahtar kelimeleri.
# A4 aşamasında pytrends'ten gelen gerçek verilerle değiştirilecek.
KATEGORI_KELIMELERI = {
    "Tekstil / El sanatı": ["el yapımı", "el emeği", "hediyelik", "doğal kumaş"],
    "Gıda":                ["ev yapımı", "katkısız", "doğal", "geleneksel"],
    "Takı / Aksesuar":     ["el yapımı takı", "özel tasarım", "hediye"],
    "Tasarım / Dekorasyon": ["el yapımı dekor", "ev dekorasyonu", "özel tasarım"],
}
