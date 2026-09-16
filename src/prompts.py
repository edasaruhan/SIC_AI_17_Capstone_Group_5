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
# 7) EK FORMATLAR — Instagram hikâyesi, WhatsApp, hashtag seti
# ---------------------------------------------------------------------------
_EK_GOREVLER = {
    "story": """Bu kez görevin farklı: Instagram HİKÂYESİ (story) için 3 karelik bir dizi
hazırlayacaksın.

Kısıtlar:
- Her karedeki ekran yazısı en fazla 8 kelime olsun; hikâyede uzun yazı okunmaz.
- Görüntüler, üreticinin telefonuyla evinde çekebileceği şeyler olsun.
- Fiyat, indirim, kargo süresi gibi anlatımda OLMAYAN bilgileri yazma.
- Son karedeki soru, anlatımda olmayan bir seçenek (renk, beden, çeşit) varmış gibi
  sormasın; ürünün kendisi ya da kullanımı hakkında olsun.""",

    "whatsapp": """Bu kez görevin farklı: üreticinin WhatsApp'ta kullanacağı iki kısa metin
hazırlayacaksın.

Kısıtlar:
- WhatsApp'ta insanlar tanıdıklarıyla yazışır: resmi değil, samimi ve kısa yaz.
- Fiyat anlatımda yoksa fiyat YAZMA; yerine [fiyat] yaz ki üretici kendisi doldursun.
- Kargo, teslim süresi, indirim gibi anlatımda OLMAYAN bilgileri ekleme.""",

    "hashtag": """Bu kez görevin farklı: Instagram için HASHTAG SETİ hazırlayacaksın.

Kısıtlar:
- Hashtag'ler boşluksuz ve küçük harf olsun.
- Kelimelerin Türkçe yazımını AYNEN koru; yalnızca boşlukları kaldır (el örgüsü →
  #elörgüsü, el emeği → #elemeği). Harf ekleme, çıkarma ya da değiştirme; ğ, ü, ş, ı,
  ö, ç harflerini olduğu gibi bırak.
- Her hashtag tek bir kavram olsun; kelimeleri zincirleme birleştirme
  (#elörgüsübebekbattaniyesi değil, #elörgüsü #bebekbattaniyesi).
- "Göz nuru", "sevgiyle" gibi yasak kalıpları hashtag olarak da kullanma.
- Anlatımda olmayan bir özelliği hashtag yapma (ürün organik denmediyse #organik YAZMA).
- "#eniyi", "#mucize", "#şifalı", "#garantili" gibi iddia taşıyan etiket kullanma.
- Üretici bir şehir ya da yöre söylemediyse yer adı hashtag'i UYDURMA.""",
}

_EK_CIKTILAR = {
    "story": """**1. kare — merak**
🖼️ Görüntü: …
✍️ Ekrandaki yazı: …

**2. kare — emek**
🖼️ Görüntü: …
✍️ Ekrandaki yazı: …

**3. kare — soru**
🖼️ Görüntü: …
✍️ Ekrandaki yazı: …
🗳️ Etkileşim çıkartması: (anket ya da soru kutusuna yazılacak tek soru)""",

    "whatsapp": """**💬 Durum yazısı**
(Ürün fotoğrafının altına, en fazla 2 kısa cümle)

**📩 Soran müşteriye mesaj**
(Ürünü soran birine gönderilecek 3-4 kısa satır: ne olduğu, nasıl yapıldığı,
[fiyat], sipariş için ne yapması gerektiği)""",

    "hashtag": """**🧶 Ürünü anlatan**
(4-5 hashtag, tek satırda)

**🔎 Arayanların yazdığı**
(4-5 hashtag, tek satırda)

**🤝 Topluluk**
(2-3 hashtag — el emeğiyle üretim yapanların ortak etiketleri)

**📋 Bu gönderi için en iyi 5**
(Yukarıdakilerden seçilmiş 5 hashtag, kopyalamak için tek satırda)""",
}

EK_BICIMLER = tuple(_EK_GOREVLER)


