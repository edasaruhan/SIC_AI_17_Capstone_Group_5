# -*- coding: utf-8 -*-
"""
Üretken Kadın — Streamlit arayüzü (HITL: insan onaylı akış)

Çalıştırmak için:
    streamlit run src/app.py
"""

from datetime import datetime

import streamlit as st

import prompts
import uret

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Üretken Kadın — Emeğin dijital sesi",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Marka renkleri ---------------------------------------------------------
KOYU = "#4A2138"      # derin bordo
ANA = "#9C4368"       # ana vurgu
ALTIN = "#C08A2D"
YESIL = "#7E9B85"
ACIK = "#F3ECE4"
ZEMIN = "#FDFBFA"

st.markdown(f"""
<style>
  /* --- Streamlit'in kendi ustbilgisini gizle --- */
  [data-testid="stHeader"] {{ background: transparent; height: 0; }}
  #MainMenu, footer {{ visibility: hidden; }}
  .stApp {{ background: {ZEMIN}; }}
  .block-container {{ padding-top: 1rem; max-width: 1180px; }}

  /* --- NAVBAR --- */
  .navbar {{
      display: flex; align-items: center; justify-content: space-between;
      background: {KOYU}; padding: 0.85rem 1.6rem; border-radius: 14px;
      margin-bottom: 1.4rem; box-shadow: 0 4px 18px rgba(74,33,56,0.18);
  }}
  .nav-brand {{ display: flex; align-items: center; gap: 0.6rem; }}
  .nav-logo {{
      width: 34px; height: 34px; border-radius: 9px; background: {ANA};
      display: flex; align-items: center; justify-content: center;
      font-size: 1.1rem;
  }}
  .nav-title {{ color: #fff; font-weight: 700; font-size: 1.12rem;
                letter-spacing: 0.2px; }}
  .nav-sub {{ color: #D9C4CC; font-size: 0.72rem; margin-top: -2px; }}
  .nav-links {{ display: flex; align-items: center; gap: 1.5rem; }}
  .nav-links a {{ color: #E8DBE0; text-decoration: none; font-size: 0.86rem;
                  font-weight: 500; }}
  .nav-links a:hover {{ color: {ALTIN}; }}
  .nav-rozet {{
      background: rgba(255,255,255,0.12); color: #fff; padding: 0.3rem 0.75rem;
      border-radius: 20px; font-size: 0.74rem; font-weight: 600;
  }}

  /* --- HERO --- */
  .hero {{
      background: linear-gradient(135deg, {ACIK} 0%, #FBF1EC 55%, #F6E6E9 100%);
      border-radius: 16px; padding: 1.9rem 2.2rem; margin-bottom: 1.5rem;
      border: 1px solid #EBDDE2;
  }}
  .hero h1 {{ color: {KOYU}; font-size: 2.05rem; margin: 0 0 0.35rem 0;
              line-height: 1.15; }}
  .hero p {{ color: #6E6459; font-size: 1.0rem; margin: 0 0 1.0rem 0; }}
  .cipler {{ display: flex; gap: 0.6rem; flex-wrap: wrap; }}
  .cip {{
      background: #fff; border: 1px solid #E5D5DB; color: {KOYU};
      padding: 0.35rem 0.85rem; border-radius: 20px; font-size: 0.8rem;
      font-weight: 500;
  }}

  /* --- ADIM BASLIKLARI --- */
  .adim {{ display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.7rem; }}
  .adim-no {{
      width: 25px; height: 25px; border-radius: 50%; background: {ANA};
      color: #fff; display: flex; align-items: center; justify-content: center;
      font-size: 0.8rem; font-weight: 700;
  }}
  .adim-no.yesil {{ background: {YESIL}; }}
  .adim-yazi {{ color: {KOYU}; font-weight: 700; font-size: 0.95rem;
                letter-spacing: 0.4px; }}

  /* --- KARTLAR --- */
  .kart {{
      background: #fff; border: 1px solid #EADCE1; border-radius: 12px;
      padding: 1.1rem 1.3rem; margin-bottom: 0.9rem;
      box-shadow: 0 2px 10px rgba(74,33,56,0.05);
  }}
  .kart-baslik {{ color: {ANA}; font-weight: 700; font-size: 0.9rem;
                  margin-bottom: 0.5rem; }}
  .kart p {{ color: #514840; font-size: 0.9rem; line-height: 1.55; margin: 0; }}

  /* --- METRIK KUTULARI --- */
  .metrik {{
      background: #fff; border: 1px solid #EADCE1; border-radius: 11px;
      padding: 0.85rem 1rem; text-align: center;
  }}
  .metrik-deger {{ color: {ANA}; font-size: 1.5rem; font-weight: 700;
                   line-height: 1.1; }}
  .metrik-etiket {{ color: #8A7A80; font-size: 0.74rem; margin-top: 0.2rem; }}

  /* --- BUTONLAR --- */
  div.stButton > button {{
      background: {ANA}; color: #fff; border: none; border-radius: 9px;
      font-weight: 600; padding: 0.6rem 1rem; transition: all 0.15s;
  }}
  div.stButton > button:hover {{ background: {KOYU}; color: #fff; }}
  div.stDownloadButton > button {{
      background: #fff; color: {YESIL}; border: 1.5px solid {YESIL};
      border-radius: 9px; font-weight: 600;
  }}

  /* --- SEKMELER --- */
  .stTabs [data-baseweb="tab-list"] {{ gap: 0.35rem; }}
  .stTabs [data-baseweb="tab"] {{
      border-radius: 9px 9px 0 0; padding: 0.55rem 1.1rem;
      font-weight: 600; font-size: 0.9rem;
  }}
  .stTabs [aria-selected="true"] {{ background: {ACIK}; color: {KOYU} !important; }}

  /* --- ETIK SERIDI --- */
  .ifsa {{
      background: #FBF6F2; border: 1px dashed #DCC9CF; border-radius: 10px;
      color: #7A6C72; font-size: 0.8rem; text-align: center;
      padding: 0.6rem; margin-top: 1.6rem;
  }}
  .altbilgi {{ color: #A0949A; font-size: 0.76rem; text-align: center;
               margin-top: 0.8rem; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# NAVBAR
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="navbar">
  <div class="nav-brand">
    <div class="nav-logo">🧵</div>
    <div>
      <div class="nav-title">Üretken Kadın</div>
      <div class="nav-sub">Emeğin dijital sesi</div>
    </div>
  </div>
  <div class="nav-links">
    <a href="https://github.com/Tugce-hub/Uretken_Kadin" target="_blank">GitHub</a>
    <span class="nav-rozet">Samsung Innovation Campus</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Oturum durumu
# ---------------------------------------------------------------------------
if "sonuc" not in st.session_state:
    st.session_state.sonuc = None
if "gecmis" not in st.session_state:
    st.session_state.gecmis = []


# ---------------------------------------------------------------------------
# SEKMELER
# ---------------------------------------------------------------------------
sekme_uret, sekme_gecmis, sekme_nasil, sekme_etik = st.tabs(
    ["✍️  İçerik Üret", "📁  Geçmişim", "💡  Nasıl Çalışır", "🛡️  Etik ve Gizlilik"]
)


# ===========================================================================
# SEKME 1 — İÇERİK ÜRET
# ===========================================================================
with sekme_uret:
    st.markdown("""
    <div class="hero">
      <h1>Ürününüzü anlatın,<br>gerisini biz yazalım.</h1>
      <p>Kendi cümlelerinizle anlatmanız yeterli — sosyal medya ve satış sayfası
         metinlerinizi saniyeler içinde hazırlıyoruz.</p>
      <div class="cipler">
        <div class="cip">✓ Sizin üslubunuz korunur</div>
        <div class="cip">✓ Abartı ve uydurma yok</div>
        <div class="cip">✓ Son karar her zaman sizde</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    sol, sag = st.columns([1, 1], gap="large")

    # ------------------------------------------------------------------ SOL
    with sol:
        st.markdown('<div class="adim"><div class="adim-no">1</div>'
                    '<div class="adim-yazi">ÜRÜNÜNÜZÜ ANLATIN</div></div>',
                    unsafe_allow_html=True)

        anlatim = st.text_area(
            "Anlatım",
            height=175,
            placeholder="Ne ürettiğinizi, nasıl yaptığınızı ve ne kadar sürdüğünü "
                        "anlatın.\n\nÖrnek: El örgüsü bebek battaniyesi yapıyorum. "
                        "Organik pamuk ipliği kullanıyorum, tamamen elde örüyorum. "
                        "Bir tanesi yaklaşık üç günümü alıyor…",
            label_visibility="collapsed",
        )

        k1, k2 = st.columns(2)
        with k1:
            kategori = st.selectbox("Kategori",
                                    list(prompts.KATEGORI_KELIMELERI.keys()))
        with k2:
            ton = st.selectbox("Anlatım tonu",
                               ["sıcak ve samimi", "sade ve bilgilendirici",
                                "şık ve zarif"])

        with st.expander("⚙️  Gelişmiş ayarlar (rapor / karşılaştırma için)"):
            teknik = st.radio(
                "Prompt tekniği",
                ["few_shot", "zero_shot", "chain_of_thought"],
                captions=["Örneklerle — varsayılan, en iyi sonuç",
                          "Örneksiz — karşılaştırma tabanı (baseline)",
                          "Adım adım düşündürerek"],
            )
            st.caption(f"Kullanılan model: `{uret.MODEL}`")

        if st.button("✦   İçerik Üret", use_container_width=True, type="primary"):
            if not anlatim.strip():
                st.warning("Önce ürününüzü birkaç cümleyle anlatın.")
            elif len(anlatim.split()) < 5:
                st.warning("Biraz daha ayrıntı verin — en az bir iki cümle yazın.")
            else:
                with st.spinner("İçeriğiniz hazırlanıyor…"):
                    try:
                        sonuc = uret.icerik_uret(anlatim=anlatim, kategori=kategori,
                                                 ton=ton, teknik=teknik)
                        st.session_state.sonuc = sonuc
                        st.session_state.gecmis.insert(0, {
                            "saat": datetime.now().strftime("%H:%M"),
                            "kategori": kategori,
                            "anlatim": anlatim,
                            "instagram": sonuc.instagram,
                            "shopier": sonuc.shopier,
                        })
                    except Exception as hata:
                        st.session_state.sonuc = None
                        st.error(f"İçerik üretilemedi: {hata}")

    # ------------------------------------------------------------------ SAĞ
    with sag:
        st.markdown('<div class="adim"><div class="adim-no yesil">2</div>'
                    '<div class="adim-yazi">DÜZENLEYİN VE ONAYLAYIN</div></div>',
                    unsafe_allow_html=True)

        sonuc = st.session_state.sonuc

        if sonuc is None:
            st.markdown("""
            <div class="kart">
              <div class="kart-baslik">Henüz içerik üretilmedi</div>
              <p>Soldaki kutuya ürününüzü anlatıp <b>İçerik Üret</b> düğmesine basın.
              Size iki ayrı metin hazırlayacağız:</p>
              <br>
              <p>📱 <b>Instagram gönderisi</b> — kısa, dikkat çeken, hikâyenizi anlatan<br>
              🛍️ <b>Shopier açıklaması</b> — aranınca bulunan, bilgi veren</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="kart-baslik">📱 Instagram gönderisi</div>',
                        unsafe_allow_html=True)
            ig = st.text_area("Instagram", value=sonuc.instagram, height=140,
                              label_visibility="collapsed")

            st.markdown('<div class="kart-baslik">🛍️ Shopier ürün açıklaması</div>',
                        unsafe_allow_html=True)
            sh = st.text_area("Shopier", value=sonuc.shopier, height=165,
                              label_visibility="collapsed")

            b1, b2 = st.columns(2)
            with b1:
                if st.button("✓   Onayla", use_container_width=True):
                    st.success("Onaylandı! Aşağıdan kopyalayabilirsiniz.")
            with b2:
                st.download_button("⬇  Metinleri indir",
                                   data=f"INSTAGRAM\n{ig}\n\nSHOPIER\n{sh}",
                                   file_name="uretken_kadin_icerik.txt",
                                   use_container_width=True)

            with st.expander("📋  Kopyalamak için tıklayın"):
                st.caption("Instagram gönderisi")
                st.code(ig, language=None)
                st.caption("Shopier açıklaması")
                st.code(sh, language=None)

            # --- Ölçümler ---
            kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
            kapsam = uret.seo_kapsami(f"{ig} {sh}", kelimeler)
            klise = uret.klise_sayisi(f"{ig} {sh}")
            benzerlik = uret.kanal_benzerligi(ig, sh)

            st.markdown("<br>", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            for kol, deger, etiket in [
                (m1, f"{kapsam}/{len(kelimeler)}", "SEO anahtar kelime"),
                (m2, str(klise), "klişe ifade"),
                (m3, f"{benzerlik:.2f}", "kanal benzerliği"),
            ]:
                kol.markdown(f'<div class="metrik"><div class="metrik-deger">{deger}'
                             f'</div><div class="metrik-etiket">{etiket}</div></div>',
                             unsafe_allow_html=True)

    st.markdown('<div class="ifsa">Bu içerik yapay zekâ ile üretilmiştir · '
                'yayınlamadan önce okuyup düzenleyin — son karar her zaman sizindir</div>',
                unsafe_allow_html=True)


# ===========================================================================
# SEKME 2 — GEÇMİŞİM
# ===========================================================================
with sekme_gecmis:
    st.markdown("### 📁 Bu oturumda ürettikleriniz")

    if not st.session_state.gecmis:
        st.info("Henüz içerik üretmediniz. **İçerik Üret** sekmesinden başlayın.")
    else:
        st.caption(f"Toplam {len(st.session_state.gecmis)} içerik üretildi. "
                   "(Sayfayı yenilerseniz bu liste sıfırlanır.)")
        for i, kayit in enumerate(st.session_state.gecmis):
            baslik = kayit["anlatim"][:65].replace("\n", " ")
            with st.expander(f"{kayit['saat']}  ·  {kayit['kategori']}  ·  {baslik}…"):
                st.markdown("**Anlatımınız**")
                st.write(kayit["anlatim"])
                g1, g2 = st.columns(2)
                with g1:
                    st.markdown("**📱 Instagram**")
                    st.write(kayit["instagram"])
                with g2:
                    st.markdown("**🛍️ Shopier**")
                    st.write(kayit["shopier"])

        if st.button("🗑  Geçmişi temizle"):
            st.session_state.gecmis = []
            st.rerun()


# ===========================================================================
# SEKME 3 — NASIL ÇALIŞIR
# ===========================================================================
with sekme_nasil:
    st.markdown("### 💡 Üç adımda içeriğiniz hazır")
    st.write("")

    a1, a2, a3 = st.columns(3, gap="medium")
    adimlar = [
        (a1, "1", "Siz anlatın",
         "Ürününüzü kendi cümlelerinizle yazın. Teknik bilgi, pazarlama dili "
         "ya da özel bir yazım biçimi gerekmez — nasıl konuşuyorsanız öyle yazın."),
        (a2, "2", "Yapay zekâ düzenlesin",
         "Anlatımınız, iki farklı kanala uygun metne dönüştürülür. Instagram "
         "için kısa ve dikkat çekici, Shopier için aranınca bulunan bir metin."),
        (a3, "3", "Siz onaylayın",
         "Metinleri okur, beğenmediğiniz yeri değiştirir ve onaylarsınız. "
         "Sizin onayınız olmadan hiçbir içerik kullanılmaz."),
    ]
    for kol, no, baslik, aciklama in adimlar:
        kol.markdown(f"""
        <div class="kart" style="min-height: 215px;">
          <div class="adim"><div class="adim-no">{no}</div>
          <div class="adim-yazi">{baslik.upper()}</div></div>
          <p>{aciklama}</p>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown("#### Neden iki ayrı metin?")
    n1, n2 = st.columns(2, gap="medium")
    n1.markdown("""
    <div class="kart">
      <div class="kart-baslik">📱 Instagram gönderisi</div>
      <p><b>Amacı:</b> kaydırırken durdurmak.<br><br>
      Kısa cümleler, sizin sesiniz ve ürününüzün en ilginç detayıyla başlayan
      bir açılış. Malzeme listesi burada yer almaz.</p>
    </div>
    """, unsafe_allow_html=True)
    n2.markdown("""
    <div class="kart">
      <div class="kart-baslik">🛍️ Shopier ürün açıklaması</div>
      <p><b>Amacı:</b> arayan kişinin bulması.<br><br>
      Ürünün adı, malzemesi, süresi ve kime uygun olduğu açıkça yazılır.
      İnsanların aramada kullandığı kelimeler doğal biçimde geçer.</p>
    </div>
    """, unsafe_allow_html=True)


# ===========================================================================
# SEKME 4 — ETİK VE GİZLİLİK
# ===========================================================================
with sekme_etik:
    st.markdown("### 🛡️ Güçlendiriyoruz, sömürmüyoruz")
    st.write("Yapay zekâyı burada bir *yazar* olarak değil, sizin sesinizi "
             "görünür kılan bir *araç* olarak kullanıyoruz.")
    st.write("")

    ilkeler = [
        ("🔍", "Şeffaflık",
         "Her içerikte yapay zekâ ile üretildiği açıkça belirtilir. Bunu gizlemeyiz."),
        ("🎙️", "Otantiklik",
         "Sizin anlatımınız temel alınır. Yapay zekâ hikâye uydurmaz, "
         "kullandığınız somut kelimeleri korur."),
        ("⚖️", "Abartısızlık",
         "“Mucize”, “garanti”, “en iyi” gibi ispatsız iddialar üretilmez. "
         "Gıda ürünlerinde sağlık iddiası kurulmaz."),
        ("✋", "İnsan onayı",
         "Hiçbir içerik sizin onayınız olmadan kullanılmaz. Son karar her zaman "
         "üreticidedir (human-in-the-loop)."),
        ("🔒", "Veri gizliliği",
         "Anlatımınız yalnızca içerik üretmek için kullanılır. KVKK kapsamında "
         "açık rıza olmadan saklanmaz veya paylaşılmaz."),
        ("🌱", "Önyargı kontrolü",
         "Üretilen metinler klişe ve kalıplaşmış dil açısından ölçülür; "
         "tek tip anlatım dayatılmaz."),
    ]
    for i in range(0, len(ilkeler), 2):
        kol1, kol2 = st.columns(2, gap="medium")
        for kol, (ikon, baslik, aciklama) in zip((kol1, kol2), ilkeler[i:i + 2]):
            kol.markdown(f"""
            <div class="kart" style="min-height: 128px;">
              <div class="kart-baslik">{ikon}  {baslik}</div>
              <p>{aciklama}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="altbilgi">Üretken Kadın · Samsung Innovation Campus '
                'Generative AI Capstone · Tuğçe Deniz & Barış Aslan</div>',
                unsafe_allow_html=True)
