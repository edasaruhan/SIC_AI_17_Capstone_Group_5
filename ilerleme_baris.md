# İlerleme Günlüğü — Barış

Merhaba Tuğçe 👋
Bu dosya, senin GitHub'a koyduğun çalışan çekirdeğin **üzerine** eklediğim
geliştirmeleri anlatır. Amacım hiçbir şeyi bozmadan, dökümanlarımızda (Concept
Note, Veri Araştırması, Data Prep & Model Exploration, Strateji Raporu) yazıp da
kodda henüz olmayan parçaları tamamlamaktı. Aşağıda her bir eklemeyi **ne / neden /
nasıl çalıştırılır** başlıklarıyla yazdım.

> Kısa özet: Dökümanlarda söz verdiğimiz ama kodda eksik olan **4 boşluğu** kapattım:
> (1) Google Trends entegrasyonu, (2) içerik kalite ML modeli, (3) KVKK rıza akışı,
> (4) README/repo düzeni. Mevcut dosyalarına neredeyse hiç dokunmadım; çoğunlukla
> yeni dosyalar ekledim.

---

## 1) Google Trends (SEO) entegrasyonu ✅

**Ne:** Anahtar kelimeler artık `prompts.py` içinde elle yazılan sabit listeyle
sınırlı değil. Yeni `src/trends.py` modülü, kategoriye göre **Google Trends'ten
canlı** anahtar kelime çekiyor (Türkiye, "ilgili sorgular").

**Neden:** Concept Note'ta ve tech-stack'te pytrends vardı (`requirements.txt`'te de
duruyordu) ama kullanan kod yoktu; `prompts.py`'de "A4 aşamasında pytrends ile
değişecek" notun vardı. Ürünün SEO vaadinin kalbi buydu — onu bağladım.

**Nasıl çalışır / güvenlik ağı:**
- Google Trends kotası düşüktür ve sık 429 (çok istek) döndürür. Bu yüzden modül
  **asla çökmez**: ağ yoksa, kota dolduysa veya boş sonuç gelirse otomatik olarak
  senin sabit `KATEGORI_KELIMELERI` listene düşer.
- Sonuçlar `data/trends_onbellek.json` içinde **7 gün önbelleklenir** (kotayı
  korumak için).
- Kelimenin nereden geldiği (`trends` / `önbellek` / `varsayılan`) şeffaf biçimde
  arayüzde gösterilir.
- `uret.icerik_uret(...)`'e `trends_kullan` parametresi ekledim. Arayüzde açık
  (canlı değer), **toplu testte kapalı** — böylece test metriklerimiz her seferinde
  aynı kelime setiyle ölçülür, tekrarlanabilir kalır.

**Dene:**
```bash
python src/trends.py          # her kategori için kelimeleri ve kaynağını yazar
```

---

## 2) İçerik kalite modeli (ML sınıflandırıcı) ✅

**Ne:** "Data Prep & Model Exploration" dökümanındaki sınıflandırıcıyı gerçek,
çalışan kodla kurdum. Model, üretilen taslağın **"onaya hazır (yüksek)"** mı yoksa
**"revizyon gerek (düşük)"** mi olduğunu kestiriyor — yani üreticiye gitmeden önce
çalışan bir **HITL ön-filtresi**.

**Neden:** Dökümanda koca bir bölüm vardı ama ne kod ne veri seti mevcuttu.

**Dosyalar:**
- `src/kalite.py` — öznitelik çıkarımı **ve** çıkarım (tahmin). Eğitim ve arayüz
  aynı öznitelikleri buradan kullanır (train/serve tutarlılığı). Öznitelikler
  dökümandakiyle aynı: kelime_sayısı, seo_kapsamı, abartı_işareti, klişe_işareti,
  duygu_yoğunluğu, hikaye_ipucu + TF-IDF(500).
- `src/kalite_veri_uret.py` — **prototip etiketli veri setini** üretir
  (`data/kalite_etiketli.csv`). Dökümanımız da zaten "temsili/prototip veri" diyordu;
  ben bunu şeffaf ve yeniden üretilebilir hale getirdim. "Yüksek" örnekler somut,
  öykülü, klişesiz; "düşük" örnekler klişe/abartı yüklü, aşırı pazarlamacı veya çok
  kısa. Gerçekçi olsun diye **sınırda örnekler** de kattım (model %100 değil,
  gerçekçi hata yapsın diye).
