# Üretken Kadın API — İş Ortağı Rehberi

Üretken Kadın'ın içerik motorunu kendi ürünlerine eklemek isteyen kurumlar için REST API.
Streamlit arayüzüyle **aynı çekirdeği** kullanır: aynı etik kurallar, aynı hashtag süzgeci,
aynı kalite ön filtresi.

**Kimler için?** E-ticaret ve pazaryeri platformları (satıcı paneline "açıklamamı yaz"
düğmesi), kadın kooperatifleri ve üretici ağları, belediye/STK girişimcilik programları.

**Başlamak için 3 adım:** ① Bize başvurun; kurumunuza özel API anahtarı ve günlük kota
tanımlansın · ② `/docs` sayfasında anahtarınızla istekleri canlı deneyin · ③ Kendi sunucunuza
ekleyin; üretilen metni üreticiye onaylatarak yayımlayın.

> Canlı, denenebilir belge: sunucu adresinin sonuna `/docs` ekleyin (Swagger arayüzü).

---

## 1. Hızlı başlangıç

```bash
curl -X POST https://API-ADRESI/v1/icerik \
  -H "X-API-Key: uk_..." \
  -H "Content-Type: application/json" \
  -d '{"anlatim": "El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, tamamen elde örüyorum.", "kategori": "Tekstil / El sanatı"}'
```

```python
import httpx

yanit = httpx.post(
    "https://API-ADRESI/v1/icerik",
    headers={"X-API-Key": "uk_..."},
    json={"anlatim": "El örgüsü bebek battaniyesi yapıyorum. ...", "kategori": "Tekstil / El sanatı"},
    timeout=90,
)
yanit.raise_for_status()
icerik = yanit.json()
print(icerik["instagram"], icerik["shopier"], sep="\n\n")
```

```javascript
// Node.js 18+ — anahtar ortam değişkeninde, istek sunucu tarafından atılır
const yanit = await fetch("https://API-ADRESI/v1/icerik", {
  method: "POST",
  headers: { "X-API-Key": process.env.UK_API_KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ anlatim: "El örgüsü bebek battaniyesi yapıyorum. ...", kategori: "Tekstil / El sanatı" }),
  signal: AbortSignal.timeout(90_000),
});
if (!yanit.ok) throw new Error((await yanit.json()).hata.mesaj);
const icerik = await yanit.json();
```

Yanıt (örnek; metinler her çağrıda farklıdır):

```json
{
  "instagram": "Anneannemden öğrendiğim desen, üç günlük emek...\n#elörgüsü #bebekbattaniyesi",
  "shopier": "El örgüsü bebek battaniyesi. Organik pamuk ipliğiyle tamamen elde örülür...",
  "model": "gemini-3.5-flash-lite",
  "anahtar_kelimeler": ["el yapımı", "el emeği", "hediyelik", "doğal kumaş"],
  "anahtar_kelime_kaynagi": "önbellek",
  "metrikler": {"seo_kapsami": 2, "anahtar_kelime_sayisi": 4, "klise_sayisi": 0, "kanal_benzerligi": 0.12},
  "kalite": {"hazir": true, "olasilik": 0.87, "etiket": "Onaya hazır", "gerekceler": []},
  "uyari": "Bu içerik yapay zekâ ile üretildi; yayımlanmadan önce üretici tarafından okunup onaylanmalıdır."
}
```

---

## 2. Kimlik doğrulama

- Her istekte `X-API-Key: uk_...` başlığı gönderilir.
- Anahtarı **yalnızca kendi sunucunuzdan** kullanın. Tarayıcıya, mobil uygulamaya ya da
  herkese açık koda koymayın — anahtarı gören herkes kotanızı harcayabilir.
- Anahtarlarınızı biz de göremeyiz: sistemde yalnızca özetleri (SHA-256) tutulur. Anahtar
  kaybolursa ya da sızarsa iptal edip yenisini veririz.

---

## 3. Uç noktalar

| Yöntem | Yol | Ne yapar | Günlük kotadan düşer mi? |
|---|---|---|---|
| `POST` | `/v1/icerik` | Anlatımdan Instagram gönderisi + Shopier açıklaması, metrikler ve kalite ön filtresi | Evet (1) |
| `POST` | `/v1/format` | `story` (3 karelik hikâye), `whatsapp`, `hashtag`, `reels` (video planı), `foto` (fotoğraf rehberi) | Evet (1) |
| `POST` | `/v1/transkript` | Sesli anlatımı yazıya döker; konuşanın kelimeleri korunur. `multipart/form-data`: `ses` + `acik_riza=true` | Evet (1) |
| `POST` | `/v1/kalite` | Hazır bir metin "onaya hazır" mı? Gerekçeler ve öznitelikler | Hayır |
| `GET` | `/v1/anahtar-kelimeler?kategori=...` | Kategori için arama kelimeleri (Google Trends, 7 gün önbellek) | Hayır |
| `POST` | `/v1/takvim.ics` | Paylaşım planından telefon takvimine eklenen `.ics` dosyası | Hayır |
| `GET` | `/v1/kullanim` | Bugünkü kota kullanımınız | Hayır (hız sınırına da sayılmaz) |
| `GET` | `/saglik` | Sunucu ayakta mı? (anahtar gerekmez) | — |

