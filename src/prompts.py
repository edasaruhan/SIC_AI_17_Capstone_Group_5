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
7. DOLGU CÜMLESİ KURMA. Üretici somut bir şey anlattı; sen onun üzerine duygusal
   süs ekleme. Aşağıdaki kalıplar ve benzerleri YASAK:
     - "her ilmeğinde ayrı bir emek/özen var"
     - "sevgiyle hazırlandı", "göz nuru", "el emeği göz nuru"
     - "özenli bir dokunuş arayanlar için"
     - "anlamlı bir hediye arayanlar için"
     - "yaşamınıza değer katacak", "fark yaratan"
     - "her biri ayrı bir sanat eseri"
   Bir cümle, anlatımda olmayan bir bilgi taşımıyorsa o cümleyi hiç yazma.
   Kısa ve dolu olmak, uzun ve süslü olmaktan iyidir.
8. Üreticinin kullandığı somut kelimeleri koru (örn. "anneannemden öğrendiğim",
   "üç günümü alıyor", "bahçemizin"). Bunları eş anlamlılarıyla değiştirme —
   otantikliği taşıyan şey tam olarak bu kelimelerdir.

Ürettiğin içerik, üretici tarafından okunup onaylanacaktır. Onun adına konuşuyorsun;
söylemediği bir şeyi söyleme."""


# ---------------------------------------------------------------------------
# Çıktı biçimi — iki kanal, ayrıştırılabilir olsun diye etiketli
# ---------------------------------------------------------------------------
CIKTI_BICIMI = """İKİ KANAL BİRBİRİNDEN FARKLI OLMALI. Aynı cümleleri iki yere yazma;
ikisi farklı işe yarar:

[INSTAGRAM]  → Amaç: kaydırırken DURDURMAK.
  - İlk cümle, anlatımdaki EN İLGİNÇ tek detayla başlasın (süre, teknik, kimden
    öğrenildiği gibi). Ürün tanımıyla başlama, merak uyandır.
  - 2-3 kısa cümle. Konuşma dili. "Ben" diliyle yaz.
  - Malzeme listesi, ölçü, teknik ayrıntı YAZMA — orası Shopier'in işi.
  - En fazla 5 hashtag, en sonda.

[SHOPIER]  → Amaç: arayan kişinin BULMASI ve karar vermesi.
  - İlk cümle ürünün ne olduğunu net söylesin (arama sonucunda görünecek).
  - Malzeme, üretim şekli, süre, varsa ölçü/gramaj açıkça yazılsın.
  - Son cümle kime uygun olduğunu somut söylesin.
  - Bilgi verici ve sakin bir dil; Instagram'daki duygusal cümleleri TEKRARLAMA.

Çıktıyı tam olarak şu biçimde ver, etiketleri değiştirme, başka açıklama ekleme:

[INSTAGRAM]
(metin)

[SHOPIER]
(metin)"""


# ---------------------------------------------------------------------------
# 1) ZERO-SHOT — örnek verilmez (baseline)
# ---------------------------------------------------------------------------
def zero_shot(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
              anahtar_kelimeler: list[str] | None = None,
              uslup_ornekleri: list[str] | None = None) -> str:
    kelime_blogu = _kelime_blogu(anahtar_kelimeler)
    uslup = uslup_blogu(uslup_ornekleri)
    return f"""{SISTEM_TALIMATI}

ÜRÜN KATEGORİSİ: {kategori}
İSTENEN TON: {ton}
{kelime_blogu}{uslup}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Yukarıdaki anlatımı kullanarak pazarlama içeriği yaz.

{CIKTI_BICIMI}"""


# ---------------------------------------------------------------------------
# 2) FEW-SHOT — üreticinin üslubundan örneklerle
# ---------------------------------------------------------------------------
def few_shot(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
             anahtar_kelimeler: list[str] | None = None,
             ornekler: list[dict] | None = None,
             uslup_ornekleri: list[str] | None = None) -> str:
    """`ornekler`: [{"anlatim": "...", "instagram": "...", "shopier": "..."}, ...]"""
    ornekler = ornekler or VARSAYILAN_ORNEKLER
    kelime_blogu = _kelime_blogu(anahtar_kelimeler)
    uslup = uslup_blogu(uslup_ornekleri)

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
{kelime_blogu}{uslup}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

{CIKTI_BICIMI}"""


# ---------------------------------------------------------------------------
# 3) CHAIN-OF-THOUGHT — önce düşün, sonra yaz
# ---------------------------------------------------------------------------
def chain_of_thought(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
                     anahtar_kelimeler: list[str] | None = None,
                     uslup_ornekleri: list[str] | None = None) -> str:
    kelime_blogu = _kelime_blogu(anahtar_kelimeler)
    uslup = uslup_blogu(uslup_ornekleri)
    return f"""{SISTEM_TALIMATI}

ÜRÜN KATEGORİSİ: {kategori}
İSTENEN TON: {ton}
{kelime_blogu}{uslup}
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
# 4) SES → METİN  (üretici ürününü sesli anlatır)
# ---------------------------------------------------------------------------
SES_TALIMATI = """Bu ses kaydında bir üretici, kendi ürettiği ürünü anlatıyor.

