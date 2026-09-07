# Yayına Alma (Deploy) — Üretken Kadın

Bu rehber, uygulamayı **ücretsiz Streamlit Community Cloud**'a alıp herkesin
(telefon dâhil) açabileceği kalıcı bir `https://...` adresi elde etmek içindir.

> Neden Streamlit Cloud? Ücretsiz, GitHub'a bağlı, API anahtarını "secret" olarak
> güvenle saklar ve her `git push` sonrası otomatik günceller. Bu proje için birebir.

---

## Ön koşullar (kodda hazır ✅)

- `requirements.txt` — tüm bağımlılıklar (Streamlit Cloud bunu kurar).
- `.streamlit/config.toml` — tema ve sunucu ayarları.
- Kalite modeli **kendi kendine eğitilir** — repoda model ikilisi olmasa da
  (gitignore'da) uygulama `data/kalite_etiketli.csv`'den çalışır bir model kurar.
- API anahtarı hem `.env` (yerel) hem `st.secrets` (bulut) üzerinden okunur.

## Adımlar

1. **Kodun GitHub'da güncel olduğundan emin ol** (bu repo: `Tugce-hub/Uretken_Kadin`, `main`):
   ```bash
   git push origin main
   ```

2. **share.streamlit.io** adresine git → **GitHub ile giriş yap** (Continue with GitHub).
   İlk girişte Streamlit'in repoya erişimine izin vermen istenir.

3. **Create app → Deploy a public app from GitHub** ve şunları seç:
   - **Repository:** `Tugce-hub/Uretken_Kadin`
   - **Branch:** `main`
   - **Main file path:** `src/app.py`
   - (İsteğe bağlı) özel bir alt-alan adı (URL) belirle.

4. **Advanced settings → Secrets** kutusuna API anahtarını gir (TOML biçiminde):
   ```toml
   GEMINI_API_KEY = "buraya_kendi_anahtarin"
   # Gerekirse model adını da sabitleyebilirsin:
   # GEMINI_MODEL = "gemini-3.6-flash"
   ```
   > Bu anahtar yalnızca sunucuda saklanır; koda veya GitHub'a yazılmaz.

5. **Deploy**'a bas. Birkaç dakikada bağımlılıklar kurulur ve uygulama açılır.
   Sana `https://<isim>.streamlit.app` gibi bir adres verilir — **bu adresi
   telefonda da açabilirsin**.

## Güncelleme

Kodda değişiklik yapıp `git push origin main` dediğinde uygulama **otomatik**
yeniden dağıtılır. Ayrı bir işlem gerekmez.

## Sık karşılaşılanlar

| Durum | Çözüm |
|---|---|
| "GEMINI_API_KEY bulunamadı" | Adım 4'teki Secrets'ı eklemeyi/doğru yazmayı kontrol et. |
| Kalite rozeti görünmüyor | Sorun değil — model CSV'den kurulamadıysa özellik sessizce gizlenir; çekirdek üretim çalışır. |
| Kurulum çok uzun sürüyor | İlk deploy'da bağımlılıklar (scikit-learn vb.) derlenir; sonraki açılışlar hızlıdır. |
| Uygulamayı durdurmak istiyorum | Streamlit Cloud panelinden uygulamayı "delete/reboot" edebilirsin. |

## Alternatifler (ileride)

- **Hugging Face Spaces** (Streamlit desteği) — benzer, ücretsiz.
- **Render / Railway** — daha fazla kontrol, konteyner tabanlı.
- Kurumsal/özel kullanım için kendi sunucunda `streamlit run` + reverse proxy.
