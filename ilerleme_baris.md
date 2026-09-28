# İlerleme Günlüğü — Barış

*Son güncelleme: 08.09.2026*

Merhaba Tuğçe 👋

Bu dosya, senin GitHub'a koyduğun çalışan çekirdeğin **üzerine** eklediğim
geliştirmeleri anlatır. Amacım hiçbir şeyi bozmadan, dökümanlarımızda (Concept
Note, Veri Araştırması, Data Prep & Model Exploration, Strateji Raporu) yazıp da
kodda henüz olmayan parçaları tamamlamak ve arayüzü gerçek kullanıcımıza —
teknolojiden anlamayan bir üretici kadına — göre kurmaktı.

> **Kısa özet (3 blok):**
> 1. Dökümanlarda söz verdiğimiz ama kodda eksik olan **4 boşluğu kapattım**:
>    Google Trends entegrasyonu, içerik kalite ML modeli, KVKK rıza akışı, README.
> 2. **Arayüzü son kullanıcı odaklı yeniden kurguladım** — 8 sekmeli panodan
>    adım adım akışa geçtik; teknik/rapor bileşenleri "Geliştirici modu" arkasına alındı.
> 3. Uygulamayı **yayına almaya hazırladım** (tek eksik: depo erişimi — bkz. son bölüm).
>
> Toplam 10 commit ekledim. Senin mevcut dosyalarına neredeyse hiç dokunmadım;
> çoğunlukla yeni dosyalar ekledim.

---

# BÖLÜM 1 — Dökümandaki 4 boşluk kapatıldı

## 1) Google Trends (SEO) entegrasyonu ✅

**Ne:** Anahtar kelimeler artık `prompts.py` içindeki sabit listeyle sınırlı değil.
Yeni `src/trends.py`, kategoriye göre **Google Trends'ten canlı** kelime çekiyor
(Türkiye, "ilgili sorgular").

**Neden:** `requirements.txt`'te pytrends duruyordu ama kullanan kod yoktu;
`prompts.py`'de "A4 aşamasında pytrends ile değişecek" notun vardı. Ürünün SEO
vaadinin kalbi buydu.

**Güvenlik ağı:** Trends kotası düşüktür ve sık 429 döndürür. Modül **asla çökmez** —
ağ/kota sorununda otomatik olarak senin `KATEGORI_KELIMELERI` listene düşer.
Sonuçlar `data/trends_onbellek.json`'da 7 gün önbelleklenir. Kelimenin nereden
geldiği (canlı / önbellek / varsayılan) arayüzde şeffafça gösterilir.

**Not:** `uret.icerik_uret`'e `trends_kullan` parametresi ekledim. Arayüzde açık,
**toplu testte kapalı** — böylece test metriklerimiz her seferinde aynı kelime
setiyle ölçülür, tekrarlanabilir kalır.

```bash
python src/trends.py     # her kategori için kelimeleri ve kaynağını yazar
```

## 2) İçerik kalite modeli (ML sınıflandırıcı) ✅

**Ne:** "Data Prep & Model Exploration" dökümanındaki sınıflandırıcıyı gerçek,
çalışan kodla kurdum. Model, üretilen taslağın **"onaya hazır"** mı **"revizyon
gerek"** mi olduğunu kestiriyor — yani üreticiye gitmeden çalışan bir **HITL ön
filtresi**.

**Neden:** Dökümanda koca bir bölüm vardı ama ne kod ne veri seti mevcuttu.

**Dosyalar:**
- `src/kalite.py` — öznitelik çıkarımı **ve** tahmin. Eğitim ile arayüz aynı
  öznitelikleri buradan kullanır (train/serve tutarlılığı). Öznitelikler
  dökümandakiyle aynı: kelime_sayısı, seo_kapsamı, abartı_işareti, klişe_işareti,
  duygu_yoğunluğu, hikaye_ipucu + TF-IDF(500).
- `src/kalite_veri_uret.py` — **prototip etiketli veri setini** üretir
  (`data/kalite_etiketli.csv`, 468 örnek). Dökümanımız zaten "temsili/prototip veri"
  diyordu; ben bunu şeffaf ve yeniden üretilebilir hale getirdim. Gerçekçi olsun diye
  **sınırda örnekler** de kattım (model %100 değil, gerçekçi hata yapsın diye).