def ek_format(anlatim: str, kategori: str, bicim: str,
              anahtar_kelimeler: list[str] | None = None,
              uslup_ornekleri: list[str] | None = None) -> str:
    """Instagram hikâyesi / WhatsApp / hashtag seti prompt'u. Etik kurallar ortaktır."""
    if bicim not in _EK_GOREVLER:
        raise ValueError(f"Bilinmeyen biçim: {bicim}")
    kelimeler = ""
    if bicim == "hashtag" and anahtar_kelimeler:
        kelimeler = ("\nARAMA VERİSİNDEN GELEN ANAHTAR KELİMELER: "
                     f"{', '.join(anahtar_kelimeler)}\n"
                     "Bunlardan ürüne GERÇEKTEN uyanları boşluksuz hashtag'e çevirip "
                     "'Arayanların yazdığı' grubunda kullan; uymayanı kullanma. Kelimedeki "
                     "malzeme anlatımda geçmiyorsa o kelime uymaz (örn. ürün iplikten "
                     "örülüyorsa 'doğal kumaş' uymaz).\n")
    return f"""{SISTEM_TALIMATI}

{_EK_GOREVLER[bicim]}

ÜRÜN KATEGORİSİ: {kategori}
{kelimeler}{uslup_blogu(uslup_ornekleri)}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Çıktıyı tam olarak şu Markdown biçiminde ver, başka açıklama ekleme:

{_EK_CIKTILAR[bicim]}"""


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


# ---------------------------------------------------------------------------
# 8) GÖRSEL STÜDYOSU — fotoğraftan anlatım
# ---------------------------------------------------------------------------
def foto_anlatim(kategori: str) -> str:
    return f"""{SISTEM_TALIMATI}

Bu kez görevin farklı: sana üreticinin ürün FOTOĞRAFI verildi. Fotoğrafa bakarak ürünü
tanımlayacak ve üreticinin anlatımını zenginleştirmesine yardım edeceksin.

Kurallar:
- Yalnızca fotoğrafta GÖRDÜĞÜN şeyleri yaz: ürün türü, renkler, desen, doku, biçim, görünen ayrıntılar.
- Malzeme, içerik, ağırlık, ölçü, üretim süresi ya da teknik fotoğraftan kesin anlaşılamaz;
  bunları UYDURMA, "sorular" listesinde üreticiye sor.
- "anlatim_taslagi": üreticinin ağzından, birinci tekil kişiyle 2-3 kısa cümle; yalnızca görünen
  özellikleri kullan. Bilinmeyen yerleri köşeli parantezle bırak: [malzeme], [kaç günde yaptığınız].
- Fotoğrafta ürün seçilemiyorsa "urun" alanına "belirsiz" yaz.
- Fotoğrafta insan yüzü ya da kişisel bilgi varsa bunları tarif etme.

ÜRÜN KATEGORİSİ (üreticinin seçtiği): {kategori}

Yalnızca şu JSON'u ver:
{{"urun": "", "gorunen_ozellikler": [], "renkler": [], "anlatim_taslagi": "", "sorular": []}}"""



# ---------------------------------------------------------------------------
# 9) SATIŞ ARAÇLARI — müşteriye cevap, pazaryeri ilanı, çeviri, kampanya
# ---------------------------------------------------------------------------
def musteri_cevabi(mesaj: str, urun_bilgisi: str, ton: str) -> str:
    return f"""{SISTEM_TALIMATI}

Bu kez görevin farklı: bir müşterinin üreticiye yazdığı mesaja, üretici adına kısa bir cevap
TASLAĞI hazırlayacaksın. Üretici okuyup düzenleyecek, sonra gönderecek.

Kurallar:
- Nazik, {ton} ve kısa yaz (en fazla 5 cümle); WhatsApp ya da Instagram mesajı gibi.
- Fiyat, kargo süresi, stok, indirim, iade koşulu gibi bilgiler ÜRÜN BİLGİSİNDE yoksa UYDURMA;
  yerine köşeli parantezle yer tutucu yaz: [fiyat], [kargo süresi], [stok durumu] gibi.
- Baskı kuran satış dili kullanma ("son şans", "hemen alın" gibi).
- Müşteri şikâyet ediyorsa önce anlayışla karşıla ve çözüm için bilgi iste; para iadesi ya da
  tazminat sözü verme.
- Müşterinin kişisel bilgilerini (ad, adres, telefon) cevaba yazma.

ÜRÜN BİLGİSİ (üreticinin kendi anlatımı):
\"\"\"{urun_bilgisi or "Verilmedi."}\"\"\"

MÜŞTERİNİN MESAJI:
\"\"\"{mesaj}\"\"\"

Yalnızca şu JSON'u ver:
{{"cevap": ""}}"""


