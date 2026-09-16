# -*- coding: utf-8 -*-
"""
Üretken Kadın — KVKK aydınlatma ve açık rıza metinleri

Neden var: "Veri Araştırması" dökümanı, ses verisi işlemenin KVKK açısından açık
bir eksik olduğunu belirtir. İki nokta kritiktir:
  1. Ses kaydı kimlik/duygu amaçlı işlenirse KVKK m.6 kapsamında ÖZEL NİTELİKLİ
     (biyometrik) veri sayılabilir → AÇIK RIZA gerekir.
  2. Veri bulut tabanlı bir API'ye (Google Gemini) gönderildiği için KVKK m.9
     kapsamında YURT DIŞINA AKTARIM söz konusudur → aydınlatma zorunludur.

Bu modül yalnızca METİN ve yardımcı içerir; işlevsel rıza kapısı arayüzde
(app.py) uygulanır. Böylece metin tek yerden yönetilir ve testlerde kullanılabilir.

Tasarım ilkesi: veri minimizasyonu. Ses/metin yalnızca içerik üretimi için,
o oturum boyunca işlenir; kalıcı olarak saklanmaz.
"""

from __future__ import annotations

# Kısa, kullanıcı dostu aydınlatma (ses girişinden önce gösterilir)
SES_AYDINLATMA = """**Sesli anlatım ve verileriniz (KVKK)**

Ses kaydınızı yalnızca **metne çevirmek ve içerik üretmek** için kullanırız.
Bunu yapabilmek için kayıt, çeviri sırasında Google Gemini servisine gönderilir
(**yurt dışına aktarım** — KVKK m.9).

- Kaydınız kimlik doğrulama veya duygu analizi için **kullanılmaz**.
- Kaydınız tarafımızca **kalıcı olarak saklanmaz**; işlem bitince oturumdan silinir.
- İstemezseniz sesli anlatımı kullanmak **zorunda değilsiniz** — yazarak da
  anlatabilirsiniz (aynı sonuç).

Devam etmek için aşağıdaki açık rıza kutusunu işaretlemeniz gerekir."""

SES_RIZA_ETIKETI = ("Ses kaydımın metne çevrilmek üzere Google Gemini'ye "
                    "aktarılmasına ve bu iş için işlenmesine **açık rıza** veriyorum.")

# Metin girişi için hafif aydınlatma (bilgilendirme; ayrı rıza kutusu gerektirmez)
METIN_AYDINLATMA = ("Yazdığınız anlatım, içerik üretmek için Google Gemini'ye "
                    "gönderilir (yurt dışına aktarım). Kişisel/hassas bilgi "
                    "(ad-soyad, adres, telefon) yazmayın — buna gerek yok.")

# Görsel stüdyosunda fotoğraf yükleme alanının altında gösterilir
FOTO_AYDINLATMA = ("Yalnızca ürün fotoğrafı yükleyin; insan yüzü, adres ya da kişisel bilgi içeren "
                   "fotoğraf yüklemeyin. Hızlı düzeltme, paylaşım görseli ve katalog bu sunucuda "
                   "hazırlanır. \"Fotoğraftan anlatım\" ise fotoğrafı "
                   "Google Gemini'ye gönderir (yurt dışına aktarım). Fotoğraflar kalıcı olarak "
                   "saklanmaz; sayfayı kapatınca silinir.")

# Pano → Kaydet / yükle bölümünde gösterilir
KAYIT_ACIKLAMA = ("Planınız hesabınızda otomatik olarak saklanır. İsterseniz buradan bir kopyasını "
                  "cihazınıza indirebilir ya da daha önce indirdiğiniz bir dosyayı yükleyebilirsiniz. "
                  "Dosyada anlatımlarınız ve içerikleriniz bulunur — başkalarıyla paylaşmayın.")

