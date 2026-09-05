# Üretken Kadın — Kurulum ve Çalıştırma

Bu rehber, projeyi kendi bilgisayarınızda çalıştırmanız içindir.
**Her ekip üyesi kendi API anahtarını alır — anahtar paylaşılmaz.**

---

## 1. Gemini API anahtarı alın (ücretsiz)

1. https://aistudio.google.com adresine Google hesabınızla girin
2. Sağ üstten **Get API key** → **Create API key**
3. Çıkan anahtarı kopyalayın (uzun bir metin)

> Ücretsiz katman bu proje için fazlasıyla yeterlidir, kart bilgisi istemez.

---

## 2. Projeyi hazırlayın

Klasörü açıp terminalde (PowerShell) şu adımları izleyin:

```bash
# sanal ortam oluştur
python -m venv .venv

# ortamı etkinleştir (Windows PowerShell)
.venv\Scripts\Activate.ps1

# paketleri kur
pip install -r requirements.txt
```

---

## 3. Anahtarınızı tanımlayın

1. `.env.example` dosyasını kopyalayın
2. Kopyanın adını **`.env`** yapın
3. İçini şöyle doldurun:

```
GEMINI_API_KEY=buraya_kendi_anahtariniz
```

> `.env` dosyası `.gitignore` içinde olduğu için **GitHub'a yüklenmez**.
> Anahtarınızı kimseyle paylaşmayın, ekran görüntüsüne almayın.

---

## 4. Çalıştırın

**Önce çekirdeği test edin** (terminalde çıktı verir):

```bash
python src/uret.py
```

Ekranda bir Instagram metni ve bir Shopier açıklaması görüyorsanız çekirdek çalışıyor demektir.

**Sonra arayüzü açın:**

```bash
streamlit run src/app.py
```

Tarayıcıda otomatik açılır (`http://localhost:8501`).

---

## Sorun giderme

| Hata | Çözüm |
|---|---|
| `GEMINI_API_KEY bulunamadı` | `.env` dosyasını oluşturmayı veya içine anahtarı yazmayı unutmuşsunuz |
| `ModuleNotFoundError: google` | `pip install -r requirements.txt` komutunu çalıştırın |
| `ModuleNotFoundError: prompts` | Komutu proje ana klasöründen çalıştırın (`src` içinden değil) |
| `404 ... model is no longer available` | Google eski modeli kapatmış. Hata mesajı hangi modeli önerdiyse onu kullanın: `.env` dosyasına `GEMINI_MODEL=önerilen-model-adı` satırını ekleyin (kodu değiştirmenize gerek yok) |

---

## Dosyalar ne işe yarıyor?

| Dosya | Görevi |
|---|---|
| `src/prompts.py` | Prompt şablonları (zero-shot / few-shot / chain-of-thought) ve etik kısıtlar |
| `src/uret.py` | Gemini çağrısı, çıktının iki kanala ayrıştırılması, SEO kapsam ölçümü |
| `src/app.py` | Streamlit arayüzü — gir, üret, düzenle, onayla |
| `data/ornekler.csv` | Test için 10 örnek ürün anlatımı |
| `.env` | API anahtarınız (GitHub'a gitmez) |