def pazaryeri_ilani(anlatim: str, kategori: str, platform: str, dil: str,
                    anahtar_kelimeler: list[str] | None = None) -> str:
    if dil == "en":
        kural = ("Bu görevde 6. kural (Türkçe yazma) geçerli değil: ilanı İNGİLİZCE yaz (Etsy). "
                 "Başlık en fazla 140 karakter olsun ve alıcının arama kutusuna yazacağı kelimelerle "
                 "başlasın. En fazla 13 etiket ver; her etiket en fazla 20 karakterlik İngilizce "
                 "arama ifadesi olsun. Özellikler ve açıklama da İngilizce olsun.")
    else:
        kural = ("İlanı TÜRKÇE yaz. Başlık en fazla 100 karakter olsun: ürün türü + öne çıkan özellik "
                 "+ (anlatımda varsa) malzeme. En fazla 15 etiket ver; alıcının arama kutusuna "
                 "yazacağı Türkçe ifadeler olsun.")
    kelimeler = ""
    if anahtar_kelimeler:
        kelimeler = ("\nARAMA VERİSİNDEN GELEN ANAHTAR KELİMELER: " + ", ".join(anahtar_kelimeler) +
                     "\nBunlardan ürüne GERÇEKTEN uyanları başlıkta ya da açıklamada doğal biçimde kullan.\n")
    return f"""{SISTEM_TALIMATI}

Bu kez görevin farklı: üreticinin anlatımından {platform} için ÜRÜN İLANI hazırlayacaksın.

Kurallar:
- {kural}
- "ozellikler": madde madde, "Özellik: değer" biçiminde (ör. "Malzeme: organik pamuk ipliği").
  Yalnızca anlatımda geçen bilgileri yaz.
- Ölçü, ağırlık, yıkama/saklama talimatı, renk seçenekleri gibi ilanda olması gereken ama anlatımda
  OLMAYAN bilgileri "eksik_bilgiler" listesine Türkçe yaz; bunları UYDURMA.
- "aciklama": 2-4 kısa paragraf; bilgi verici ve sakin; emeği ve üretim sürecini anlat.
{kelimeler}
ÜRÜN KATEGORİSİ: {kategori}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Yalnızca şu JSON'u ver:
{{"baslik": "", "ozellikler": [], "aciklama": "", "etiketler": [], "eksik_bilgiler": []}}"""


def ceviri(metin: str, hedef_dil: str = "İngilizce") -> str:
    return f"""Aşağıdaki Türkçe ürün metnini {hedef_dil}ye çevir.
- Anlamı koru; bilgi ekleme ya da çıkarma, abartı katma.
- El emeği ürün satışına uygun, doğal ve sade bir dil kullan.
- Hashtag'leri ve köşeli parantezli yer tutucuları ([fiyat] gibi) anlamına uygun biçimde çevir.
- Yalnızca çeviriyi yaz; açıklama ekleme.

METİN:
\"\"\"{metin}\"\"\""""


def kampanya_onerisi(gun_adi: str, tarih_metni: str, kalan_gun: int, anlatim: str,
                     kategori: str) -> str:
    return f"""{SISTEM_TALIMATI}

Bu kez görevin farklı: üretici için "{gun_adi}" ({tarih_metni}, {kalan_gun} gün kaldı) özel
gününe yönelik küçük bir kampanya planı hazırlayacaksın.

Kurallar:
- Sahte aciliyet ya da uydurma indirim yazma ("son 2 ürün", "%50 indirim" gibi). İndirim
  önerirsen oranı [indirim oranı] diye yer tutucu bırak.
- Ürün bu güne gerçekten uymuyorsa bunu dürüstçe söyle ve uygun bir açı öner (hediye paketi
  gibi) ya da bu günü atlamayı öner.
- Yalnızca anlatımdaki bilgileri kullan.

ÜRÜN KATEGORİSİ: {kategori}
ÜRETİCİNİN KENDİ ANLATIMI:
\"\"\"{anlatim}\"\"\"

Çıktıyı tam olarak şu Markdown biçiminde ver, başka açıklama ekleme:

**🎯 Kampanya fikri**
(1-2 cümle)

**📅 Paylaşım planı**
1. **10 gün önce:** …
2. **3 gün önce:** …
3. **Özel gün:** …

**📱 Örnek gönderi metni**
(Özel güne uygun, en fazla 3 cümle ve en fazla 5 hashtag)

**🎁 Küçük dokunuş**
(Paketleme ya da not kartı gibi, maliyeti düşük tek öneri)"""