- `src/kalite_egit.py` — dökümandaki hattı birebir kurar: TF-IDF + StandardScaler,
  **RandomForest + GridSearchCV + StratifiedKFold(5)**, skor F1. Confusion matrix,
  ROC eğrisi ve öznitelik önemi grafiklerini `ciktilar/model/` altına kaydeder.

**Sonuç (prototip veri, 288 yüksek / 180 düşük):** doğruluk ~%98, F1 ~0.98,
düşük-sınıf recall 1.0.
⚠️ *Bunlar prototip veri üzerindedir; saha pilotunda gerçek insan etiketleriyle
güncellenecek — raporlarda bu ayrımı hep belirtiyorum.*

```bash
python src/kalite_veri_uret.py    # veri setini üretir
python src/kalite_egit.py         # eğitir + metrik/grafik kaydeder
```

Model dosyası yoksa arayüz bu özelliği **sessizce gizler** — yani eğitmeyi
unutursan uygulama yine sorunsuz çalışır.

## 3) KVKK aydınlatma & açık rıza akışı ✅

**Ne:** `src/kvkk.py` + arayüzde **işlevsel bir rıza kapısı**. Sesli anlatım için
kullanıcının açık rıza kutusunu işaretlemesi gerekiyor; işaretlemeden "sesimi yazıya
dök" düğmesi pasif.

**Neden:** Veri Araştırması dökümanı bunu açık eksik olarak işaretlemişti: ses verisi
KVKK m.6'da özel nitelikli (biyometrik) sayılabilir → açık rıza; veri Gemini'ye
(yurt dışı) gittiği için m.9 → aydınlatma. Önceden UI'da yalnızca metin vardı.

## 4) README + repo düzeni ✅

Kök `README.md` (ne yaptığı, mimari diyagramı, kurulum, KPI, yol haritası),
`requirements.txt`'e ML paketleri, `.gitignore`'a model ikilisi/önbellek/secret koruması.

---

# BÖLÜM 2 — Arayüz yeniden kurgulandı

Arayüzü üç turda ele aldık; **üçüncüsü en önemlisi.**

**1. tur — Erişilebilirlik.** WCAG AA kontrastı: üç rengi sayısal ölçüp düzelttim
(etiket rengi 4.06 → 6.5, altbilgi 2.92 → 5.8, yeşil buton 3.04 → 5.7). Görünür
klavye odak halkası, 44px dokunma hedefleri, `prefers-reduced-motion`, responsive.

**2. tur — Profesyonel tasarım sistemi.** Lexend + Source Sans 3 tipografi, semantik
renk tokenleri, tutarlı gölge/kart sistemi, ince giriş animasyonları.

**3. tur — Son kullanıcı odağı (asıl dönüşüm).**
Önceki hâli bir "mühendis panosu"ydu: 8 sekme, gelişmiş ayarlar, confusion matrix,
"chain-of-thought" — hepsi kullanıcının yüzüne yığılmıştı. Şimdi:

- **Adım adım akış:** Karşılama (ne yapıyoruz) → Anlat → Sonuç. Her ekranda tek iş,
  tek birincil buton.
- **Karşılama ekranı:** sade dille ne yaptığımız + 3 adım + güven notu
  ("hikâyenizi uydurmaz, son karar sizde").
- **Kullanıcıdan kaldırılanlar:** anlatım tonu, prompt tekniği, gelişmiş ayarlar,
  SEO/klişe/benzerlik metrikleri. Arka planda sıcak ton + few-shot otomatik kullanılıyor.
- **Kaybolmadı, saklandı:** Prompt karşılaştırma, toplu üretim, test paneli ve model
  metrikleri artık kenar çubuğundaki **"🔧 Geliştirici / rapor modu"** anahtarının
  arkasında. Capstone kanıtımız duruyor, üretici hiç görmüyor.
- **Dil değişti:** "%81 güven" yerine *"✅ İçeriğiniz yayına hazır görünüyor"*;
  "gerekçeler" yerine *"💡 Küçük bir öneri: şunlara bakmak isteyebilirsiniz…"*

**Geri navigasyonu düzeltildi.** Hiçbir ekranda geri dönüş yolu yoktu ve tarayıcının
geri tuşu çalışmıyordu. Geri yığını + her ekranda "← Geri" düğmesi + URL senkronu
(`?ekran=...`) ekledim. Streamlit tarayıcı geri tuşunda kendiliğinden yeniden
çalışmadığı için, geri tuşunu uygulamanın kendi geri düğmesine bağlayan bir köprü
kurdum — sayfa yenilenmediği için **üretilen içerikler kaybolmuyor.**