Kaydı Türkçe olarak yazıya dök. Kurallar:
- Konuşanın kendi kelimelerini KORU. Düzgün Türkçeye çevirmeye, cümleyi
  güzelleştirmeye veya kısaltmaya çalışma.
- Yalnızca "ııı", "şey", "yani bir de" gibi anlamsız doldurma seslerini at ve
  cümleleri noktalama ile düzenle.
- Kişi eklerini aynen koru: "kendim", "örüyorum", "bahçemizin" gibi kelimeleri
  değiştirme — üreticinin emeğini anlatan kısım tam olarak bunlardır.
- Sayıları söylendiği gibi yazıyla bırak ("yirmi gün", "üç günümü"); rakama çevirme.
- Duymadığın hiçbir bilgiyi EKLEME. Anlaşılmayan yeri [anlaşılmadı] diye işaretle.
- Yalnızca metni yaz; başlık, açıklama veya yorum ekleme."""


# ---------------------------------------------------------------------------
# 5) REELS / TİKTOK SENARYOSU  (video çekimi için plan)
# ---------------------------------------------------------------------------
def reels_senaryosu(anlatim: str, kategori: str, ton: str = "sıcak ve samimi",
                    uslup_ornekleri: list[str] | None = None) -> str:
    uslup = uslup_blogu(uslup_ornekleri)
    return f"""{SISTEM_TALIMATI}

Bu kez görevin farklı: üreticinin telefonuyla tek başına çekebileceği,
20-30 saniyelik bir Reels/TikTok videosu için ÇEKİM PLANI hazırlayacaksın.

Kısıtlar:
- Üretici tek başına, telefonla, evinde çekiyor. Ekip, stüdyo, ışık ekipmanı YOK.
- Yüzünü göstermek zorunda kalmasın; eller ve ürün yeterli olsun.
- Her plan tek cümleyle, yapılabilir biçimde anlatılsın.

ÜRÜN KATEGORİSİ: {kategori}
İSTENEN TON: {ton}
{uslup}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Çıktıyı tam olarak şu Markdown biçiminde ver, başka açıklama ekleme:

**🎣 İlk 3 saniye**
(İzleyiciyi durduracak açılış — ekranda görünecek yazı ya da söylenecek ilk cümle)

**🎬 Çekim planı**
1. (0-5 sn) …
2. (5-12 sn) …
3. (12-20 sn) …
4. (20-30 sn) …

**🎤 Seslendirme metni**
(Üreticinin kendi sesiyle okuyacağı, 25 saniyeyi geçmeyen metin)

**📝 Video açıklaması**
(Gönderi altına yazılacak kısa metin + en fazla 5 hashtag)

**💡 Küçük ipucu**
(Çekimi kolaylaştıracak tek bir pratik öneri)"""


# ---------------------------------------------------------------------------
# 6) FOTOĞRAF ÇEKİM REHBERİ
# ---------------------------------------------------------------------------
def foto_rehberi(anlatim: str, kategori: str) -> str:
    return f"""{SISTEM_TALIMATI}

Bu kez görevin farklı: üreticinin ürününü kendi telefonuyla, evinde, profesyonel
ekipman olmadan nasıl fotoğraflayacağını anlatacaksın.

Kısıtlar:
- Yalnızca telefon kamerası, gün ışığı ve evde bulunabilecek malzemeler.
- Satın alınması gereken hiçbir şey önerme (softbox, reflektör vb. YOK).
- Bu ürüne ÖZEL öneriler ver; genel fotoğrafçılık tavsiyesi verme.

ÜRÜN KATEGORİSİ: {kategori}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Çıktıyı tam olarak şu Markdown biçiminde ver, başka açıklama ekleme:

**📸 Çekmeniz gereken 4 kare**
1. **Ana kare** — …
2. **Detay karesi** — …
3. **Kullanım karesi** — …
4. **Hikâye karesi** — …

**💡 Işık**
(Bu ürün için evde en iyi ışığı nasıl bulacağı — tek paragraf)

**🎨 Arka plan ve düzen**
(Evde bulunabilecek malzemelerle bu ürüne yakışan zemin önerisi)

