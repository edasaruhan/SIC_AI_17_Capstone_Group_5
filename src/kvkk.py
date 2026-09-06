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

# Ayrıntılı politika (Etik/KVKK sekmesinde gösterilir)
POLITIKA_MADDELERI = [
    ("Hangi veriyi işliyoruz?",
     "Yalnızca ürününüzü anlattığınız ses veya metni. Reklam kimliği, konum ya da "
     "iletişim bilgisi toplamayız."),
    ("Ne amaçla?",
     "Yalnızca pazarlama içeriği (Instagram/Shopier metni, Reels planı, foto "
     "rehberi) üretmek için. Başka amaçla kullanılmaz."),
    ("Nereye aktarılıyor?",
     "İçerik üretimi Google Gemini API üzerinden yapılır; bu, KVKK m.9 kapsamında "
     "yurt dışına veri aktarımı anlamına gelir. Bu yüzden ses için açık rıza alırız."),
    ("Ne kadar saklıyoruz?",
     "Anlatımınız ve üretilen içerik yalnızca oturum boyunca bellekte tutulur; "
     "sayfayı kapatınca silinir. Sunucumuzda kalıcı kayıt tutulmaz."),
    ("Haklarınız",
     "KVKK m.11 kapsamında verinize erişme, düzeltme ve silinmesini isteme "
     "haklarınız vardır. Sesli anlatımı hiç kullanmama seçeneğiniz her zaman açıktır."),
    ("Veri minimizasyonu",
     "Sistemi, işini görecek en az veriyle çalışacak biçimde tasarladık; hassas "
     "bilgi istemez ve toplamayız."),
]
