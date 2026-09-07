# -*- coding: utf-8 -*-
"""
Üretken Kadın — Streamlit arayüzü (HITL: insan onaylı akış)

Tasarım: UI/UX Pro Max rehberine göre profesyonel, erişilebilir ve responsive.
- Tipografi: Lexend (başlık) + Source Sans 3 (metin) — erişilebilirlik odaklı.
- Semantik renk tokenleri (:root), WCAG AA kontrast, görünür odak halkası.
- Onboarding (atlanabilir), zengin boş durumlar, ince animasyonlar.

Çalıştırmak için:
    streamlit run src/app.py
"""

import csv
import glob
import io
import json
import os
from datetime import datetime

import streamlit as st

import kalite
import kvkk
import prompts
import trends
import uret

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Üretken Kadın — Emeğin dijital sesi",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Streamlit Cloud'da API anahtarı "secret" olarak gelir; uret.py os.getenv okuduğu
# için secret'ı ortam değişkenine aktarıyoruz (yerelde .env kullanılmaya devam eder).
try:
    for _a in ("GEMINI_API_KEY", "GEMINI_MODEL"):
        if _a in st.secrets:
            os.environ.setdefault(_a, str(st.secrets[_a]))
except Exception:
    pass

# Python tarafında (grafikler vb.) gereken renkler; tam palet CSS :root'ta.
ANA = "#9B3D63"; KOYU = "#4A2138"; SAGE = "#6E8F77"

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Oturum durumu
# ---------------------------------------------------------------------------
varsayilanlar = {
    "sonuc": None, "gecmis": [], "anlatim_metni": "",
    "uslup_ornekleri": [], "karsilastirma": None, "toplu_sonuc": None,
    "reels": None, "foto": None, "ses_rizasi": False, "onboarding_gizle": False,
}
for anahtar, deger in varsayilanlar.items():
    st.session_state.setdefault(anahtar, deger)


# ---------------------------------------------------------------------------
# KENAR ÇUBUĞU
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Ayarlar")
    buyuk_yazi = st.toggle("Büyük yazı modu", value=False,
                           help="Tüm metinleri büyütür — okuması zor gelenler için.")
    st.divider()

    st.markdown("**Ton profiliniz**")
    if st.session_state.uslup_ornekleri:
        st.success(f"Aktif — {len(st.session_state.uslup_ornekleri)} örnek "
                   "kullanılıyor. İçerikleriniz sizin üslubunuzla yazılıyor.")
    else:
        st.info("Henüz tanımlamadınız. *Ton Profilim* sekmesinden kendi "
                "metinlerinizi ekleyin.")

    st.divider()
    st.markdown("**Bu oturum**")
    st.metric("Üretilen içerik", len(st.session_state.gecmis))
    if st.session_state.gecmis:
        sayac = {}
        for kayit in st.session_state.gecmis:
            sayac[kayit["kategori"]] = sayac.get(kayit["kategori"], 0) + 1
        st.caption(f"En çok: {max(sayac, key=sayac.get)}")

    st.divider()
    st.caption("Yayınlamadan önce metinleri mutlaka okuyun — "
               "son karar her zaman sizindir.")

TABAN = "18px" if buyuk_yazi else "16px"


# ---------------------------------------------------------------------------
# TASARIM SİSTEMİ (CSS)
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {{
  --bg: #FBF8F6; --surface: #FFFFFF; --surface-2: #F7EFF2;
  --border: #ECE1E6; --border-strong: #DDCAD3;
  --primary: #9B3D63; --primary-deep: #4A2138; --primary-soft: #F4E6EC;
  --accent: #B0791E; --sage: #5E7E67;
  --text: #2E2A28; --text-2: #574E48; --muted: #6B5F64;
  --danger: #B3261E;
  --radius-sm: 10px; --radius: 14px; --radius-lg: 20px;
  --shadow-sm: 0 1px 2px rgba(74,33,56,.06);
  --shadow-md: 0 4px 16px rgba(74,33,56,.10);
  --shadow-lg: 0 14px 34px rgba(74,33,56,.16);
}}

/* ---- Temel ---- */
html {{ font-size: {TABAN}; }}
.stApp {{ background: var(--bg); }}
.stApp, .stApp p, .stApp li, .stApp label, input, textarea, select, button {{
  font-family: 'Source Sans 3', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--text); }}
.stApp p, .stApp li {{ line-height: 1.62; }}
h1, h2, h3, h4, .marka, .hero h1, .kart-baslik, .bolum-yazi, .metrik-deger {{
  font-family: 'Lexend', 'Source Sans 3', sans-serif; }}
[data-testid="stHeader"] {{ background: transparent; height: 0; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1180px; }}
.stApp {{ overflow-x: hidden; }}
.kart p, .hero p {{ overflow-wrap: anywhere; }}
a {{ color: var(--primary); }}

/* ---- Erişilebilirlik: görünür odak halkası ---- */
a:focus-visible, button:focus-visible, input:focus-visible,
textarea:focus-visible, select:focus-visible, [role="tab"]:focus-visible,
[data-baseweb="select"]:focus-within {{
  outline: 3px solid var(--accent) !important; outline-offset: 2px !important;
  border-radius: 8px; }}

/* ---- Navbar ---- */
.navbar {{ display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(120deg, var(--primary-deep) 0%, #5E2A44 100%);
  padding: 0.9rem 1.5rem; border-radius: var(--radius);
  margin-bottom: 1.4rem; box-shadow: var(--shadow-md); }}
.nav-brand {{ display: flex; align-items: center; gap: 0.7rem; }}
.nav-logo {{ width: 38px; height: 38px; border-radius: 11px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 130%);
  display: flex; align-items: center; justify-content: center; font-size: 1.2rem;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.15); }}