**Kategoriler:** `Tekstil / El sanatı` · `Gıda` · `Takı / Aksesuar` · `Tasarım / Dekorasyon`

**Sınırlar:** anlatım 20–4000 karakter · üslup örneği en fazla 3 (her biri 1000 karakter) ·
ses dosyası en fazla 10 MB (wav, mp3, aiff, aac, ogg, flac) · takvimde en fazla 100 öğe.
Tanımlanmamış alan gönderilirse istek reddedilir (yazım hatalarını erken yakalamak için).

**Süre:** `/v1/icerik` genellikle birkaç saniyede döner. `trends_kullan: true` (varsayılan) ve
önbellek boşsa Google Trends sorgusu 15–20 saniye ekleyebilir; `ozenli: true` daha yavaştır
(sunucu en fazla ~30 sn bekler, sonra hızlı modele geçer). İstemci zaman aşımını **90 sn** yapın.

---

## 4. Kota ve hız sınırı

- **Günlük kota:** yapay zekâ çağıran istekler düşer; Türkiye saatiyle gece yarısı yenilenir.
- **Dakikalık sınır:** kayan 60 saniyede tüm `/v1` istekleri sayılır.
- Her yanıtta `X-Kota-Limit` ve `X-Kota-Kalan` başlıkları döner.
- Sınır aşılınca `429` + `Retry-After` (saniye) döner: `kota_asildi` ya da `hiz_siniri`.
- **Sizden kaynaklanmayan hatalar kotadan düşmez:** model yoğunluğu (`503`), üretim hatası
  (`502`), sunucu hatası (`500`) ve doğrulama hataları (`422`) harcanan hakkı geri verir.

---

## 5. Hata kodları

Tüm hatalar aynı biçimdedir: `{"hata": {"kod": "...", "mesaj": "..."}}`

| HTTP | `kod` | Anlamı | Ne yapmalı? |
|---|---|---|---|
| 401 | `anahtar_yok` / `anahtar_gecersiz` | Başlık yok ya da anahtar iptal edilmiş | Anahtarı kontrol edin |
| 400 | `riza_gerekli` | Ses için `acik_riza=true` gönderilmedi | Konuşandan açık rıza alın |
| 413 | `istek_cok_buyuk` / `ses_cok_buyuk` | Gövde 12 MB ya da ses 10 MB üstü | Dosyayı küçültün |
| 415 | `desteklenmeyen_ses` | Ses türü desteklenmiyor | wav/mp3/aiff/aac/ogg/flac |
| 422 | `gecersiz_istek` | Alan eksik/hatalı; `ayrintilar` hangi alan olduğunu söyler | İsteği düzeltin (tekrar denemek işe yaramaz) |
| 429 | `kota_asildi` / `hiz_siniri` | Günlük kota ya da dakikalık sınır | `Retry-After` kadar bekleyin |
| 502 | `model_hatasi` | İçerik üretilemedi | Bir kez tekrar deneyin |
| 503 | `model_yogun` / `kalite_modeli_yok` | Model geçici olarak yoğun | `Retry-After` sonra tekrar deneyin |
| 500 | `sunucu_hatasi` / `yapilandirma_hatasi` | Bizden kaynaklı | Bize bildirin |

Güvenlik gereği hata yanıtları gönderdiğiniz metni **geri yansıtmaz**.

---

## 6. KVKK, etik ve sorumluluklar

**Bizim yaptıklarımız**
- İstek gövdeleri (anlatım, ses, üretilen metin) sunucuda **saklanmaz** ve **günlüğe yazılmaz**;
  günlükte yalnızca yol, durum kodu, iş ortağı adı ve süre bulunur.
- İçerik üretimi için veri **Google Gemini API**'ye iletilir — bu, KVKK m.9 kapsamında
  **yurt dışına aktarımdır**.
- Etik kurallar her çağrıda uygulanır: uydurma özellik, "mucize/garanti" gibi ispatsız iddia,
  gıdada sağlık iddiası yazılmaz; hashtag'ler kural tabanlı süzgeçten geçer.

**İş ortağının yapması gerekenler**
- Son kullanıcılarınızı (üreticileri) verilerinin yapay zekâ ile işlendiği ve yurt dışına
  aktarıldığı konusunda **aydınlatın**.
- Ses göndermeden önce konuşan kişiden **açık rıza** alın ve `acik_riza=true` gönderin.
- Anlatımlara ad, telefon, adres gibi kişisel veri koymamaları için kullanıcıyı yönlendirin.
- Üretilen içeriği üreticinin **onayı olmadan yayımlamayın** (her yanıttaki `uyari` alanı).