**⚠️ Kaçınılması gerekenler**
(Bu üründe sık yapılan iki hata)"""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def uslup_blogu(uslup_ornekleri: list[str] | None) -> str:
    """
    Üreticinin kendi yazdığı metinlerden üslup referansı bloğu üretir.

    Arayüzdeki 'Ton Profilim' bölümünde kullanıcı kendi eski paylaşımlarını
    yapıştırır; bu metinler modele "bu kişinin yazım tarzı budur" diye verilir.
    Few-shot'tan farkı: hazır örnek çifti değil, doğrudan üslup referansıdır.
    """
    if not uslup_ornekleri:
        return ""
    temiz = [o.strip() for o in uslup_ornekleri if o and o.strip()]
    if not temiz:
        return ""
    blok = "\n".join(f'  {i}. "{o}"' for i, o in enumerate(temiz, 1))
    return (
        "\nBU ÜRETİCİNİN KENDİ YAZDIĞI METİNLER (üslup referansı):\n"
        f"{blok}\n"
        "Yeni içeriği yazarken bu metinlerin cümle uzunluğunu, samimiyet düzeyini "
        "ve kelime tercihlerini taklit et. İçeriklerini kopyalama — yalnızca ÜSLUBU "
        "al. Bu kişi nasıl yazıyorsa öyle yaz.\n"
    )


def _kelime_blogu(anahtar_kelimeler) -> str:
    """SEO kelimeleri varsa prompt'a eklenecek blok (A4 aşamasında beslenecek)."""
    if not anahtar_kelimeler:
        return ""
    kelimeler = ", ".join(anahtar_kelimeler)
    return (f"\nARAMA VERİSİNDEN GELEN ANAHTAR KELİMELER: {kelimeler}\n"
            "Önce bu kelimelerden ürüne GERÇEKTEN uyanları seç. Uymayanı hiç kullanma "
            "(örn. ürün kumaş değilse 'doğal kumaş' yazma).\n"
            "Uyan kelimelerin HEPSİNİ [SHOPIER] metninde, Instagram metninde ise en az "
            "birini DOĞAL biçimde kullan — insanların arama kutusuna yazdığı biçimiyle.\n"
            "Zorlama, listeleme, art arda dizme; cümle akışı bozulmasın.\n")


# Ton profili için başlangıç örnekleri.
# A3 aşamasında gerçek üreticinin kendi metinleriyle değiştirilecek.
VARSAYILAN_ORNEKLER = [
    {
        # Instagram: kanca = SÜRE. Malzeme yok, kisa, konusma dili.
        # Shopier  : malzeme + sure + kime uygun. Duygusal cumle yok.
        "anlatim": "Keçeden bebek patiği yapıyorum. Yün keçe kullanıyorum, "
                   "boyası doğal. Bir çiftini bir günde bitiriyorum.",
        "instagram": "Bir çift patik, tam bir günüm. Ama o minik ayaklara bakınca "
                     "değiyor.\n"
                     "#keçepatik #elemeği #bebekhediyesi",
        "shopier": "El yapımı keçe bebek patiği. Doğal boyalı yün keçeden elde "
                   "dikilmiştir. Bir çift yaklaşık bir günlük emekle hazırlanır. "
                   "Yeni doğan hediyesi arayanlar ve doğal malzeme tercih eden "
                   "anneler için uygundur.",
    },
    {
        # Instagram: kanca = "sadece iki malzeme" carpiciligi.
        # Shopier  : gramaj, yontem, ne icermedigi, kime uygun.
        "anlatim": "Ev yapımı vişne reçeli. Kendi bahçemizin vişnesi, şeker dışında "
                   "hiçbir şey katmıyorum. 400 gramlık kavanozlarda.",
        "instagram": "İçinde iki şey var: bahçemizin vişnesi ve şeker. Başka hiçbir "
                     "şey.\n"
                     "#evyapımıreçel #vişnereçeli #katkısız",
        "shopier": "Ev yapımı vişne reçeli, 400 g cam kavanozda. Kendi bahçemizde "
                   "yetişen vişnelerden yalnızca şeker eklenerek geleneksel yöntemle "
                   "pişirilmiştir. Koruyucu, renklendirici veya aroma içermez. "
                   "Kahvaltılık doğal reçel arayanlar için.",
    },
]


# Çıktı kalitesini ölçmek için taranan klişe kalıpları.
# uret.klise_sayisi() bu listeyi kullanır; toplu testte metrik olarak raporlanır.
KLISE_KALIPLARI = [
    "ilmeğinde", "sevgiyle hazırlan", "göz nuru",
    "özenli bir dokunuş", "anlamlı bir hediye", "değer katacak", "fark yaratan",
    "ayrı bir sanat eseri", "ayrı bir özen", "emek ve özen", "özenle hazırlan",
    "sizler için", "hayatınıza", "eşsiz bir deneyim", "vazgeçilmez",
]


# Kategoriye göre kullanılabilecek başlangıç anahtar kelimeleri.
# A4 aşamasında pytrends'ten gelen gerçek verilerle değiştirilecek.
KATEGORI_KELIMELERI = {
    "Tekstil / El sanatı": ["el yapımı", "el emeği", "hediyelik", "doğal kumaş"],
    "Gıda":                ["ev yapımı", "katkısız", "doğal", "geleneksel"],
    "Takı / Aksesuar":     ["el yapımı takı", "özel tasarım", "hediye"],
    "Tasarım / Dekorasyon": ["el yapımı dekor", "ev dekorasyonu", "özel tasarım"],
}