- `src/kalite_egit.py` — dökümandaki hattı birebir kurar: TF-IDF + StandardScaler,
  **RandomForest + GridSearchCV + StratifiedKFold(5)**, skor F1. Değerlendirmede
  accuracy/precision/recall/F1/ROC-AUC hesaplar; **confusion matrix, ROC eğrisi ve
  öznitelik önemi** grafiklerini `ciktilar/model/` altına PNG olarak kaydeder.

**Şu anki sonuçlar (prototip veri, 468 örnek — 288 yüksek / 180 düşük):**
doğruluk ~%98, F1 ~0.98, ROC-AUC yüksek, düşük-sınıf recall 1.0.
*Bunlar prototip veri üzerindedir; saha pilotunda gerçek insan etiketleriyle
güncellenecek (tıpkı dökümanda dediğimiz gibi).*

**Dene:**
```bash
python src/kalite_veri_uret.py    # veri setini üretir
python src/kalite_egit.py         # modeli eğitir + metrik/grafik kaydeder
python src/kalite.py              # iki örnekle hızlı tahmin denemesi
```
Model dosyası yoksa arayüz bu özelliği **sessizce gizler** — yani eğitmeyi
unutursan uygulama yine sorunsuz çalışır.

---

## 3) KVKK aydınlatma & açık rıza akışı ✅

**Ne:** Yeni `src/kvkk.py` modülü + arayüzde işlevsel bir **rıza kapısı**. Sesli
anlatım kullanmak için kullanıcının önce **açık rıza kutusunu** işaretlemesi
gerekiyor; işaretlemeden "Sesimi metne çevir" düğmesi pasif.

**Neden:** Veri Araştırması dökümanı bunu açık bir eksik olarak işaretlemişti: ses
verisi KVKK m.6'da özel nitelikli (biyometrik) sayılabilir → açık rıza; veri Gemini'ye
(yurt dışı) gittiği için KVKK m.9 → aydınlatma. Önceden UI'da sadece metin vardı.

**Nerede görünür:**
- Sesli anlatım sekmesinde: aydınlatma açılır kutusu + zorunlu rıza onayı.
- Metin girişinde: kısa bilgilendirme ("hassas bilgi yazmayın").
- "Etik & KVKK" sekmesinde: 6 maddelik ayrıntılı politika (hangi veri, ne amaçla,
  nereye, ne kadar saklanıyor, haklarınız, veri minimizasyonu).

---

## 4) README + repo düzeni ✅

**Ne:** Kök dizine düzgün bir **`README.md`** ekledim (M6 kilometre taşı istiyordu):
ne yaptığı, mimari diyagramı (mermaid), kurulum, ML modeli, KPI, etik/KVKK, yol
haritası ve proje yapısı. Senin `KURULUM.md`'ne dokunmadım; README oradan link
veriyor.

`requirements.txt`'e kalite modeli için gerekenleri ekledim: scikit-learn, scipy,
joblib, matplotlib.

---

## Senin dosyalarına ne oldu? (dokunduğum yerler)

Neredeyse her şey **yeni dosya**. Mevcut kodda sadece küçük, güvenli değişiklikler:

| Dosya | Değişiklik |
|---|---|
| `src/uret.py` | `icerik_uret`'e `trends_kullan` parametresi; anahtar kelime yoksa artık Trends'ten çekiyor (hata olursa sabit listeye düşüyor). |
| `src/toplu_test.py` | Testte `trends_kullan=False` (metrikler tekrarlanabilir kalsın diye). |
| `src/app.py` | Yeni importlar; KVKK rıza kapısı; kalite rozeti; Trends düğmesi; Panel'de model metrikleri; Etik sekmesine KVKK politikası. |
| `requirements.txt` | ML paketleri eklendi. |

**Bozulan bir şey yok:** senin çekirdek üretim akışın, prompt'ların, ton profili,
toplu test ve arayüzün aynen çalışıyor. Yeni özellikler modüler; biri (ör. model)
yoksa uygulama yine açılıyor.

---

## Kurulum notu (senin için)

Yeni ML paketleri için:
```bash
pip install -r requirements.txt
```
Sonra istersen bir kez modeli eğit:
```bash
python src/kalite_veri_uret.py && python src/kalite_egit.py
```
ve arayüzü aç:
```bash
streamlit run src/app.py
```

Soru olursa yaz — kolay gelsin! 🌸
