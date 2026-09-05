# -*- coding: utf-8 -*-
"""
Üretken Kadın — Streamlit arayüzü (HITL: insan onaylı akış)

Çalıştırmak için:
    streamlit run src/app.py
"""

import streamlit as st

import prompts
import uret

# ---------------------------------------------------------------------------
st.set_page_config(page_title="Üretken Kadın", page_icon="🧵", layout="wide")

RENK_ANA = "#9C4368"
RENK_KOYU = "#4A2138"

st.markdown(f"""
<style>
  .stApp {{ background-color: #FDFBFA; }}
  h1 {{ color: {RENK_KOYU}; margin-bottom: 0rem; }}
  .altbaslik {{ color: #6E6459; font-style: italic; margin-top: -0.6rem;
                margin-bottom: 1.2rem; }}
  .kart {{ background: #FBF6F2; border: 1px solid #E3D5DA; border-radius: 10px;
           padding: 0.9rem 1.1rem; margin-bottom: 0.8rem; }}
  .kart-baslik {{ color: {RENK_ANA}; font-weight: 700; font-size: 0.95rem;
                  margin-bottom: 0.4rem; }}
  .ifsa {{ color: #8A7A80; font-size: 0.8rem; font-style: italic;
           text-align: center; margin-top: 1.5rem; }}
  div.stButton > button {{ background-color: {RENK_ANA}; color: white;
                           border: none; border-radius: 8px; font-weight: 600;
                           padding: 0.5rem 1rem; }}
</style>
""", unsafe_allow_html=True)

st.title("Üretken Kadın")
st.markdown('<p class="altbaslik">Ürününüzü kendi cümlelerinizle anlatın — '
            'gerisini bize bırakın.</p>', unsafe_allow_html=True)

# Oturum durumu
if "sonuc" not in st.session_state:
    st.session_state.sonuc = None

sol, sag = st.columns([1, 1], gap="large")

# ---------------------------------------------------------------------------
# SOL — girdi
# ---------------------------------------------------------------------------
with sol:
    st.markdown(f"**1 · ÜRÜNÜNÜZÜ ANLATIN**")

    anlatim = st.text_area(
        "Ne ürettiğinizi, nasıl yaptığınızı ve ne kadar sürdüğünü anlatın:",
        height=180,
        placeholder="Örnek: El örgüsü bebek battaniyesi yapıyorum. Organik pamuk "
                    "ipliği kullanıyorum, tamamen elde örüyorum. Bir tanesi yaklaşık "
                    "üç günümü alıyor…",
        label_visibility="collapsed",
    )

    k1, k2 = st.columns(2)
    with k1:
        kategori = st.selectbox("Kategori", list(prompts.KATEGORI_KELIMELERI.keys()))
    with k2:
        ton = st.selectbox("Ton", ["sıcak ve samimi", "sade ve bilgilendirici",
                                   "şık ve zarif"])

    with st.expander("Gelişmiş (rapor için)"):
        teknik = st.radio(
            "Prompt tekniği",
            ["few_shot", "zero_shot", "chain_of_thought"],
            help="Rapordaki karşılaştırma için: zero_shot = baseline (temel karşılaştırma).",
            horizontal=False,
        )

    uret_butonu = st.button("✦  İçerik Üret", use_container_width=True)

    if uret_butonu:
        if not anlatim.strip():
            st.warning("Önce ürününüzü birkaç cümleyle anlatın.")
        else:
            with st.spinner("İçerik hazırlanıyor…"):
                try:
                    st.session_state.sonuc = uret.icerik_uret(
                        anlatim=anlatim, kategori=kategori, ton=ton, teknik=teknik
                    )
                except Exception as hata:
                    st.session_state.sonuc = None
                    st.error(f"İçerik üretilemedi: {hata}")

# ---------------------------------------------------------------------------
# SAĞ — çıktı (düzenlenebilir)
# ---------------------------------------------------------------------------
with sag:
    st.markdown("**2 · DÜZENLEYİN VE ONAYLAYIN**")
    sonuc = st.session_state.sonuc

    if sonuc is None:
        st.info("Soldaki kutuya ürününüzü anlatıp **İçerik Üret** düğmesine basın.")
    else:
        st.markdown('<div class="kart-baslik">Instagram gönderisi</div>',
                    unsafe_allow_html=True)
        ig = st.text_area("Instagram", value=sonuc.instagram, height=150,
                          label_visibility="collapsed")

        st.markdown('<div class="kart-baslik">Shopier ürün açıklaması</div>',
                    unsafe_allow_html=True)
        sh = st.text_area("Shopier", value=sonuc.shopier, height=170,
                          label_visibility="collapsed")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("✓  Onayla", use_container_width=True):
                st.success("Onaylandı. Metinleri kopyalayıp kendi hesabınızda "
                           "paylaşabilirsiniz.")
        with b2:
            st.download_button("⬇  Metinleri indir",
                               data=f"INSTAGRAM\n{ig}\n\nSHOPIER\n{sh}",
                               file_name="uretken_kadin_icerik.txt",
                               use_container_width=True)

        # KPI: SEO kapsamı
        kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
        if kelimeler:
            kapsam = uret.seo_kapsami(ig + " " + sh, kelimeler)
            st.caption(f"SEO kapsamı: {kapsam}/{len(kelimeler)} anahtar kelime "
                       f"kullanıldı — {', '.join(kelimeler)}")

st.markdown('<p class="ifsa">Bu içerik yapay zekâ ile üretilmiştir · '
            'son karar her zaman üreticidedir</p>', unsafe_allow_html=True)