> Taraflardan hangisinin veri sorumlusu, hangisinin veri işleyen olduğu ve yurt dışına aktarımın
> hukuki dayanağı sözleşme aşamasında bir **hukuk danışmanıyla** netleştirilmelidir.
> Gemini API'nin **ücretsiz katman** koşullarında gönderilen içerik Google tarafından ürün
> geliştirme amacıyla kullanılabilir; iş ortağı trafiği için **ücretli katman** kullanılmalıdır
> (güncel koşulları Google'ın Gemini API şartlarından kontrol edin).

---

## 7. Sürümleme

- `/v1` kararlıdır. Uyumu bozan değişiklikler `/v2` altında yayımlanır.
- Yanıtlara **yeni alanlar eklenebilir**; istemciniz tanımadığı alanları yok saymalıdır.

---

# İşletim rehberi (Üretken Kadın ekibi için)

## Anahtar oluşturma ve iptal

```bash
python src/api_guvenlik.py yeni --ad "Kooperatif A" --kota 500 --dakika 30
python src/api_guvenlik.py liste
python src/api_guvenlik.py sil --ad "Kooperatif A"
```

`yeni` komutu anahtarı **yalnızca bir kez** gösterir ve özetini `api_anahtarlari.json`'a yazar
(bu dosya `.gitignore`'da). Anahtarı iş ortağına güvenli bir kanaldan iletin (e-posta gövdesine
düz metin yazmayın). Bulut ortamı için komutun yazdırdığı JSON'u `API_ANAHTARLARI` ortam
değişkenine koyun; iptalden sonra bu değişkeni de güncelleyin.

Örnek paketler (kota değerleri serbestçe ayarlanır): **Deneme** 50/gün · **Kooperatif**
500/gün · **Platform** 5000/gün. Kotayı belirlerken Gemini API'nin kendi hız sınırlarını da
göz önünde bulundurun.

## Yerelde çalıştırma

```bash
pip install -r requirements-api.txt
uvicorn api:app --app-dir src --reload
```

`http://127.0.0.1:8000/docs` adresinden denenir. `GEMINI_API_KEY` `.env`'den okunur.

## Testler (anahtar ve internet gerektirmez)

```bash
python tests/test_api.py
```

## Docker

```bash
docker build -t uretken-kadin-api .
docker run -p 8000:8000 --env-file .env uretken-kadin-api
```

İmaj `.env` ve `api_anahtarlari.json` dosyalarını **içermez** (`.dockerignore`); gizli bilgiler
çalıştırırken ortam değişkeni olarak verilir.

## Render'a yayınlama

1. Render → **New → Web Service** → GitHub deposunu bağlayın. Depo özel olduğu için Render'a
   erişim izni depo yöneticisi (Tuğçe) tarafından verilmelidir.
2. Çalışma ortamı: **Docker** (depodaki `Dockerfile` kullanılır).
3. **Environment** bölümüne `GEMINI_API_KEY` ve `API_ANAHTARLARI` ekleyin.
4. **Health Check Path:** `/saglik`
5. Ücretsiz örnekler bir süre istek gelmeyince uykuya geçer ve ilk istek yavaşlar; iş ortakları
   için ücretli örnek kullanın.

## Google Cloud Run'a yayınlama

```bash
gcloud run deploy uretken-kadin-api --source . --region europe-west1 \
  --max-instances 1 \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,API_ANAHTARLARI=api-anahtarlari:latest
```

Gizli değerleri önce Secret Manager'a ekleyin. Cloud Run `PORT` değişkenini kendisi verir;
`Dockerfile` bunu kullanır.

## Ölçekleme

Kota ve hız sınırı sayaçları **bellekte** tutulur. Bu yüzden:

- API **tek süreç, tek örnek** çalışmalıdır (`--workers 1`, Cloud Run'da `--max-instances 1`).
  Birden çok örnekte her örnek kendi sayacını tutar ve gerçek kota katlanır.
- Sunucu yeniden başlarsa günün sayaçları sıfırlanır.
- Trafik tek örneği aşarsa sayaçlar Redis gibi paylaşılan bir depoya taşınmalıdır
  (`api_guvenlik.Sayac` ile aynı arayüz: `dene`, `iade`, `kullanilan`).
- Geçersiz anahtarla deneme yapan istemciler sayılmaz; kaba kuvvet denemelerine karşı
  platformun (Render/Cloud Run/Cloudflare) IP tabanlı sınırlaması açılmalıdır.

## Bilinen sınırlar

- Kalite ön filtresi **prototip etiketli veriyle** eğitilmiştir; kesin karar değil, gözden
  geçirme önceliği içindir. Sunucu açılışında bellekte eğitilir (birkaç saniye).
- Google Trends sık `429` döndürür; bu durumda sabit kategori kelimelerine düşülür
  (`anahtar_kelime_kaynagi: "varsayılan"`).
- Docker imajı yerelde derlenip denendi (15.09.2026): imaj ~800 MB, ilk derleme ~5 dk, açılış
  ~2 sn; tüm uç noktalar gerçek Gemini ile çalıştı, imajda `.env`/anahtar dosyası yok, root
  olmayan kullanıcıyla çalışıyor. Derleme sırasında Docker diskinde ~2 GB boş yer gerekir.
  Platformda ilk yayından sonra `/saglik` ve `/docs` yine kontrol edilmelidir.