.marka {{ color: #fff; font-weight: 700; font-size: 1.18rem; letter-spacing: -.2px; }}
.marka-alt {{ color: #E4CFD8; font-size: 0.8rem; margin-top: -3px; }}
.nav-sag {{ display: flex; align-items: center; gap: 1.1rem; }}
.nav-sag a {{ color: #EBDCE2; text-decoration: none; font-size: 0.9rem;
  font-weight: 600; transition: color .16s ease; }}
.nav-sag a:hover {{ color: #fff; }}
.nav-rozet {{ background: rgba(255,255,255,.12); color: #fff; padding: 0.32rem 0.8rem;
  border-radius: 999px; font-size: 0.76rem; font-weight: 600; }}

/* ---- Hero ---- */
.hero {{ background: linear-gradient(150deg, var(--surface-2) 0%, #FCF3F0 60%, #FBEDF0 100%);
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: 2.6rem 2rem 2.2rem; text-align: center; margin-bottom: 1.1rem;
  animation: girisYumusak .5s ease both; }}
.hero-badge {{ display: inline-block; background: #fff; border: 1px solid var(--border-strong);
  color: var(--primary); font-weight: 600; font-size: 0.8rem; padding: 0.3rem 0.85rem;
  border-radius: 999px; margin-bottom: 1rem; box-shadow: var(--shadow-sm); }}
.hero h1 {{ color: var(--primary-deep); font-size: 2.35rem; line-height: 1.15;
  margin: 0 0 0.7rem; letter-spacing: -0.6px; font-weight: 700; }}
.hero h1 .vurgu {{ color: var(--primary); }}
.hero p {{ color: var(--text-2); font-size: 1.06rem; max-width: 600px;
  margin: 0 auto; line-height: 1.6; }}

/* ---- Onboarding adımları ---- */
.adimlar {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem;
  margin-bottom: 1.2rem; }}
.adim-kart {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.1rem 1.15rem; box-shadow: var(--shadow-sm);
  animation: girisYumusak .5s ease both; }}
.adim-kart:nth-child(2) {{ animation-delay: .06s; }}
.adim-kart:nth-child(3) {{ animation-delay: .12s; }}
.adim-rozet {{ width: 30px; height: 30px; border-radius: 9px; background: var(--primary-soft);
  color: var(--primary); font-weight: 700; font-size: 0.95rem; display: flex;
  align-items: center; justify-content: center; margin-bottom: 0.6rem;
  font-family: 'Lexend', sans-serif; }}
.adim-kart h4 {{ margin: 0 0 0.25rem; font-size: 1rem; color: var(--primary-deep); }}
.adim-kart p {{ margin: 0; font-size: 0.92rem; color: var(--muted); line-height: 1.5; }}

/* ---- Bölüm başlığı (adım göstergesi) ---- */
.bolum {{ display: flex; align-items: center; gap: 0.6rem; margin: 0.2rem 0 0.9rem; }}
.bolum-no {{ width: 28px; height: 28px; border-radius: 50%; background: var(--primary);
  color: #fff; font-weight: 700; font-size: 0.9rem; display: flex; align-items: center;
  justify-content: center; font-family: 'Lexend', sans-serif; box-shadow: var(--shadow-sm); }}
.bolum-no.ikinci {{ background: var(--sage); }}
.bolum-yazi {{ color: var(--primary-deep); font-weight: 600; font-size: 1.06rem; }}

/* ---- Kartlar ---- */
.kart {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.15rem 1.3rem; margin-bottom: 0.9rem;
  box-shadow: var(--shadow-sm); transition: box-shadow .18s ease, transform .18s ease; }}
.kart:hover {{ box-shadow: var(--shadow-md); }}
.kart-baslik {{ color: var(--primary); font-weight: 600; font-size: 0.98rem;
  margin-bottom: 0.4rem; }}
.kart p {{ color: var(--text-2); font-size: 0.97rem; line-height: 1.55; margin: 0; }}

/* ---- Zengin boş durum ---- */
.bos {{ background: var(--surface); border: 1.5px dashed var(--border-strong);
  border-radius: var(--radius); padding: 2rem 1.5rem; text-align: center; }}
.bos-ikon {{ font-size: 2rem; margin-bottom: 0.5rem; opacity: .85; }}
.bos h4 {{ margin: 0 0 0.5rem; color: var(--primary-deep); font-size: 1.08rem; }}
.bos p {{ color: var(--muted); font-size: 0.95rem; margin: 0 auto; max-width: 340px; }}
.bos-liste {{ text-align: left; max-width: 320px; margin: 0.9rem auto 0; }}
.bos-liste div {{ background: var(--surface-2); border-radius: var(--radius-sm);
  padding: 0.6rem 0.85rem; margin-bottom: 0.5rem; font-size: 0.92rem; color: var(--text-2); }}

/* ---- Metrikler ---- */
.metrik {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 0.85rem 1rem; text-align: center;
  box-shadow: var(--shadow-sm); }}
.metrik-deger {{ color: var(--primary); font-size: 1.55rem; font-weight: 700;
  line-height: 1.1; font-variant-numeric: tabular-nums; }}
.metrik-etiket {{ color: var(--muted); font-size: 0.82rem; margin-top: 0.25rem; }}

/* ---- Butonlar: varsayılan = temiz outline, primary = dolu CTA ---- */
.stButton > button, .stDownloadButton > button {{
  background: var(--surface); color: var(--primary);
  border: 1.5px solid var(--border-strong); border-radius: var(--radius-sm);
  font-family: 'Lexend', sans-serif; font-weight: 600; font-size: 0.95rem;
  min-height: 44px; padding: 0.5rem 1.1rem; cursor: pointer;
  transition: background .16s ease, border-color .16s ease, transform .12s ease, box-shadow .16s ease; }}
.stButton > button:hover:not(:disabled), .stDownloadButton > button:hover:not(:disabled) {{
  border-color: var(--primary); background: var(--primary-soft);
  transform: translateY(-1px); box-shadow: var(--shadow-sm); }}
.stButton > button:active:not(:disabled) {{ transform: translateY(0) scale(.99); }}
.stButton > button:disabled, .stDownloadButton > button:disabled {{
  opacity: 0.5; cursor: not-allowed; }}
.stDownloadButton > button {{ color: var(--sage); border-color: var(--sage); }}

/* primary CTA — tek güçlü eylem */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {{
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-deep) 115%);
  color: #fff !important; border: none; box-shadow: var(--shadow-md); }}
.stButton > button[kind="primary"]:hover:not(:disabled),
.stButton > button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{
  filter: brightness(1.06); transform: translateY(-1px); box-shadow: var(--shadow-lg);
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-deep) 115%); }}

/* ---- Girdi alanları ---- */
.stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {{
  border-radius: var(--radius-sm) !important; }}
.stTextArea textarea, .stTextInput input {{ font-size: 1rem !important;
  border: 1.5px solid var(--border-strong) !important; }}