---

# BÖLÜM 3 — Yayına alma hazırlığı

Uygulama Streamlit Community Cloud'a alınmaya hazır (ayrıntı: **`DEPLOY.md`**):

- `.streamlit/config.toml` — paletle uyumlu tema.
- API anahtarı hem `.env` (yerel) hem **`st.secrets`** (bulut) üzerinden okunuyor.
- Kalite modeli bulutta **kendi kendine eğiliyor** — model ikilisi gitignore'da
  olduğu için repoda yok; uygulama `data/kalite_etiketli.csv`'den çalışır bir model kurar.
- Mobil uyumlu (375px'te test edildi): sekmeler yatay kayıyor, düğmeler yığılmıyor.

🔴 **Tek engel:** Depo **private** olduğu için Streamlit göremiyor
("This repository does not exist"). Çözüm için bkz. son bölüm.

---

# Senin dosyalarına ne oldu?

Neredeyse her şey **yeni dosya**. Mevcut kodda yalnızca küçük, güvenli değişiklikler:

| Dosya | Değişiklik |
|---|---|
| `src/uret.py` | `icerik_uret`'e `trends_kullan` parametresi; anahtar kelime yoksa Trends'ten çekiyor (hata olursa sabit listeye düşüyor). |
| `src/toplu_test.py` | Testte `trends_kullan=False` (metrikler tekrarlanabilir kalsın diye). |
| `src/app.py` | Baştan yazıldı (adım adım akış + geliştirici modu). Tüm işlevler korundu. |
| `requirements.txt` | scikit-learn, scipy, joblib, matplotlib eklendi. |

**Bozulan bir şey yok:** çekirdek üretim akışın, prompt'ların, ton profili, sesli
anlatım, Reels/fotoğraf ve toplu test aynen çalışıyor.

---

# Şu anki durum ve dürüst notlar

- Uygulama uçtan uca **yerelde çalışıyor**; kod GitHub'da güncel (`main`).
- ⚠️ Yeni arayüzü **gerçek API ile uçtan uca henüz denemedik** (anlat → içerik üret).
  API kotasını harcamamak için ertelendi — yapılacak ilk iş bu olmalı.
- ⚠️ Kalite modelinin metrikleri **prototip veri** üzerinde; gerçek etiket yok.

---

# Sıradaki işler (haftalık rapora da yazdık)

1. **Sesli anlatım doğruluğunu ölçmek** — ses→metin adımı üreticinin kendi
   kelimelerini ne kadar koruyor?
2. **Çıktıları 1–5 kalite rubriğiyle sistematik gözden geçirmek** — halüsinasyon/
   abartı/SEO ölçümü ve kalite modelini gerçek çıktılarla sınamak.
3. **Görsel içerik üretimi prototipi** + çıktının ürüne sadakati (uydurma özellik
   eklememesi).

---

# Senden rica ettiklerim 🙏

1. **Depoyu public yapman** (veya bana admin vermen) — yayına alma buna takılı.
   Repoda anahtar/secret yok, kontrol ettim; public yapmak güvenli.
   *GitHub → repo → Settings → General → Danger Zone → Change visibility.*
2. **Haftalık ilerleme raporuna kendi maddelerini eklemen** — 1. soruya senin bu
   haftaki işlerin de girmeli (madde sınırı 3).
3. **Takım adı** — raporda boş bıraktım, bilmiyorum.
4. **Görev dağılımını yeniden senkronlayalım** — Concept Note matrisinde Google
   Trends/SEO senin sorumluluğunda görünüyordu, onu ben yaptım. **Değerlendirme
   rubriği ve kör A/B** hâlâ sende; sıradaki işlerin 2. maddesi tam olarak onun
   önkoşulunu hazırlıyor, birlikte ilerleyebiliriz.

---

# Kurulum (senin için)

```bash
pip install -r requirements.txt
python src/kalite_veri_uret.py && python src/kalite_egit.py   # modeli bir kez eğit
streamlit run src/app.py
```

`.env` dosyasına kendi `GEMINI_API_KEY`'ini yaz (anahtarlar paylaşılmaz, `.env`
GitHub'a gitmez). Ayrıntı: `KURULUM.md`.

Soru olursa yaz — kolay gelsin! 🌸