# Kayıt formunda gösterilir; kayıt için açık rıza kutusu işaretlenmelidir
HESAP_AYDINLATMA = """**Hesabınız ve verileriniz (KVKK)**

- **Ne saklıyoruz?** E-posta adresiniz, adınız ve şifrenizin geri çevrilemez özeti (şifrenizin
  kendisini biz de göremeyiz); hazırladığınız içerikler, paylaşım takviminiz, ton profiliniz ve
  kaydettiğiniz fiyatlar. **Fotoğraflarınız ve ses kayıtlarınız saklanmaz.**
- **Ne amaçla?** Hesabınıza her girdiğinizde içeriklerinize kaldığınız yerden devam edebilmeniz için.
  Başka amaçla kullanılmaz, kimseyle paylaşılmaz, reklam için kullanılmaz.
- **Nerede?** Yurt dışındaki bir bulut veritabanı hizmetinde (Neon) saklanır; bu, KVKK m.9
  kapsamında yurt dışına aktarımdır. İçerik üretimi için anlatımınız ayrıca Google Gemini'ye gönderilir.
- **Çerez:** Sayfayı yenileyince girişiniz kapanmasın diye tarayıcınıza yalnızca bir oturum çerezi
  koyarız (en fazla 30 gün; çıkış yapınca silinir). Reklam ya da izleme çerezi kullanmayız.
- **Ne kadar süre?** Siz hesabınızı silene kadar.
- **Haklarınız (KVKK m.11):** Hesabım sayfasından verilerinizi indirebilir, şifrenizi değiştirebilir
  ve hesabınızı tüm verileriyle birlikte kalıcı olarak silebilirsiniz."""

HESAP_RIZA_ETIKETI = ("Aydınlatma metnini okudum; hesap bilgilerimin ve hazırladığım içeriklerin bu "
                      "amaçla yurt dışındaki bir veritabanında saklanmasına **açık rıza** veriyorum.")

# Firmalar için API sayfasındaki başvuru formunda gösterilir
BASVURU_AYDINLATMA = """**Başvuru bilgileriniz (KVKK)**

- **Ne saklıyoruz?** Kurum adı ve türü, yetkili adı, iş e-postası, web sitesi, kullanım amacı ve
  tahmini kullanım miktarı.
- **Ne amaçla?** Yalnızca başvurunuzu değerlendirmek ve size API anahtarıyla ilgili dönüş yapmak için.
  Pazarlama amacıyla kullanılmaz, kimseyle paylaşılmaz.
- **Nerede?** Yurt dışındaki bir bulut veritabanı hizmetinde (Neon) saklanır; bu, KVKK m.9 kapsamında
  yurt dışına aktarımdır.
- **Ne kadar süre?** Başvurunuz sonuçlandıktan sonra en fazla 1 yıl; siz isterseniz daha önce silinir.
- **Haklarınız (KVKK m.11):** Bilgilerinizin düzeltilmesini ya da silinmesini, başvuru numaranızla
  birlikte bize yazarak isteyebilirsiniz."""

BASVURU_RIZA_ETIKETI = ("Aydınlatma metnini okudum; başvuru bilgilerimin bu amaçla yurt dışındaki bir "
                        "veritabanında saklanmasına **açık rıza** veriyorum.")

# Ayrıntılı politika (Etik/KVKK sekmesinde gösterilir)
POLITIKA_MADDELERI = [
    ("Hangi veriyi işliyoruz?",
     "Hesabınız için e-posta adresinizi, adınızı ve şifrenizin geri çevrilemez özetini; ayrıca "
     "ürününüzü anlattığınız ses veya metni. Reklam kimliği ya da konum toplamayız."),
    ("Ne amaçla?",
     "Yalnızca pazarlama içeriği (Instagram/Shopier metni, Reels planı, foto "
     "rehberi) üretmek ve hesabınızda saklamak için. Başka amaçla kullanılmaz."),
    ("Nereye aktarılıyor?",
     "İçerik üretimi Google Gemini API üzerinden yapılır; hesap bilgileriniz ve içerikleriniz "
     "yurt dışındaki bir veritabanı hizmetinde (Neon) saklanır. İkisi de KVKK m.9 kapsamında "
     "yurt dışına aktarımdır; bu yüzden ses için ve kayıt olurken açık rıza alırız."),
    ("Ne kadar saklıyoruz?",
     "Hesabınızdaki içerikler, paylaşım takviminiz, ton profiliniz ve kaydettiğiniz fiyatlar siz "
     "hesabınızı silene kadar saklanır. Fotoğraf ve ses kayıtları saklanmaz; işlendikten sonra "
     "sayfayı kapatınca silinir."),
    ("Haklarınız",
     "KVKK m.11 kapsamında verinize erişme, düzeltme ve silinmesini isteme haklarınız vardır. "
     "Hesabım sayfasından verilerinizi indirebilir ve hesabınızı kalıcı olarak silebilirsiniz."),
    ("Veri minimizasyonu",
     "Sistemi, işini görecek en az veriyle çalışacak biçimde tasarladık; hassas "
     "bilgi istemez ve toplamayız."),
]