.stTextArea textarea:focus, .stTextInput input:focus {{
  border-color: var(--primary) !important; }}

/* ---- Sekmeler ---- */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.25rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border); }}
.stTabs [data-baseweb="tab"] {{ border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  padding: 0.55rem 0.95rem; font-family: 'Lexend', sans-serif; font-weight: 600;
  font-size: 0.92rem; color: var(--muted); }}
.stTabs [aria-selected="true"] {{ background: var(--surface-2);
  color: var(--primary) !important; }}

/* ---- Bilgi şeritleri ---- */
.ifsa {{ background: var(--surface-2); border: 1px dashed var(--border-strong);
  border-radius: var(--radius-sm); color: var(--muted); font-size: 0.88rem;
  text-align: center; padding: 0.75rem; margin-top: 1.4rem; }}
.altbilgi {{ color: var(--muted); font-size: 0.85rem; text-align: center; margin-top: 1rem; }}

/* ---- Animasyon ---- */
@keyframes girisYumusak {{ from {{ opacity: 0; transform: translateY(10px); }}
  to {{ opacity: 1; transform: none; }} }}
.metrik, .kart, .bos {{ animation: girisYumusak .4s ease both; }}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ transition: none !important; animation: none !important; }}
}}

/* ---- Responsive (mobile-first inceltmeler) ---- */
@media (max-width: 720px) {{
  .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; }}
  .navbar {{ flex-direction: column; gap: 0.6rem; align-items: flex-start;
    padding: 0.85rem 1.1rem; }}
  .nav-sag {{ flex-wrap: wrap; gap: 0.7rem; }}
  .adimlar {{ grid-template-columns: 1fr; }}
  .hero {{ padding: 1.7rem 1.1rem; }}
  .hero h1 {{ font-size: 1.75rem; }}
  .hero p {{ font-size: 1rem; }}
  /* 8 sekme mobilde tek satırda yatay kaysın (alt alta kırılmak yerine) */
  .stTabs [data-baseweb="tab-list"] {{ flex-wrap: nowrap; overflow-x: auto;
    -webkit-overflow-scrolling: touch; }}
  .stTabs [data-baseweb="tab"] {{ white-space: nowrap; padding: 0.5rem 0.7rem; }}
}}
@media (max-width: 420px) {{
  .hero h1 {{ font-size: 1.55rem; }}
  .metrik-deger {{ font-size: 1.35rem; }}
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# NAVBAR
# ---------------------------------------------------------------------------
st.markdown("""
<div class="navbar">
  <div class="nav-brand">
    <div class="nav-logo">🧵</div>
    <div>
      <div class="marka">Üretken Kadın</div>
      <div class="marka-alt">Emeğin dijital sesi</div>
    </div>
  </div>
  <div class="nav-sag">
    <span class="nav-rozet">Yapay zekâ destekli · Son karar sizde</span>
    <a href="https://github.com/Tugce-hub/Uretken_Kadin" target="_blank">GitHub</a>
  </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def bolum(no: str, yazi: str, ikinci: bool = False) -> None:
    sinif = "bolum-no ikinci" if ikinci else "bolum-no"
    st.markdown(f'<div class="bolum"><div class="{sinif}">{no}</div>'
                f'<div class="bolum-yazi">{yazi}</div></div>', unsafe_allow_html=True)


def metrik_satiri(veriler: list[tuple]) -> None:
    for kol, (deger, etiket) in zip(st.columns(len(veriler)), veriler):
        kol.markdown(f'<div class="metrik"><div class="metrik-deger">{deger}</div>'
                     f'<div class="metrik-etiket">{etiket}</div></div>',
                     unsafe_allow_html=True)


def olcumler(ig: str, sh: str, kategori: str) -> tuple:
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    return (uret.seo_kapsami(f"{ig} {sh}", kelimeler), len(kelimeler),
            uret.klise_sayisi(f"{ig} {sh}"), uret.kanal_benzerligi(ig, sh))


TEKNIK_ADLARI = {
    "few_shot": "Örneklerle yazdır  (few-shot)",
    "zero_shot": "Örneksiz yazdır  (zero-shot)",
    "chain_of_thought": "Adım adım düşündür  (chain-of-thought)",
}

ORNEKLER = [
    ("Bebek battaniyesi", "Tekstil / El sanatı",
     "El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, "
     "tamamen elde örüyorum. Bir tanesi yaklaşık üç günümü alıyor. Anneannemden "
     "öğrendiğim bir desen kullanıyorum."),
    ("Domates salçası", "Gıda",
     "Ev yapımı domates salçası. Kendi bahçemizin domatesi, güneşte kurutuyorum. "
     "Hiçbir katkı maddesi yok, sadece domates ve tuz. 700 gramlık kavanozlarda "
     "satıyorum."),
    ("Gümüş kolye", "Takı / Aksesuar",
     "Gümüş tel sarma tekniğiyle kolye yapıyorum. 925 ayar gümüş tel kullanıyorum, "
     "taşları doğal taş. Her kolye tek, aynısından ikinci bir tane olmuyor."),
]


# ---------------------------------------------------------------------------
# SEKMELER
# ---------------------------------------------------------------------------
(s_uret, s_karsi, s_ton, s_toplu,
 s_gecmis, s_panel, s_nasil, s_etik) = st.tabs([
    "İçerik Üret", "Karşılaştır", "Ton Profilim", "Toplu Üretim",
    "Geçmişim", "Panel", "Nasıl Çalışır", "Etik & KVKK",
])


# ===========================================================================
# 1 — İÇERİK ÜRET
# ===========================================================================
with s_uret:
    st.markdown("""
    <div class="hero">
      <div class="hero-badge">Ücretsiz · Sesli veya yazılı · Dakikalar içinde</div>
      <h1>Emeğinizin bir hikâyesi var.<br>
          <span class="vurgu">Duyulmasını sağlayalım.</span></h1>
      <p>Ürününüzü kendi cümlelerinizle anlatın; Instagram gönderiniz, satış
         sayfası metniniz ve video çekim planınız hazır olsun.</p>
    </div>
    """, unsafe_allow_html=True)

    # ---------------- ONBOARDING (atlanabilir) ----------------
    if not st.session_state.onboarding_gizle:
        st.markdown("""
        <div class="adimlar">
          <div class="adim-kart"><div class="adim-rozet">1</div>
            <h4>Siz anlatın</h4>
            <p>Ürününüzü nasıl konuşuyorsanız öyle yazın ya da sesli anlatın.
               Teknik bilgi gerekmez.</p></div>
          <div class="adim-kart"><div class="adim-rozet">2</div>
            <h4>Yapay zekâ düzenlesin</h4>
            <p>Anlatımınız Instagram ve Shopier için iki ayrı, aranınca bulunan
               metne dönüşür.</p></div>
          <div class="adim-kart"><div class="adim-rozet">3</div>
            <h4>Siz onaylayın</h4>
            <p>Okur, dilediğiniz yeri değiştirir ve onaylarsınız. Onayınız
               olmadan hiçbir şey kullanılmaz.</p></div>
        </div>
        """, unsafe_allow_html=True)
        oc1, oc2 = st.columns([4, 1])
        with oc2:
            if st.button("Rehberi gizle", use_container_width=True):
                st.session_state.onboarding_gizle = True
                st.rerun()

    st.markdown("**Hızlı başlamak için hazır bir örnek deneyin:**")
    ok = st.columns(3)
    for kol, (etiket, ornek_kat, metin) in zip(ok, ORNEKLER):
        if kol.button(etiket, use_container_width=True, key=f"ornek_{etiket}"):
            st.session_state.anlatim_metni = metin
            st.rerun()

    st.divider()
    sol, sag = st.columns([1.05, 0.95], gap="large")

    # ---------------- SOL: GİRDİ ----------------
    with sol:
        bolum("1", "Ürününüzü anlatın")

        with st.expander("🎙️  Konuşarak anlatmak ister misiniz?"):
            st.caption("Yazmak zor geliyorsa konuşun — sesinizi metne çeviririz. "
                       "Kendi kelimeleriniz korunur, cümleleriniz değiştirilmez.")
            with st.expander("Verileriniz nasıl işlenir? (KVKK)"):
                st.markdown(kvkk.SES_AYDINLATMA)
            st.session_state.ses_rizasi = st.checkbox(
                kvkk.SES_RIZA_ETIKETI, value=st.session_state.ses_rizasi)
            ses_kaydi = st.audio_input("Kaydı başlatmak için mikrofona basın")
            cevir = st.button("Sesimi metne çevir", use_container_width=True,
                              disabled=not st.session_state.ses_rizasi)
            if ses_kaydi is not None and not st.session_state.ses_rizasi:
                st.info("Devam etmek için yukarıdaki açık rıza kutusunu işaretleyin.")
            if ses_kaydi is not None and st.session_state.ses_rizasi and cevir:
                with st.spinner("Ses kaydınız yazıya dökülüyor…"):
                    try:
                        metin = uret.sesten_metne(ses_kaydi.getvalue(), "audio/wav")
                        if metin:
                            st.session_state.anlatim_metni = metin
                            st.success("Metne çevrildi — aşağıdan düzenleyebilirsiniz.")
                            st.rerun()
                        else:
                            st.warning("Ses anlaşılamadı, tekrar dener misiniz?")
                    except Exception as hata:
                        st.error(f"Ses çevrilemedi: {hata}")

        anlatim = st.text_area(
            "Ürün anlatımı", height=180, key="anlatim_metni",
            placeholder="Ne ürettiğinizi, nasıl yaptığınızı ve ne kadar sürdüğünü "
                        "anlatın.\n\nÖrnek: El örgüsü bebek battaniyesi yapıyorum…",
            label_visibility="collapsed",
        )
        st.caption("🔒 " + kvkk.METIN_AYDINLATMA)

        k1, k2 = st.columns(2)
        with k1:
            kategori = st.selectbox("Kategori",
                                    list(prompts.KATEGORI_KELIMELERI.keys()))
        with k2:
            ton = st.selectbox("Anlatım tonu", ["sıcak ve samimi",
                                                "sade ve bilgilendirici",
                                                "şık ve zarif"])

        with st.expander("Gelişmiş ayarlar (rapor / karşılaştırma için)"):
            teknik = st.radio(
                "Yapay zekâya nasıl yazdıralım?",
                ["few_shot", "zero_shot", "chain_of_thought"],
                format_func=lambda t: TEKNIK_ADLARI[t],
                captions=[
                    "Örnek metinler göstererek — varsayılan, en iyi sonucu verir",
                    "Hiç örnek göstermeden — kıyaslama için",
                    "Yazmadan önce adım adım düşünmesini isteyerek",
                ])
            st.divider()
            st.caption("SEO anahtar kelimeleri Google Trends'ten canlı çekilir; "
                       "ulaşılamazsa sabit listeye düşülür.")
            if st.button("Bu kategori için Trends kelimelerini göster"):
                with st.spinner("Google Trends sorgulanıyor…"):
                    ts = trends.trend_getir(kategori)
                etiket = {"trends": "Google Trends (canlı)",
                          "önbellek": "Google Trends (önbellek)",
                          "varsayılan": "Varsayılan liste (Trends'e ulaşılamadı)"}
                st.info(f"**Kaynak:** {etiket[ts.kaynak]}\n\n" + ", ".join(ts.kelimeler))

        if st.button("✦   İçerik Üret", use_container_width=True, type="primary"):
            if not anlatim.strip():
                st.warning("Önce ürününüzü birkaç cümleyle anlatın.")
            elif len(anlatim.split()) < 5:
                st.warning("Biraz daha ayrıntı verin — en az bir iki cümle yazın.")
            else:
                with st.spinner("İçeriğiniz hazırlanıyor…"):
                    try:
                        sonuc = uret.icerik_uret(
                            anlatim=anlatim, kategori=kategori, ton=ton, teknik=teknik,
                            uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                        st.session_state.sonuc = sonuc
                        st.session_state.gecmis.insert(0, {
                            "saat": datetime.now().strftime("%H:%M"),
                            "kategori": kategori, "anlatim": anlatim,
                            "instagram": sonuc.instagram, "shopier": sonuc.shopier})
                    except Exception as hata:
                        st.session_state.sonuc = None
                        st.error(f"İçerik üretilemedi: {hata}")

    # ---------------- SAĞ: ÇIKTI ----------------
    with sag:
        bolum("2", "Düzenleyin ve onaylayın", ikinci=True)
        sonuc = st.session_state.sonuc

        if sonuc is None:
            st.markdown("""
            <div class="bos">
              <div class="bos-ikon">✍️</div>
              <h4>İçeriğiniz burada belirecek</h4>
              <p>Soldaki alana ürününüzü anlatıp <b>İçerik Üret</b>'e basın.
                 Size iki hazır metin sunacağız:</p>
              <div class="bos-liste">
                <div>📱 <b>Instagram gönderisi</b> — kısa, dikkat çeken, hikâyenizi anlatan</div>
                <div>🛍️ <b>Shopier açıklaması</b> — aranınca bulunan, bilgi veren</div>
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="kart-baslik">📱 Instagram gönderisi</div>',
                        unsafe_allow_html=True)
            ig = st.text_area("Instagram", value=sonuc.instagram, height=140,
                              label_visibility="collapsed")
            st.markdown('<div class="kart-baslik">🛍️ Shopier ürün açıklaması</div>',
                        unsafe_allow_html=True)
            sh = st.text_area("Shopier", value=sonuc.shopier, height=160,
                              label_visibility="collapsed")

            b1, b2 = st.columns(2)
            with b1:
                if st.button("✓   Onayla", use_container_width=True, type="primary"):
                    st.success("Onaylandı! Aşağıdan kopyalayabilirsiniz.")
            with b2:
                st.download_button("⬇  Metinleri indir",
                                   data=f"INSTAGRAM\n{ig}\n\nSHOPIER\n{sh}",
                                   file_name="uretken_kadin_icerik.txt",
                                   use_container_width=True)

            with st.expander("Kopyalamak için tıklayın"):
                st.caption("Instagram gönderisi"); st.code(ig, language=None)
                st.caption("Shopier açıklaması"); st.code(sh, language=None)

            kapsam, toplam, klise, benzerlik = olcumler(ig, sh, kategori)
            st.markdown("<br>", unsafe_allow_html=True)
            metrik_satiri([(f"{kapsam}/{toplam}", "SEO anahtar kelime"),
                           (str(klise), "klişe ifade"),
                           (f"{benzerlik:.2f}", "kanal benzerliği")])

            # Kalite ön-filtresi (HITL yardımcısı)
            model = kalite.model_al()
            if model.mevcut():
                thn = model.tahmin(f"{ig}\n{sh}", kategori)
                if thn["hazir"]:
                    st.success(f"🤖 **Onaya hazır** görünüyor "
                               f"(güven %{thn['olasilik'] * 100:.0f}). Yine de okuyup "
                               "onaylayın — son karar sizde.")
                else:
                    neden = "; ".join(thn["gerekceler"]) or "kalite sinyalleri zayıf"
                    st.warning(f"🤖 **Gözden geçirmenizi öneririz** "
                               f"(hazır olasılığı %{thn['olasilik'] * 100:.0f}). "
                               f"Dikkat: {neden}.")
                st.caption("Bu bir yardımcı tahmindir, karar değil. Metni siz onaylarsınız.")

            # Ek içerikler
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="kart-baslik">✨ Bu ürün için daha fazlası</div>',
                        unsafe_allow_html=True)
            e1, e2 = st.columns(2)
            with e1:
                if st.button("🎬  Reels senaryosu", use_container_width=True):
                    with st.spinner("Çekim planı hazırlanıyor…"):
                        try:
                            st.session_state.reels = uret.reels_uret(
                                anlatim=st.session_state.anlatim_metni,
                                kategori=kategori, ton=ton,
                                uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                        except Exception as hata:
                            st.error(f"Senaryo üretilemedi: {hata}")
            with e2:
                if st.button("📸  Fotoğraf rehberi", use_container_width=True):
                    with st.spinner("Çekim önerileri hazırlanıyor…"):
                        try:
                            st.session_state.foto = uret.foto_rehberi_uret(
                                anlatim=st.session_state.anlatim_metni, kategori=kategori)
                        except Exception as hata:
                            st.error(f"Rehber üretilemedi: {hata}")

            if st.session_state.get("reels"):
                with st.expander("🎬  Reels / TikTok çekim planı", expanded=True):
                    st.markdown(st.session_state.reels)
                    st.download_button("⬇  Senaryoyu indir", data=st.session_state.reels,
                                       file_name="reels_senaryosu.md", key="ind_reels")
            if st.session_state.get("foto"):
                with st.expander("📸  Fotoğraf çekim rehberi", expanded=True):
                    st.markdown(st.session_state.foto)
                    st.download_button("⬇  Rehberi indir", data=st.session_state.foto,
                                       file_name="fotograf_rehberi.md", key="ind_foto")

    st.markdown('<div class="ifsa">Bu içerik yapay zekâ ile üretilmiştir · '
                'yayınlamadan önce okuyup düzenleyin — son karar her zaman sizindir'
                '</div>', unsafe_allow_html=True)


# ===========================================================================
# 2 — KARŞILAŞTIR
# ===========================================================================
with s_karsi:
    st.markdown("### Prompt tekniklerini karşılaştırın")
    st.write("Aynı anlatım, üç farklı yöntemle işlenir. Hangi yaklaşımın daha iyi "
             "sonuç verdiğini yan yana görebilirsiniz — bu karşılaştırma, proje "
             "raporundaki *prompt tasarımı* bölümünün kanıtıdır.")

    k_anlatim = st.text_area("Karşılaştırılacak anlatım", height=110,
                             value=ORNEKLER[0][2],
                             help="Üç teknik de bu metin üzerinde çalıştırılacak.")
    kk1, kk2 = st.columns([1, 2])
    with kk1:
        k_kategori = st.selectbox("Kategori", list(prompts.KATEGORI_KELIMELERI.keys()),
                                  key="karsi_kat")

    if st.button("Üç tekniği de çalıştır", type="primary"):
        if len(k_anlatim.split()) < 5:
            st.warning("Karşılaştırma için biraz daha uzun bir anlatım girin.")
        else:
            sonuclar = {}
            ilerleme = st.progress(0.0, text="Başlıyor…")
            for i, tkn in enumerate(["zero_shot", "few_shot", "chain_of_thought"], 1):
                ilerleme.progress(i / 3, text=f"{tkn} çalışıyor… ({i}/3)")
                try:
                    sonuclar[tkn] = uret.icerik_uret(
                        anlatim=k_anlatim, kategori=k_kategori, teknik=tkn,
                        uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                except Exception as e:
                    sonuclar[tkn] = e
            ilerleme.empty()
            st.session_state.karsilastirma = (sonuclar, k_kategori)

    if st.session_state.karsilastirma:
        sonuclar, k_kat = st.session_state.karsilastirma
        for kol, (tkn, sonuc) in zip(st.columns(3, gap="medium"), sonuclar.items()):
            with kol:
                st.markdown(f'<div class="kart-baslik">{TEKNIK_ADLARI[tkn]}</div>',
                            unsafe_allow_html=True)
                if isinstance(sonuc, Exception):
                    st.error(f"Hata: {sonuc}")
                    continue
                st.markdown("**📱 Instagram**"); st.write(sonuc.instagram)
                st.markdown("**🛍️ Shopier**"); st.write(sonuc.shopier)
                kapsam, toplam, klise, benzerlik = olcumler(
                    sonuc.instagram, sonuc.shopier, k_kat)
                st.caption(f"SEO {kapsam}/{toplam} · klişe {klise} · "
                           f"benzerlik {benzerlik:.2f}")

        basarililar = {t: s for t, s in sonuclar.items()
                       if not isinstance(s, Exception)}
        if len(basarililar) > 1:
            st.divider()
            st.markdown("#### Özet karşılaştırma")
            satirlar = []
            for tkn, sonuc in basarililar.items():
                kapsam, toplam, klise, benzerlik = olcumler(
                    sonuc.instagram, sonuc.shopier, k_kat)
                satirlar.append({
                    "Teknik": TEKNIK_ADLARI[tkn],
                    "SEO kapsamı": f"{kapsam}/{toplam}",
                    "Klişe (az iyi)": klise,
                    "Kanal benzerliği (az iyi)": round(benzerlik, 2),
                    "Instagram (kelime)": len(sonuc.instagram.split()),
                    "Shopier (kelime)": len(sonuc.shopier.split())})
            st.dataframe(satirlar, use_container_width=True, hide_index=True)


# ===========================================================================
# 3 — TON PROFİLİM
# ===========================================================================
with s_ton:
    st.markdown("### Kendi üslubunuzu öğretin")
    st.write("Daha önce yazdığınız paylaşımlardan birkaçını buraya yapıştırın. "
             "Yapay zekâ bunları okuyup **sizin gibi yazmayı** öğrenir — cümle "
             "uzunluğunuzu, samimiyetinizi ve kelime tercihlerinizi taklit eder. "
             "İçerikleriniz kopyalanmaz, yalnızca üslubunuz örnek alınır.")

    with st.form("ton_formu"):
        st.markdown("**Kendi yazdığınız metinler** (en az bir tane)")
        y1 = st.text_area("Örnek 1", height=80,
                          placeholder="Örn: Bugün de tezgah başındayım, sabahtan "
                                      "beri örüyorum. Bu rengi çok sevdim…")
        y2 = st.text_area("Örnek 2 (isteğe bağlı)", height=80)
        y3 = st.text_area("Örnek 3 (isteğe bağlı)", height=80)
        kaydet = st.form_submit_button("Ton profilimi kaydet", type="primary")

    if kaydet:
        yeni = [m for m in (y1, y2, y3) if m and m.strip()]
        if not yeni:
            st.warning("En az bir metin yapıştırın.")
        else:
            st.session_state.uslup_ornekleri = yeni
            st.success(f"Ton profiliniz kaydedildi ({len(yeni)} örnek). "
                       "Bundan sonraki tüm içerikler sizin üslubunuzla yazılacak.")

    if st.session_state.uslup_ornekleri:
        st.divider()
        st.markdown("#### Aktif ton profiliniz")
        for i, ornek in enumerate(st.session_state.uslup_ornekleri, 1):
            st.markdown(f'<div class="kart"><div class="kart-baslik">Örnek {i}</div>'
                        f'<p>{ornek}</p></div>', unsafe_allow_html=True)
        if st.button("Ton profilini sil"):
            st.session_state.uslup_ornekleri = []
            st.rerun()
    else:
        st.info("Şu an ton profiliniz yok — varsayılan örnekler kullanılıyor.")


# ===========================================================================
# 4 — TOPLU ÜRETİM
# ===========================================================================
with s_toplu:
    st.markdown("### Birden fazla ürün için tek seferde içerik")
    st.write("Çok ürününüz varsa hepsini tek tek yazmanıza gerek yok. Ürün "
             "anlatımlarınızı içeren bir **CSV dosyası** yükleyin, tümü için "
             "içerik üretelim.")

    st.markdown('<div class="kart"><div class="kart-baslik">Dosya biçimi</div>'
                '<p>CSV dosyanızda <b>anlatim</b> sütunu bulunmalı. İsteğe bağlı '
                'olarak <b>kategori</b> sütunu da ekleyebilirsiniz.</p></div>',
                unsafe_allow_html=True)

    ornek_csv = "anlatim,kategori\nEl örgüsü bebek battaniyesi yapıyorum…,Tekstil / El sanatı\n"
    st.download_button("⬇  Örnek CSV şablonunu indir", data=ornek_csv,
                       file_name="ornek_sablon.csv")

    yuklenen = st.file_uploader("CSV dosyanızı seçin", type=["csv"])
    t_kategori = st.selectbox("Varsayılan kategori (dosyada yoksa kullanılır)",
                              list(prompts.KATEGORI_KELIMELERI.keys()), key="toplu_kat")

    if yuklenen is not None:
        try:
            icerik = yuklenen.getvalue().decode("utf-8-sig")
            satirlar = list(csv.DictReader(io.StringIO(icerik)))
        except Exception as e:
            satirlar = []
            st.error(f"Dosya okunamadı: {e}")

        if satirlar and "anlatim" not in satirlar[0]:
            st.error("CSV dosyasında **anlatim** sütunu bulunamadı.")
        elif satirlar:
            st.success(f"{len(satirlar)} ürün bulundu.")
            if st.button(f"{len(satirlar)} ürün için içerik üret", type="primary"):
                cikti, ilerleme = [], st.progress(0.0, text="Başlıyor…")
                for i, satir in enumerate(satirlar, 1):
                    ilerleme.progress(i / len(satirlar),
                                      text=f"{i}/{len(satirlar)} üretiliyor…")
                    kat = satir.get("kategori") or t_kategori
                    try:
                        s = uret.icerik_uret(
                            anlatim=satir["anlatim"], kategori=kat,
                            uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                        cikti.append({"anlatim": satir["anlatim"], "kategori": kat,
                                      "instagram": s.instagram, "shopier": s.shopier,
                                      "durum": "✅"})
                    except Exception as e:
                        cikti.append({"anlatim": satir["anlatim"], "kategori": kat,
                                      "instagram": "", "shopier": "",
                                      "durum": f"⚠️ {str(e)[:60]}"})
                ilerleme.empty()
                st.session_state.toplu_sonuc = cikti

    if st.session_state.toplu_sonuc:
        st.divider()
        basarili = sum(1 for s in st.session_state.toplu_sonuc if s["durum"] == "✅")
        st.markdown(f"#### Sonuçlar — {basarili}/{len(st.session_state.toplu_sonuc)} başarılı")
        st.dataframe(st.session_state.toplu_sonuc, use_container_width=True,
                     hide_index=True)
        tampon = io.StringIO()
        yazici = csv.DictWriter(tampon, fieldnames=list(
            st.session_state.toplu_sonuc[0].keys()))
        yazici.writeheader(); yazici.writerows(st.session_state.toplu_sonuc)
        st.download_button("⬇  Sonuçları CSV olarak indir", data=tampon.getvalue(),
                           file_name="uretken_kadin_toplu.csv")


# ===========================================================================
# 5 — GEÇMİŞİM
# ===========================================================================
with s_gecmis:
    st.markdown("### Bu oturumda ürettikleriniz")
    if not st.session_state.gecmis:
        st.markdown("""
        <div class="bos"><div class="bos-ikon">📁</div>
          <h4>Henüz içerik üretmediniz</h4>
          <p><b>İçerik Üret</b> sekmesinden başlayın; ürettikleriniz burada listelenir.</p>
        </div>""", unsafe_allow_html=True)
    else:
        st.caption(f"Toplam {len(st.session_state.gecmis)} içerik üretildi. "
                   "(Sayfayı yenilerseniz bu liste sıfırlanır.)")
        for kayit in st.session_state.gecmis:
            baslik = kayit["anlatim"][:65].replace("\n", " ")
            with st.expander(f"{kayit['saat']}  ·  {kayit['kategori']}  ·  {baslik}…"):
                st.markdown("**Anlatımınız**"); st.write(kayit["anlatim"])
                g1, g2 = st.columns(2)
                g1.markdown("**📱 Instagram**"); g1.write(kayit["instagram"])
                g2.markdown("**🛍️ Shopier**"); g2.write(kayit["shopier"])
        if st.button("Geçmişi temizle"):
            st.session_state.gecmis = []
            st.rerun()


# ===========================================================================
# 6 — PANEL
# ===========================================================================
with s_panel:
    st.markdown("### Test sonuçları paneli")
    st.write("`ciktilar/` klasöründeki toplu test sonuçları — projenin ölçülebilir "
             "kanıtı. Her çalıştırma ayrı bir dosyaya kaydedilir.")

    dosyalar = sorted(glob.glob(os.path.join(KOK, "ciktilar", "*.csv")), reverse=True)
    if not dosyalar:
        st.info("Henüz toplu test çalıştırılmamış.\n\n"
                "Terminalden `python src/toplu_test.py` komutuyla çalıştırabilirsiniz.")
    else:
        secilen = st.selectbox("Sonuç dosyası",
                               [os.path.basename(d) for d in dosyalar])
        with open(os.path.join(KOK, "ciktilar", secilen), encoding="utf-8-sig") as f:
            satirlar = list(csv.DictReader(f))
        basarili = [s for s in satirlar if not s.get("hata")]

        if not basarili:
            st.warning("Bu dosyada başarılı sonuç yok.")
        else:
            sayi = lambda k: [float(s.get(k) or 0) for s in basarili]
            ort = lambda k: sum(sayi(k)) / len(basarili)
            metrik_satiri([
                (f"{len(basarili)}/{len(satirlar)}", "başarılı üretim"),
                (f"%{100 * sum(sayi('seo_kapsam')) / max(sum(sayi('seo_toplam')), 1):.0f}",
                 "SEO kapsamı"),
                (f"{sum(sayi('klise')):.0f}", "toplam klişe"),
                (f"{ort('benzerlik'):.2f}", "ort. kanal benzerliği"),
            ])
            st.markdown("<br>", unsafe_allow_html=True)
            p1, p2 = st.columns(2, gap="medium")
            with p1:
                st.markdown("**Kategoriye göre SEO kapsamı**")
                kategoriler = {}
                for s in basarili:
                    kategoriler.setdefault(s["kategori"], []).append(
                        float(s["seo_kapsam"]) / max(float(s["seo_toplam"]), 1))
                st.bar_chart({k: sum(v) / len(v) for k, v in kategoriler.items()},
                             height=260, color=ANA)
            with p2:
                st.markdown("**Ortalama metin uzunluğu (kelime)**")
                st.bar_chart({"Instagram": ort("ig_kelime"),
                              "Shopier": ort("sh_kelime")}, height=260, color=SAGE)
            with st.expander("Ham veriyi göster"):
                st.dataframe(satirlar, use_container_width=True, hide_index=True)

    # İçerik kalite modeli
    st.divider()
    st.markdown("### İçerik kalite modeli")
    st.write("İçeriğin *onaya hazır* mı yoksa *revizyon gerek* mi olduğunu kestiren "
             "sınıflandırıcı (HITL ön-filtresi). Metrikler prototip veri setinde "
             "hesaplanmıştır; saha pilotunda güncellenecektir.")
    metrik_yolu = os.path.join(KOK, "ciktilar", "model", "metrikler.json")
    if not os.path.exists(metrik_yolu):
        st.info("Model henüz eğitilmemiş.\n\n"
                "Terminalden: `python src/kalite_veri_uret.py` sonra "
                "`python src/kalite_egit.py`")
    else:
        with open(metrik_yolu, encoding="utf-8") as f:
            m = json.load(f)
        metrik_satiri([
            (f"%{m['dogruluk'] * 100:.0f}", "doğruluk"),
            (f"{m['f1_yuksek']:.2f}", "F1 (yüksek)"),
            (f"{m['roc_auc']:.2f}", "ROC-AUC"),
            (f"{m['duyarlilik_dusuk']:.2f}", "recall (düşük sınıf)"),
        ])
        st.markdown("<br>", unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3, gap="medium")
        for kol, dosya, alt in [
            (g1, "confusion_matrix.png", "Confusion matrix"),
            (g2, "roc_egrisi.png", "ROC eğrisi"),
            (g3, "oznitelik_onemi.png", "Öznitelik önemi")]:
            yol = os.path.join(KOK, "ciktilar", "model", dosya)
            if os.path.exists(yol):
                kol.image(yol, caption=alt, use_container_width=True)


# ===========================================================================
# 7 — NASIL ÇALIŞIR
# ===========================================================================
with s_nasil:
    st.markdown("### Üç adımda içeriğiniz hazır")
    st.write("")
    a1, a2, a3 = st.columns(3, gap="medium")
    for kol, no, baslik, aciklama in [
        (a1, "1", "Siz anlatın",
         "Ürününüzü kendi cümlelerinizle yazın. Teknik bilgi ya da özel bir yazım "
         "biçimi gerekmez — nasıl konuşuyorsanız öyle yazın."),
        (a2, "2", "Yapay zekâ düzenlesin",
         "Anlatımınız iki farklı kanala uygun metne dönüşür: Instagram için kısa ve "
         "dikkat çekici, Shopier için aranınca bulunan bir metin."),
        (a3, "3", "Siz onaylayın",
         "Metinleri okur, beğenmediğiniz yeri değiştirir ve onaylarsınız. Sizin "
         "onayınız olmadan hiçbir içerik kullanılmaz."),
    ]:
        kol.markdown(f"""
        <div class="kart" style="min-height: 210px;">
          <div class="adim-rozet">{no}</div>
          <h4 style="margin:0 0 .3rem; color:var(--primary-deep);">{baslik}</h4>
          <p>{aciklama}</p>
        </div>""", unsafe_allow_html=True)

    st.write("")
    st.markdown("#### Neden iki ayrı metin?")
    n1, n2 = st.columns(2, gap="medium")
    n1.markdown("""
    <div class="kart"><div class="kart-baslik">📱 Instagram gönderisi</div>
      <p><b>Amacı:</b> kaydırırken durdurmak. Kısa cümleler, sizin sesiniz ve
      ürününüzün en ilginç detayıyla başlayan bir açılış. Malzeme listesi burada
      yer almaz.</p></div>""", unsafe_allow_html=True)
    n2.markdown("""
    <div class="kart"><div class="kart-baslik">🛍️ Shopier ürün açıklaması</div>
      <p><b>Amacı:</b> arayan kişinin bulması. Ürünün adı, malzemesi, süresi ve kime
      uygun olduğu açıkça yazılır. İnsanların aramada kullandığı kelimeler doğal
      biçimde geçer.</p></div>""", unsafe_allow_html=True)

    st.write("")
    st.markdown("#### Diğer özellikler")
    for kol, ad, aciklama in [
        (c, a, b) for c, (a, b) in zip(st.columns(3, gap="medium"), [
            ("🎙️ Sesli anlatım",
             "Yazmak zor geliyorsa konuşun — sesiniz metne çevrilir, kelimeleriniz korunur."),
            ("📦 Toplu üretim",
             "CSV yükleyin, tüm ürünleriniz için tek seferde içerik alın."),
            ("🎬 Reels ve fotoğraf",
             "Video çekim planı ve ürününüze özel fotoğraf rehberi alın.")])]:
        kol.markdown(f'<div class="kart" style="min-height:120px;">'
                     f'<div class="kart-baslik">{ad}</div>'
                     f'<p>{aciklama}</p></div>', unsafe_allow_html=True)


# ===========================================================================
# 8 — ETİK & KVKK
# ===========================================================================
with s_etik:
    st.markdown("### Güçlendiriyoruz, sömürmüyoruz")
    st.write("Yapay zekâyı burada bir *yazar* olarak değil, sizin sesinizi görünür "
             "kılan bir *araç* olarak kullanıyoruz.")
    st.write("")

    ilkeler = [
        ("Şeffaflık",
         "Her içerikte yapay zekâ ile üretildiği açıkça belirtilir. Bunu gizlemeyiz."),
        ("Otantiklik",
         "Sizin anlatımınız temel alınır. Yapay zekâ hikâye uydurmaz, kullandığınız "
         "somut kelimeleri korur."),
        ("Abartısızlık",
         "“Mucize”, “garanti”, “en iyi” gibi ispatsız iddialar üretilmez. Gıda "
         "ürünlerinde sağlık iddiası kurulmaz."),
        ("İnsan onayı",
         "Hiçbir içerik sizin onayınız olmadan kullanılmaz. Son karar her zaman "
         "üreticidedir (human-in-the-loop)."),
        ("Veri gizliliği",
         "Anlatımınız yalnızca içerik üretmek için kullanılır. KVKK kapsamında açık "
         "rıza olmadan saklanmaz veya paylaşılmaz."),
        ("Önyargı kontrolü",
         "Üretilen metinler klişe ve kalıplaşmış dil açısından ölçülür; tek tip "
         "anlatım dayatılmaz."),
    ]
    for i in range(0, len(ilkeler), 2):
        for kol, (baslik, aciklama) in zip(st.columns(2, gap="medium"), ilkeler[i:i + 2]):
            kol.markdown(f'<div class="kart" style="min-height:120px;">'
                         f'<div class="kart-baslik">{baslik}</div>'
                         f'<p>{aciklama}</p></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### KVKK — Kişisel verileriniz")
    st.write("Sesli/yazılı anlatımınız içerik üretmek için Google Gemini'ye "
             "gönderilir. Bunun ne anlama geldiğini açıkça anlatıyoruz:")
    for i in range(0, len(kvkk.POLITIKA_MADDELERI), 2):
        for kol, (baslik, aciklama) in zip(st.columns(2, gap="medium"),
                                           kvkk.POLITIKA_MADDELERI[i:i + 2]):
            kol.markdown(f'<div class="kart" style="min-height:130px;">'
                         f'<div class="kart-baslik">{baslik}</div>'
                         f'<p>{aciklama}</p></div>', unsafe_allow_html=True)

    st.markdown('<div class="altbilgi">Üretken Kadın · Emeğin dijital sesi</div>',
                unsafe_allow_html=True)
