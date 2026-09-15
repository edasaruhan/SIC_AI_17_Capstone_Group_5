# -*- coding: utf-8 -*-
"""
Üretken Kadın — Streamlit arayüzü (son kullanıcı odaklı, rehberli akış)

Tasarım felsefesi: kullanıcı teknolojiden anlamayan bir üreticidir. Bu yüzden
her şey TEK panoda yığılmaz; adım adım, sade bir akış vardır:
    Karşılama (ne yapıyoruz) → Anlat → Sonuç
Mühendis/rapor işleri (prompt karşılaştırma, test paneli, ML metrikleri, toplu
üretim) kenar çubuğundaki "Geliştirici modu" arkasına gizlenmiştir.

Çalıştırmak için:
    streamlit run src/app.py
"""

import csv
import glob
import html
import io
import json
import os
import re
from datetime import timedelta

import streamlit as st
import streamlit.components.v1 as components

import kalite
import kvkk
import prompts
import takvim
import trends
import uret

# ---------------------------------------------------------------------------
st.set_page_config(page_title="Üretken Kadın — Emeğin dijital sesi",
                   page_icon="🧵", layout="centered",
                   initial_sidebar_state="collapsed")

# Streamlit Cloud'da API anahtarı "secret" olarak gelir; uret.py os.getenv okur.
try:
    for _a in ("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_MODEL_OZENLI", "GEMINI_MODEL_SES",
               "API_ADRESI", "API_ILETISIM"):
        if _a in st.secrets:
            os.environ.setdefault(_a, str(st.secrets[_a]))
except Exception:
    pass
# uret.py model adlarını import anında okur; secrets sonradan geldiği için tazele.
uret.modelleri_yenile()

ANA = "#9B3D63"; KOYU = "#4A2138"; SAGE = "#6E8F77"
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kullanıcıya gösterilen dostça kategori adları → prompts anahtarları
KATEGORILER = {
    "🧶 El işi & tekstil": "Tekstil / El sanatı",
    "🍯 Gıda": "Gıda",
    "💍 Takı & aksesuar": "Takı / Aksesuar",
    "🎨 Tasarım & dekor": "Tasarım / Dekorasyon",
}
ORNEKLER = [
    ("🧶 Bebek battaniyesi", "🧶 El işi & tekstil",
     "El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, "
     "tamamen elde örüyorum. Bir tanesi yaklaşık üç günümü alıyor. Anneannemden "
     "öğrendiğim bir desen kullanıyorum."),
    ("🍅 Domates salçası", "🍯 Gıda",
     "Ev yapımı domates salçası. Kendi bahçemizin domatesi, güneşte kurutuyorum. "
     "Hiçbir katkı maddesi yok, sadece domates ve tuz. 700 gramlık kavanozlarda."),
    ("💍 Gümüş kolye", "💍 Takı & aksesuar",
     "Gümüş tel sarma tekniğiyle kolye yapıyorum. 925 ayar gümüş tel kullanıyorum, "
     "taşları doğal taş. Her kolye tek, aynısından ikinci bir tane olmuyor."),
]


# ---------------------------------------------------------------------------
# Oturum durumu
# ---------------------------------------------------------------------------
EKRANLAR = ("karsilama", "anlat", "sonuc", "pano", "iceriklerim", "ton", "yardim", "api")

varsayilanlar = {
    "ekran": "karsilama", "yigin": [], "sonuc": None, "gecmis": [],
    "anlatim_metni": "", "kategori_key": "Tekstil / El sanatı",
    "uslup_ornekleri": [], "ses_rizasi": False,
    "aktif_id": None, "plan": [], "pano_mesaj": None,
    "karsilastirma": None, "toplu_sonuc": None,
}
for a, d in varsayilanlar.items():
    st.session_state.setdefault(a, d)
# Geçmiş kayıtları kimlikle takvime ve ek formatlara bağlanır; eski oturumlarda eksik olabilir.
for _k in st.session_state.gecmis:
    _k.setdefault("id", takvim.yeni_id())
    _k.setdefault("tarih", "")
    _k.setdefault("ekler", {})


def _url_yaz(hedef: str) -> None:
    """Ekranı URL'e yazar — tarayıcının geri/ileri tuşu da çalışsın diye."""
    try:
        st.query_params["ekran"] = hedef
    except Exception:
        pass


def git(hedef: str) -> None:
    """Yeni ekrana geçer ve geldiği ekranı geri yığınına koyar."""
    if st.session_state.ekran != hedef:
        st.session_state.yigin.append(st.session_state.ekran)
        st.session_state.yigin = st.session_state.yigin[-10:]   # yığın şişmesin
    st.session_state.ekran = hedef
    _url_yaz(hedef)
    st.rerun()


def geri() -> None:
    """Bir önceki ekrana döner; yığın boşsa karşılamaya."""
    hedef = st.session_state.yigin.pop() if st.session_state.yigin else "karsilama"
    st.session_state.ekran = hedef
    _url_yaz(hedef)
    st.rerun()


# Tarayıcının geri/ileri tuşu URL'i değiştirir; onu ekrana yansıt.
try:
    # Parametre yoksa kök ekran sayılır; böylece ilk adımda da geri tuşu çalışır.
    _url_ekran = st.query_params.get("ekran") or "karsilama"
    if _url_ekran in EKRANLAR and _url_ekran != st.session_state.ekran:
        st.session_state.ekran = _url_ekran
except Exception:
    pass


# ---------------------------------------------------------------------------
# KENAR ÇUBUĞU — sade ayarlar + gizli geliştirici modu
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Ayarlar")
    buyuk_yazi = st.toggle("Büyük yazı modu", value=False,
                           help="Tüm yazıları büyütür — okuması zor gelenler için.")
    ozenli = st.toggle("Daha özenli yaz", value=False,
                       help="İçerikler biraz daha yavaş hazırlanır ama daha özenli "
                            "yazılır. Kapalıyken birkaç saniyede hazır olur.")
    st.divider()
    st.caption("Ton profiliniz")
    if st.session_state.uslup_ornekleri:
        st.success(f"Aktif ({len(st.session_state.uslup_ornekleri)} örnek)")
    else:
        st.caption("Tanımlı değil.")
    if st.button("Sizin gibi yazmasını öğretin", use_container_width=True):
        git("ton")
    st.divider()
    st.caption("Firmalar ve kurumlar için")
    if st.button("🔌 API ile entegrasyon", use_container_width=True,
                 help="Üretken Kadın'ı kendi platformunuza bağlamak için belgeler"):
        git("api")
    st.divider()
    gelistirici = st.toggle("🔧 Geliştirici / rapor modu", value=False,
                            help="Prompt karşılaştırma, test paneli ve model "
                                 "metrikleri — capstone raporu içindir.")
    st.divider()
    st.caption("Yayınlamadan önce metinleri okuyun — son karar her zaman sizindir.")

TABAN = "18px" if buyuk_yazi else "16.5px"


# ---------------------------------------------------------------------------
# TASARIM SİSTEMİ (CSS) — sıcak, sade, büyük dokunma hedefleri
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
:root {{
  --bg:#FBF8F6; --surface:#FFFFFF; --surface-2:#F7EFF2;
  --border:#ECE1E6; --border-strong:#DDCAD3;
  --primary:#9B3D63; --primary-deep:#4A2138; --primary-soft:#F4E6EC;
  --accent:#B0791E; --sage:#5E7E67;
  --text:#2E2A28; --text-2:#574E48; --muted:#6B5F64;
  --radius-sm:12px; --radius:16px; --radius-lg:22px;
  --shadow-sm:0 1px 2px rgba(74,33,56,.06);
  --shadow-md:0 6px 20px rgba(74,33,56,.10);
  --shadow-lg:0 16px 40px rgba(74,33,56,.16);
}}
html {{ font-size:{TABAN}; }}
.stApp {{ background:var(--bg); overflow-x:hidden; }}
.stApp, .stApp p, .stApp li, .stApp label, input, textarea, select, button {{
  font-family:'Source Sans 3',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  color:var(--text); }}
.stApp p, .stApp li {{ line-height:1.65; }}
h1,h2,h3,h4,.marka,.dev-baslik {{ font-family:'Lexend','Source Sans 3',sans-serif; }}
[data-testid="stHeader"] {{ background:transparent; height:0; }}
/* Araç çubuğu açık kalır: kenar çubuğunu açan ok onun içinde. Yalnız menü ve Deploy gizli. */
#MainMenu, footer, [data-testid="stMainMenu"], [data-testid="stAppDeployButton"] {{ display:none !important; }}
.block-container {{ padding-top:1.2rem; padding-bottom:3.5rem; max-width:760px; }}
.kart p,.hero p {{ overflow-wrap:anywhere; }}
a {{ color:var(--primary); }}

a:focus-visible, button:focus-visible, input:focus-visible,
textarea:focus-visible, select:focus-visible, [data-baseweb="select"]:focus-within {{
  outline:3px solid var(--accent) !important; outline-offset:2px !important; border-radius:8px; }}

/* Üst bar */
.ustbar {{ display:flex; align-items:center; gap:.7rem; margin-bottom:1.1rem; }}
.ustbar .logo {{ width:40px; height:40px; border-radius:12px;
  background:linear-gradient(135deg,var(--primary),var(--accent) 130%);
  display:flex; align-items:center; justify-content:center; font-size:1.25rem; }}
.ustbar .ad {{ font-family:'Lexend'; font-weight:700; font-size:1.15rem; color:var(--primary-deep); }}
.ustbar .alt {{ font-size:.8rem; color:var(--muted); margin-top:-3px; }}

/* Karşılama */
.karsilama {{ text-align:center; padding:1rem 0 0; animation:gir .5s ease both; }}
.karsilama .amblem {{ width:84px; height:84px; border-radius:24px; margin:0 auto 1.1rem;
  background:linear-gradient(135deg,var(--primary),var(--accent) 140%);
  display:flex; align-items:center; justify-content:center; font-size:2.4rem;
  box-shadow:var(--shadow-md); }}
.karsilama h1 {{ font-size:2.15rem; color:var(--primary-deep); margin:0 0 .6rem;
  letter-spacing:-.5px; line-height:1.15; }}
.karsilama .slogan {{ color:var(--primary); font-weight:600; }}
.karsilama .aciklama {{ color:var(--text-2); font-size:1.1rem; max-width:520px;
  margin:0 auto 1.6rem; }}
.adimlar {{ display:grid; grid-template-columns:repeat(3,1fr); gap:.8rem; margin:1.4rem 0; text-align:left; }}
.adim {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  padding:1.1rem; box-shadow:var(--shadow-sm); }}
.adim .no {{ width:34px; height:34px; border-radius:11px; background:var(--primary-soft);
  color:var(--primary); font-weight:700; font-size:1.1rem; display:flex; align-items:center;
  justify-content:center; margin-bottom:.6rem; font-family:'Lexend'; }}
.adim h4 {{ margin:0 0 .2rem; font-size:1.02rem; color:var(--primary-deep); }}
.adim p {{ margin:0; font-size:.94rem; color:var(--muted); }}
.guven {{ background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius);
  padding:.9rem 1.1rem; color:var(--text-2); font-size:.96rem; margin:1rem 0 1.4rem; }}

/* Başlıklar / kartlar */
.ekran-baslik {{ font-size:1.7rem; color:var(--primary-deep); margin:.2rem 0 .3rem; }}
.ekran-alt {{ color:var(--muted); font-size:1.03rem; margin-bottom:1.2rem; }}
.kart {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  padding:1.2rem 1.3rem; margin-bottom:1rem; box-shadow:var(--shadow-sm); animation:gir .35s ease both; }}
.kart-baslik {{ color:var(--primary); font-weight:700; font-size:1.05rem; margin-bottom:.5rem;
  font-family:'Lexend'; }}
.kart p {{ color:var(--text-2); margin:0; }}
.bos {{ text-align:center; padding:2rem 1rem; color:var(--muted); }}
.bos .ik {{ font-size:2.2rem; }}

/* Butonlar — büyük, dostça */
.stButton > button, .stDownloadButton > button {{
  background:var(--surface); color:var(--primary); border:1.5px solid var(--border-strong);
  border-radius:var(--radius-sm); font-family:'Lexend'; font-weight:600; font-size:1.02rem;
  min-height:52px; padding:.7rem 1.2rem; cursor:pointer;
  transition:background .16s ease,border-color .16s ease,transform .12s ease,box-shadow .16s ease; }}
.stButton > button:hover:not(:disabled), .stDownloadButton > button:hover:not(:disabled) {{
  border-color:var(--primary); background:var(--primary-soft); transform:translateY(-1px);
  box-shadow:var(--shadow-sm); }}
.stButton > button:active:not(:disabled) {{ transform:translateY(0) scale(.99); }}
.stButton > button:disabled {{ opacity:.5; cursor:not-allowed; }}
.stDownloadButton > button {{ color:var(--sage); border-color:var(--sage); }}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {{
  background:linear-gradient(135deg,var(--primary),var(--primary-deep) 115%);
  color:#fff !important; border:none; box-shadow:var(--shadow-md); font-size:1.08rem; min-height:56px; }}
.stButton > button[kind="primary"]:hover:not(:disabled),
.stButton > button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{
  filter:brightness(1.06); transform:translateY(-1px); box-shadow:var(--shadow-lg); }}

/* Girdiler */
.stTextArea textarea, .stTextInput input {{ font-size:1.05rem !important;
  border:1.5px solid var(--border-strong) !important; border-radius:var(--radius-sm) !important; }}
.stTextArea textarea:focus, .stTextInput input:focus {{ border-color:var(--primary) !important; }}

/* Pills / segmented (kategori & giriş yöntemi) */
[data-testid="stPills"] button, [data-testid="stSegmentedControl"] button {{
  min-height:46px; font-size:1rem; border-radius:999px !important; }}

.ifsa {{ background:var(--surface-2); border:1px dashed var(--border-strong);
  border-radius:var(--radius-sm); color:var(--muted); font-size:.9rem; text-align:center;
  padding:.8rem; margin-top:1.6rem; }}

/* Geliştirici modu sekmeleri */
.dev-baslik {{ color:var(--primary-deep); font-weight:700; }}
.stTabs [data-baseweb="tab-list"] {{ gap:.25rem; flex-wrap:wrap; }}
.stTabs [data-baseweb="tab"] {{ font-family:'Lexend'; font-weight:600; }}

/* Pano */
.ozet {{ display:grid; grid-template-columns:repeat(3,1fr); gap:.6rem; margin:.3rem 0 1rem; }}
.ozet .kutu {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  padding:.85rem .9rem; box-shadow:var(--shadow-sm); animation:gir .35s ease both; }}
.ozet .deger {{ font-family:'Lexend'; font-weight:700; font-size:1.35rem; color:var(--primary-deep);
  line-height:1.2; overflow-wrap:anywhere; }}
.ozet .etiket {{ font-size:.86rem; color:var(--muted); margin-top:.15rem; }}
.gun-baslik {{ font-family:'Lexend'; font-weight:600; color:var(--primary); margin:1.1rem 0 .35rem; }}
/* Geniş Markdown tabloları (API belgesi) dar ekranda sayfayı değil yalnız kendini kaydırsın */
[data-testid="stMarkdownContainer"] table {{ display:block; max-width:100%; overflow-x:auto; }}

@keyframes gir {{ from {{opacity:0; transform:translateY(10px);}} to {{opacity:1; transform:none;}} }}
@media (prefers-reduced-motion: reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; }} }}
@media (max-width:640px) {{
  .adimlar {{ grid-template-columns:1fr; }}
  .karsilama h1 {{ font-size:1.75rem; }}
  .ozet {{ gap:.4rem; }}
  .ozet .kutu {{ padding:.6rem .55rem; }}
  .ozet .deger {{ font-size:1.02rem; }}
  .ozet .etiket {{ font-size:.78rem; }}
  .block-container {{ padding-left:.9rem; padding-right:.9rem; }}
  /* Yan yana düğmeler (gezinme, eylemler) mobilde alt alta yığılmasın */
  [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:.4rem !important; }}
  /* Streamlit dar ekranda her sütuna %100 en küçük genişlik verir; nowrap ile birleşince
     sütunlar ekran dışına taşar (375px'te "Panom"/"Yardım" görünmüyordu). Eşit paylaştır. */
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width:0 !important; width:auto !important; flex:1 1 0 !important; }}
  [data-testid="stHorizontalBlock"] .stButton > button {{
    font-size:.88rem; padding:.5rem .4rem; min-height:46px; }}
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Ortak parçalar
# ---------------------------------------------------------------------------
def ust_bar() -> None:
    """Sade üst bar: logo + geri düğmesi + gezinme."""
    st.markdown(
        '<div class="ustbar"><div class="logo">🧵</div>'
        '<div><div class="ad">Üretken Kadın</div>'
        '<div class="alt">Emeğin dijital sesi</div></div></div>',
        unsafe_allow_html=True)
    k = st.columns([1, 1, 1.15, 0.95])
    if k[0].button("← Geri", use_container_width=True, key="nav_geri",
                   help="Bir önceki ekrana dön"):
        geri()
    if k[1].button("✨ Yeni", use_container_width=True, key="nav_yeni",
                   help="Yeni bir ürün anlatın"):
        git("anlat")
    if k[2].button("🏠 Panom", use_container_width=True, key="nav_gec",
                   help="İçerikleriniz ve paylaşım takviminiz"):
        git("pano")
    if k[3].button("❓ Yardım", use_container_width=True, key="nav_yardim"):
        git("yardim")

    # Tarayıcının geri tuşunu uygulamanın kendi "← Geri" düğmesine bağlar.
    # (Streamlit popstate'te kendiliğinden yeniden çalışmaz; sayfayı yenilemek ise
    # oturumu — üretilen içerikleri — silerdi. Bu köprü oturumu korur.)
    components.html("""
    <script>
    (function(){
      const p = window.parent;
      if (!p || p.__uk_geri_koprusu) return;
      p.__uk_geri_koprusu = true;
      // ÖNEMLİ: dinleyiciyi ana pencerenin bağlamında üret. Bu bileşen iframe'i
      // her yeniden çizimde yok edildiğinden, iframe bağlamında tanımlanan bir
      // fonksiyon ilk geri'den sonra ölü kalır.
      const elle = new p.Function(
        "for (const b of document.querySelectorAll('button')) {" +
        "  if ((b.innerText || '').trim().indexOf('← Geri') === 0) { b.click(); break; }" +
        "}"
      );
      p.addEventListener('popstate', elle);
    })();
    </script>
    """, height=0)
    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)


def kalite_ipucu(ig: str, sh: str, kategori: str) -> None:
    """Kalite modelini sade, jargonsuz dille gösterir (varsa)."""
    model = kalite.model_al()
    if not model.mevcut():
        return
    thn = model.tahmin(f"{ig}\n{sh}", kategori)
    if thn["hazir"]:
        st.success("✅ İçeriğiniz **yayına hazır** görünüyor. Yine de bir okuyun, "
                   "beğenmezseniz değiştirin.")
    else:
        oneriler = thn["gerekceler"] or ["biraz daha ayrıntı ekleyebilirsiniz"]
        st.warning("💡 Küçük bir öneri — şunlara bakmak isteyebilirsiniz: "
                   + ", ".join(oneriler) + ".")


# ===========================================================================
# EKRAN: KARŞILAMA (ne iş yapıyoruz)
# ===========================================================================
def ekran_karsilama() -> None:
    st.markdown("""
    <div class="karsilama">
      <div class="amblem">🧵</div>
      <h1>El emeğinizi, <span class="slogan">arayanların bulacağı<br>bir dile</span> çeviriyoruz.</h1>
      <p class="aciklama">Ürününüzü kendi cümlelerinizle anlatın; biz sizin için
         Instagram gönderinizi ve satış sayfası yazınızı hazırlayalım.
         Yazı yazmayı ya da pazarlamayı bilmenize gerek yok.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="adimlar">
      <div class="adim"><div class="no">1</div><h4>Siz anlatın</h4>
        <p>Ürününüzü yazarak ya da sesli anlatın. Nasıl konuşuyorsanız öyle.</p></div>
      <div class="adim"><div class="no">2</div><h4>Biz hazırlayalım</h4>
        <p>Sizin sözlerinizden iki hazır metin çıkarırız — dakikalar içinde.</p></div>
      <div class="adim"><div class="no">3</div><h4>Siz onaylayın</h4>
        <p>Okur, beğendiğiniz gibi düzeltir ve paylaşırsınız. Söz hep sizde.</p></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="guven">🤍 Yapay zekâ yalnızca yardımcı olur; '
                'hikâyenizi <b>uydurmaz</b>, abartı yapmaz. Son kararı her zaman '
                'siz verirsiniz.</div>', unsafe_allow_html=True)

    if st.button("Hadi başlayalım  →", use_container_width=True, type="primary"):
        git("anlat")
    if st.button("Nasıl çalıştığını anlat", use_container_width=True):
        git("yardim")
    if st.button("📂 Kayıtlı planımla devam et", use_container_width=True,
                 help="Daha önce kaydettiğiniz içerik ve takvim dosyasını yükleyin"):
        git("pano")


# ===========================================================================
# EKRAN: ANLAT
# ===========================================================================
def ekran_anlat() -> None:
    ust_bar()
    st.markdown('<div class="ekran-baslik">Ne ürettiğinizi anlatın</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">Nasıl konuşuyorsanız öyle yazın. '
                'Malzeme, ne kadar sürdüğü, nasıl yaptığınız… aklınıza ne gelirse.</div>',
                unsafe_allow_html=True)

    # İlk kez? Örnekler
    with st.expander("İlk kez mi? Hazır bir örnekle deneyin"):
        for etiket, kat_etiket, metin in ORNEKLER:
            if st.button(etiket, use_container_width=True, key=f"or_{etiket}"):
                st.session_state.anlatim_metni = metin
                st.session_state.kategori_key = KATEGORILER[kat_etiket]
                st.rerun()

    yontem = st.segmented_control("Nasıl anlatmak istersiniz?",
                                  ["✍️ Yazarak", "🎙️ Konuşarak"],
                                  default="✍️ Yazarak", label_visibility="collapsed")

    if yontem == "🎙️ Konuşarak":
        st.caption("Konuşun, biz yazıya dökelim — kendi kelimeleriniz korunur.")
        with st.expander("Verileriniz nasıl işlenir? (KVKK)"):
            st.markdown(kvkk.SES_AYDINLATMA)
        st.session_state.ses_rizasi = st.checkbox(kvkk.SES_RIZA_ETIKETI,
                                                  value=st.session_state.ses_rizasi)
        ses = st.audio_input("Mikrofona basın ve anlatın")
        if ses is not None and not st.session_state.ses_rizasi:
            st.info("Devam etmek için yukarıdaki onay kutusunu işaretleyin.")
        if ses is not None and st.session_state.ses_rizasi and st.button(
                "Sesimi yazıya dök", use_container_width=True):
            with st.spinner("Ses kaydınız yazıya dökülüyor…"):
                try:
                    metin = uret.sesten_metne(ses.getvalue(), "audio/wav")
                    if metin:
                        st.session_state.anlatim_metni = metin
                        st.rerun()
                    else:
                        st.warning("Ses anlaşılamadı, tekrar dener misiniz?")
                except Exception as e:
                    st.error(f"Ses çevrilemedi: {e}")

    st.text_area("Ürün anlatımı", height=170, key="anlatim_metni",
                 placeholder="Örnek: El örgüsü bebek battaniyesi yapıyorum. "
                             "Organik pamuk ipliği kullanıyorum, tamamen elde "
                             "örüyorum. Bir tanesi üç günümü alıyor…",
                 label_visibility="collapsed")
    st.caption("🔒 " + kvkk.METIN_AYDINLATMA)

    st.markdown("**Bu ne tür bir ürün?**")
    etiketler = list(KATEGORILER.keys())
    tersi = {v: k for k, v in KATEGORILER.items()}
    secili_etiket = tersi.get(st.session_state.kategori_key, etiketler[0])
    secim = st.pills("Kategori", etiketler, default=secili_etiket,
                     label_visibility="collapsed")
    if secim:
        st.session_state.kategori_key = KATEGORILER[secim]

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    if st.button("İçeriğimi hazırla  ✨", use_container_width=True, type="primary"):
        anlatim = st.session_state.anlatim_metni
        if not anlatim.strip() or len(anlatim.split()) < 5:
            st.warning("Ürününüzü birkaç cümleyle anlatın (en az bir iki cümle).")
        else:
            with st.spinner("İçeriğiniz hazırlanıyor…"):
                try:
                    sonuc = uret.icerik_uret(
                        anlatim=anlatim, kategori=st.session_state.kategori_key,
                        ton="sıcak ve samimi", teknik="few_shot", ozenli=ozenli,
                        uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                    an = takvim.simdi()          # sunucu UTC olsa da Türkiye saati
                    kayit_id = takvim.yeni_id()
                    st.session_state.sonuc = sonuc
                    st.session_state.ozenli_istendi = ozenli
                    st.session_state.aktif_id = kayit_id
                    st.session_state.gecmis.insert(0, {
                        "id": kayit_id, "tarih": an.date().isoformat(),
                        "saat": an.strftime("%H:%M"),
                        "kategori": st.session_state.kategori_key, "anlatim": anlatim,
                        "instagram": sonuc.instagram, "shopier": sonuc.shopier,
                        "ekler": {}})
                    git("sonuc")
                except Exception as e:
                    st.error(f"İçerik hazırlanamadı: {e}")


# ===========================================================================
# Sonuç ekranı yardımcıları: ek formatlar ve paylaşım zamanı
# ===========================================================================
EK_ETIKETLER = {"story": "🟣 Hikâye", "whatsapp": "💬 WhatsApp", "hashtag": "#️⃣ Hashtag",
                "reels": "🎬 Video planı", "foto": "📸 Fotoğraf"}
EK_BASLIKLAR = {"story": "Instagram hikâyesi (3 kare)", "whatsapp": "WhatsApp metinleri",
                "hashtag": "Hashtag seti", "reels": "Video çekim planı",
                "foto": "Fotoğraf önerileri"}


def kayit_bul(kayit_id: str | None) -> dict | None:
    return next((k for k in st.session_state.gecmis if k.get("id") == kayit_id), None)


def ek_uret(bicim: str, kayit: dict) -> None:
    """Seçilen ek formatı üretir ve içeriğin kaydına ekler (panoda ve kayıt dosyasında da görünür)."""
    anlatim, kategori = kayit["anlatim"], kayit["kategori"]
    uslup = st.session_state.uslup_ornekleri or None
    with st.spinner("Hazırlanıyor…"):
        try:
            if bicim == "reels":
                metin = uret.reels_uret(anlatim=anlatim, kategori=kategori, ozenli=ozenli,
                                        uslup_ornekleri=uslup)
            elif bicim == "foto":
                metin = uret.foto_rehberi_uret(anlatim=anlatim, kategori=kategori,
                                               ozenli=ozenli)
            else:
                metin = uret.ek_format_uret(anlatim=anlatim, kategori=kategori, bicim=bicim,
                                            uslup_ornekleri=uslup, ozenli=ozenli)
            kayit.setdefault("ekler", {})[bicim] = metin
        except Exception as e:
            st.error(f"Hazırlanamadı: {e}")


def paylasim_zamani(kayit: dict) -> None:
    """Bu içeriği takvime ekler; telefona .ics dosyasıyla hatırlatma olarak aktarılır."""
    plan, aid = st.session_state.plan, kayit["id"]
    st.markdown('<div class="kart-baslik" style="margin-top:1.4rem">📅 Ne zaman '
                'paylaşacaksınız?</div>', unsafe_allow_html=True)
    st.caption(f"Seçtiğiniz saatten {takvim.HATIRLATMA_DK} dakika önce telefonunuz "
               "hatırlatsın; paylaşacağınız metin hatırlatmanın içinde hazır olur.")
    oneri = (takvim.sonraki_zamanlar(takvim.VARSAYILAN_GUNLER, takvim.VARSAYILAN_SAAT, 1,
                                     dolu_gunler=takvim.dolu_gunler(plan))
             or [takvim.simdi() + timedelta(days=1)])[0]
    z1, z2 = st.columns(2)
    gun = z1.date_input("Gün", value=oneri.date(), min_value=takvim.simdi().date(),
                        format="DD.MM.YYYY", key=f"pz_gun_{aid}")
    saat = z2.time_input("Saat", value=oneri.time(), step=900, key=f"pz_saat_{aid}")
    kanal = st.selectbox("Nerede paylaşacaksınız?", list(takvim.KANALLAR),
                         format_func=takvim.KANALLAR.get, key=f"pz_kanal_{aid}")
    if st.button("📅  Takvimime ekle", use_container_width=True, key=f"pz_ekle_{aid}"):
        zaman = takvim.zaman_birlestir(gun, saat)
        if zaman < takvim.simdi():
            st.warning("Geçmiş bir saat seçtiniz; lütfen ileri bir saat seçin.")
        else:
            # Hikâye/WhatsApp metni hazırlandıysa hatırlatmaya o konur, yoksa Instagram metni.
            metin = ({"instagram": kayit["instagram"], "shopier": kayit["shopier"]}.get(kanal)
                     or kayit.get("ekler", {}).get(kanal) or kayit["instagram"])
            plan.append(takvim.PlanOgesi(zaman=zaman.isoformat(), kanal=kanal,
                                         baslik=takvim.baslik_uret(kayit["anlatim"]),
                                         metin=metin, icerik_id=aid))
            st.success(f"Eklendi: {takvim.tarih_etiketi(zaman)}, {zaman:%H:%M}")

    bunlar = [o for o in plan if o.icerik_id == aid and not o.tamam]
    if bunlar:
        st.markdown("  \n".join(
            f"• {takvim.tarih_etiketi(o.zaman_dt())}, {o.zaman_dt():%H:%M} — "
            f"{takvim.KANALLAR.get(o.kanal, o.kanal)}" for o in takvim.sirali(bunlar)))
        st.download_button("📲  Telefonumun takvimine ekle", data=takvim.ics_olustur(bunlar),
                           file_name="uretken_kadin_paylasim.ics", mime="text/calendar",
                           use_container_width=True, key=f"pz_ics_{aid}")
        st.caption("İnen dosyaya dokunun; telefonunuz takvime eklemeyi önerir. "
                   "Tüm planınız için: 🏠 Panom.")


# ===========================================================================
# EKRAN: SONUÇ
# ===========================================================================
def ekran_sonuc() -> None:
    ust_bar()
    sonuc = st.session_state.sonuc
    if sonuc is None:
        git("anlat"); return
    kayit = kayit_bul(st.session_state.aktif_id)
    if kayit is None:
        # Önceki sürümden kalan oturum: içeriği bir kayda bağla ki takvim/ekler çalışsın.
        an = takvim.simdi()
        kayit = {"id": takvim.yeni_id(), "tarih": an.date().isoformat(),
                 "saat": an.strftime("%H:%M"), "kategori": st.session_state.kategori_key,
                 "anlatim": st.session_state.anlatim_metni, "instagram": sonuc.instagram,
                 "shopier": sonuc.shopier, "ekler": {}}
        st.session_state.gecmis.insert(0, kayit)
        st.session_state.aktif_id = kayit["id"]
    kategori = kayit.get("kategori") or st.session_state.kategori_key

    st.markdown('<div class="ekran-baslik">İşte içerikleriniz 🎉</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">Beğenmediğiniz yeri doğrudan '
                'düzeltebilirsiniz. Hazır olunca kopyalayıp paylaşın.</div>',
                unsafe_allow_html=True)
    # Özenli yazım istendi ama o model yoğun/yavaş olduğu için hızlı modele geçildiyse söyle.
    if (st.session_state.get("ozenli_istendi") and sonuc.model
            and sonuc.model != uret.MODEL_OZENLI):
        st.info("Özenli yazım şu an yoğun olduğu için içeriğiniz hızlı yöntemle "
                "hazırlandı. İsterseniz biraz sonra tekrar deneyebilirsiniz.")

    st.markdown('<div class="kart-baslik">📱 Instagram gönderiniz</div>',
                unsafe_allow_html=True)
    ig = st.text_area("Instagram", value=sonuc.instagram, height=140,
                      label_visibility="collapsed")
    with st.expander("📋 Kopyalamak için aç"):
        st.code(ig, language=None)

    st.markdown('<div class="kart-baslik">🛍️ Satış sayfası (Shopier) açıklamanız</div>',
                unsafe_allow_html=True)
    sh = st.text_area("Shopier", value=sonuc.shopier, height=160,
                      label_visibility="collapsed")
    with st.expander("📋 Kopyalamak için aç"):
        st.code(sh, language=None)

    kalite_ipucu(ig, sh, kategori)
    # Düzeltmeler panoya, takvime ve kayıt dosyasına da yansısın.
    kayit["instagram"], kayit["shopier"] = ig, sh

    b1, b2 = st.columns(2)
    with b1:
        st.download_button("⬇  İkisini de indir",
                           data=f"INSTAGRAM\n{ig}\n\nSHOPIER\n{sh}",
                           file_name="uretken_kadin_icerik.txt",
                           use_container_width=True)
    with b2:
        if st.button("＋  Yeni ürün anlat", use_container_width=True, type="primary"):
            git("anlat")

    paylasim_zamani(kayit)

    # İsteğe bağlı ekstralar — aynı ürün için başka yerlerde kullanılacak metinler
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    ekler = kayit.setdefault("ekler", {})
    with st.expander("✨ Diğer formatlar: hikâye, WhatsApp, hashtag, video, fotoğraf",
                     expanded=bool(ekler)):
        bicimler = list(EK_ETIKETLER.items())
        for satir in (bicimler[:3], bicimler[3:]):
            for kol, (bicim, etiket) in zip(st.columns(len(satir)), satir):
                if kol.button(etiket, use_container_width=True, key=f"ek_{bicim}"):
                    ek_uret(bicim, kayit)
        for bicim in EK_ETIKETLER:
            if not ekler.get(bicim):
                continue
            st.markdown(f'<div class="kart-baslik" style="margin-top:1rem">'
                        f'{EK_BASLIKLAR[bicim]}</div>', unsafe_allow_html=True)
            st.markdown(ekler[bicim])
            if bicim == "hashtag":      # son satır: gönderi için seçilmiş 5 hashtag
                satirlar = [s.strip() for s in ekler[bicim].splitlines()
                            if s.strip().startswith("#")]
                if satirlar:
                    st.code(satirlar[-1], language=None)

    st.markdown('<div class="ifsa">Bu içerik yapay zekâ yardımıyla hazırlandı · '
                'paylaşmadan önce okuyun — son karar sizindir.</div>',
                unsafe_allow_html=True)


# ===========================================================================
# EKRAN: PANOM — özet, paylaşım takvimi, içerikler, kaydet / yükle
# ===========================================================================
def _plan_tamam(oge_id: str) -> None:
    for o in st.session_state.plan:
        if o.id == oge_id:
            o.tamam = st.session_state[f"tamam_{oge_id}"]


def _plan_sil(oge_id: str) -> None:
    st.session_state.plan = [o for o in st.session_state.plan if o.id != oge_id]


def _plan_ertele(oge_id: str) -> None:
    """Zamanı geçen paylaşımı aynı saatle yarına alır."""
    yarin = takvim.simdi().date() + timedelta(days=1)
    for o in st.session_state.plan:
        if o.id == oge_id:
            o.zaman = takvim.zaman_birlestir(yarin, o.zaman_dt().time()).isoformat()


def _icerik_sil(kayit_id: str) -> None:
    st.session_state.gecmis = [k for k in st.session_state.gecmis if k.get("id") != kayit_id]
    st.session_state.plan = [o for o in st.session_state.plan if o.icerik_id != kayit_id]
    if st.session_state.aktif_id == kayit_id:
        st.session_state.sonuc = st.session_state.aktif_id = None


def _icerik_ac(kayit: dict) -> None:
    st.session_state.sonuc = uret.Icerik(instagram=kayit["instagram"], shopier=kayit["shopier"])
    st.session_state.aktif_id = kayit["id"]
    st.session_state.ozenli_istendi = False
    st.session_state.anlatim_metni = kayit["anlatim"]
    if kayit.get("kategori") in prompts.KATEGORI_KELIMELERI:
        st.session_state.kategori_key = kayit["kategori"]
    git("sonuc")


def _plan_satiri(o: takvim.PlanOgesi, gecen: bool = False) -> None:
    z = o.zaman_dt()
    isaret = "✅ " if o.tamam else ("⏰ " if gecen else "")
    ne_zaman = takvim.kisa_etiket(z) if (gecen or o.tamam) else f"{z:%H:%M}"
    with st.expander(f"{isaret}{ne_zaman} · {takvim.KANALLAR.get(o.kanal, o.kanal)} · "
                     f"{o.baslik}"):
        if o.metin:
            st.code(o.metin, language=None, wrap_lines=True)
        k1, k2, k3 = st.columns([1.3, 1, 0.8])
        k1.checkbox("Paylaştım", value=o.tamam, key=f"tamam_{o.id}",
                    on_change=_plan_tamam, args=(o.id,))
        if gecen:
            k2.button("Yarına al", key=f"ertele_{o.id}", on_click=_plan_ertele,
                      args=(o.id,), use_container_width=True)
        k3.button("Sil", key=f"sil_{o.id}", on_click=_plan_sil, args=(o.id,),
                  use_container_width=True)


def _pano_takvim(an) -> None:
    gecmis, plan = st.session_state.gecmis, st.session_state.plan
    bekleyen = takvim.planlanmamis(gecmis, plan)
    if bekleyen:
        st.markdown(f"**{len(bekleyen)} içeriğiniz henüz takvimde değil.** "
                    "Hangi günler paylaşmak istersiniz?")
        gunler = st.pills("Günler", takvim.GUN_KISA, selection_mode="multi",
                          default=[takvim.GUN_KISA[i] for i in takvim.VARSAYILAN_GUNLER],
                          label_visibility="collapsed", key="oner_gunler")
        saat = st.time_input("Saat", value=takvim.VARSAYILAN_SAAT, step=900, key="oner_saat")
        st.caption("20:00 yalnızca bir başlangıç önerisidir. Takipçilerinizin en çok ne "
                   "zaman çevrimiçi olduğunu Instagram profesyonel hesabınızın "
                   "istatistiklerinden görüp saati ona göre değiştirebilirsiniz.")
        if st.button(f"✨  {len(bekleyen)} içeriği takvime yerleştir", type="primary",
                     use_container_width=True, key="oner_btn"):
            if not gunler:
                st.warning("En az bir gün seçin.")
            else:
                yeni = takvim.plan_oner(gecmis, plan,
                                        [takvim.GUN_KISA.index(g) for g in gunler], saat)
                st.session_state.plan = plan + yeni
                st.session_state.pano_mesaj = f"{len(yeni)} paylaşım takvime eklendi."
                st.rerun()
        st.divider()

    if not plan:
        st.info("Takviminiz boş. İçeriklerinizi yukarıdan ya da sonuç ekranından "
                "takvime ekleyebilirsiniz.")
        return
    gruplar = takvim.ayir(plan, an)
    if gruplar["yaklasan"]:
        st.download_button("📲  Yaklaşan paylaşımları telefon takvimime ekle",
                           data=takvim.ics_olustur(gruplar["yaklasan"]),
                           file_name="uretken_kadin_takvim.ics", mime="text/calendar",
                           use_container_width=True, key="ics_hepsi")
        st.caption(f"İnen dosyaya dokunun; telefonunuz takvime eklemeyi önerir ve her "
                   f"paylaşımdan {takvim.HATIRLATMA_DK} dakika önce hatırlatır. Google "
                   "Takvim'e bilgisayardan Ayarlar → İçe aktar ile de ekleyebilirsiniz.")
        for _, ogeler in takvim.gune_gore(gruplar["yaklasan"]):
            st.markdown(f'<div class="gun-baslik">'
                        f'{html.escape(takvim.tarih_etiketi(ogeler[0].zaman_dt()))}</div>',
                        unsafe_allow_html=True)
            for o in ogeler:
                _plan_satiri(o)
    else:
        st.info("Yaklaşan paylaşım yok.")
    if gruplar["gecen"]:
        st.markdown('<div class="gun-baslik">⏰ Zamanı geçenler</div>', unsafe_allow_html=True)
        for o in gruplar["gecen"]:
            _plan_satiri(o, gecen=True)
    if gruplar["tamam"] and st.toggle(f"✅ Paylaştıklarınızı göster ({len(gruplar['tamam'])})",
                                      key="tamam_goster"):
        for o in reversed(gruplar["tamam"]):
            _plan_satiri(o)


def _pano_icerikler() -> None:
    gecmis, plan = st.session_state.gecmis, st.session_state.plan
    if not gecmis:
        st.info("Bu oturumda hazırlanmış içerik yok.")
        return
    for kayit in gecmis:
        planli = takvim.sirali([o for o in plan if o.icerik_id == kayit["id"]])
        durum = f"📅 {takvim.kisa_etiket(planli[0].zaman_dt())}" if planli else "planlanmadı"
        with st.expander(f"{takvim.baslik_uret(kayit['anlatim'])} · {durum}"):
            st.markdown("**📱 Instagram**")
            st.write(kayit["instagram"])
            st.markdown("**🛍️ Shopier**")
            st.write(kayit["shopier"])
            hazir = [EK_BASLIKLAR[b] for b in kayit.get("ekler", {}) if b in EK_BASLIKLAR]
            if hazir:
                st.caption("Hazır ek formatlar: " + ", ".join(hazir))
            a1, a2 = st.columns([1.6, 1])
            if a1.button("✏️ Aç ve düzenle", key=f"ac_{kayit['id']}", use_container_width=True):
                _icerik_ac(kayit)
            a2.button("Sil", key=f"icsil_{kayit['id']}", on_click=_icerik_sil,
                      args=(kayit["id"],), use_container_width=True)


def _plan_kaydet() -> None:
    st.caption("🔒 " + kvkk.KAYIT_ACIKLAMA)
    uslup_dahil = bool(st.session_state.uslup_ornekleri) and st.checkbox(
        "Ton profilimi de kaydet", value=True, key="kayit_uslup")
    veri = takvim.disa_aktar(st.session_state.gecmis, st.session_state.plan,
                             st.session_state.uslup_ornekleri if uslup_dahil else None)
    st.download_button("💾  Planımı kaydet", data=veri.encode("utf-8"),
                       file_name=f"uretken_kadin_planim_{takvim.simdi():%Y-%m-%d}.json",
                       mime="application/json", use_container_width=True, key="kayit_indir")


def _plan_yukle() -> None:
    dosya = st.file_uploader("Kayıtlı plan dosyanızı seçin (.json)", type=["json"],
                             key="kayit_dosya")
    if dosya is not None and st.button("📂  Yükle", use_container_width=True,
                                       key="kayit_yukle"):
        try:
            icerikler, plan, uslup, uyarilar = takvim.ice_aktar(dosya.getvalue())
        except ValueError as e:
            st.error(str(e))
            return
        st.session_state.gecmis, n_icerik = takvim.birlestir(st.session_state.gecmis, icerikler)
        st.session_state.plan, n_plan = takvim.birlestir(st.session_state.plan, plan)
        if uslup and not st.session_state.uslup_ornekleri:
            st.session_state.uslup_ornekleri = uslup
        st.session_state.pano_mesaj = " ".join(
            [f"Yüklendi: {n_icerik} içerik, {n_plan} paylaşım."] + uyarilar)
        st.rerun()


def ekran_pano() -> None:
    ust_bar()
    gecmis, plan = st.session_state.gecmis, st.session_state.plan
    an = takvim.simdi()
    st.markdown('<div class="ekran-baslik">Panonuz</div>', unsafe_allow_html=True)
    if st.session_state.pano_mesaj:
        st.success(st.session_state.pano_mesaj)
        st.session_state.pano_mesaj = None

    if not gecmis and not plan:
        st.markdown('<div class="bos"><div class="ik">🏠</div><p>Henüz içerik yok.<br>'
                    'İlk ürününüzü anlatın ya da daha önce kaydettiğiniz planı '
                    'yükleyin.</p></div>', unsafe_allow_html=True)
        if st.button("İlk içeriğimi hazırlayayım  →", use_container_width=True, type="primary"):
            git("anlat")
        st.markdown("**📂 Kayıtlı planımı yükle**")
        _plan_yukle()
        return

    st.markdown('<div class="ekran-alt">İçerikleriniz ve paylaşım takviminiz tek yerde. '
                'Sayfayı kapatınca sıfırlanır — saklamak için “Kaydet / yükle”.</div>',
                unsafe_allow_html=True)
    sira = takvim.siradaki(plan, an)
    paylasilan = sum(o.tamam for o in plan)
    kutular = [(len(gecmis), "hazır içerik"),
               (len(takvim.onumuzdeki_gunler(plan, 7, an)), "paylaşım bu hafta"),
               (takvim.kisa_etiket(sira.zaman_dt()) if sira else "—", "sıradaki paylaşım")]
    st.markdown('<div class="ozet">' + "".join(
        f'<div class="kutu"><div class="deger">{html.escape(str(d))}</div>'
        f'<div class="etiket">{e}</div></div>' for d, e in kutular) + '</div>',
        unsafe_allow_html=True)
    if plan:
        st.progress(paylasilan / len(plan), text=f"Paylaştıklarınız: {paylasilan}/{len(plan)}")

    t_takvim, t_icerik, t_kayit = st.tabs(["📅 Takvimim", "📝 İçeriklerim", "💾 Kaydet / yükle"])
    with t_takvim:
        _pano_takvim(an)
    with t_icerik:
        _pano_icerikler()
    with t_kayit:
        _plan_kaydet()
        st.divider()
        _plan_yukle()


# ===========================================================================
# EKRAN: TON PROFİLİM (isteğe bağlı)
# ===========================================================================
def ekran_ton() -> None:
    ust_bar()
    st.markdown('<div class="ekran-baslik">Sizin gibi yazmasını öğretin</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">İsteğe bağlı. Daha önce yazdığınız birkaç '
                'paylaşımı yapıştırın; içerikler sizin tarzınıza daha çok benzesin. '
                'Metinleriniz kopyalanmaz, yalnızca üslubunuz örnek alınır.</div>',
                unsafe_allow_html=True)
    with st.form("ton_formu"):
        y1 = st.text_area("Örnek 1", height=80,
                          placeholder="Örn: Bugün de tezgah başındayım, bu rengi çok sevdim…")
        y2 = st.text_area("Örnek 2 (isteğe bağlı)", height=80)
        y3 = st.text_area("Örnek 3 (isteğe bağlı)", height=80)
        if st.form_submit_button("Kaydet", type="primary"):
            yeni = [m for m in (y1, y2, y3) if m and m.strip()]
            if not yeni:
                st.warning("En az bir metin yapıştırın.")
            else:
                st.session_state.uslup_ornekleri = yeni
                st.success(f"Kaydedildi ({len(yeni)} örnek). Bundan sonraki içerikler "
                           "sizin tarzınızda yazılacak.")
    if st.session_state.uslup_ornekleri and st.button("Profilimi sil"):
        st.session_state.uslup_ornekleri = []
        st.rerun()


# ===========================================================================
# EKRAN: YARDIM / NASIL ÇALIŞIR + ETİK (sade)
# ===========================================================================
def ekran_yardim() -> None:
    ust_bar()
    st.markdown('<div class="ekran-baslik">Nasıl çalışır?</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="kart"><div class="kart-baslik">1 · Siz anlatın</div>
      <p>Ürününüzü kendi cümlelerinizle yazın ya da sesli anlatın. Teknik bilgi gerekmez.</p></div>
    <div class="kart"><div class="kart-baslik">2 · Biz iki metin hazırlayalım</div>
      <p><b>Instagram gönderisi</b> — kısa, dikkat çeken, hikâyenizi anlatan.<br>
         <b>Shopier açıklaması</b> — insanlar aradığında bulunan, bilgi veren.</p></div>
    <div class="kart"><div class="kart-baslik">3 · Siz onaylayın</div>
      <p>Metinleri okur, dilediğiniz yeri değiştirir, kopyalar ve paylaşırsınız.</p></div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ekran-baslik" style="font-size:1.3rem;margin-top:1.2rem">'
                'Söz veriyoruz</div>', unsafe_allow_html=True)
    for baslik, aciklama in [
        ("🤍 Hikâyeniz sizin", "Yapay zekâ hikâye uydurmaz; sizin anlattığınız "
         "somut şeyleri kullanır."),
        ("🚫 Abartı yok", "“Mucize”, “garanti”, “en iyi” gibi ispatsız sözler "
         "yazılmaz; gıdada sağlık iddiası kurulmaz."),
        ("✋ Son karar sizde", "Onayınız olmadan hiçbir içerik kullanılmaz."),
        ("🔒 Verileriniz güvende", "Anlatımınız yalnızca içerik hazırlamak için "
         "kullanılır, kalıcı olarak saklanmaz (KVKK)."),
    ]:
        st.markdown(f'<div class="kart"><div class="kart-baslik">{baslik}</div>'
                    f'<p>{aciklama}</p></div>', unsafe_allow_html=True)

    with st.expander("KVKK — kişisel verileriniz hakkında ayrıntı"):
        for b, a in kvkk.POLITIKA_MADDELERI:
            st.markdown(f"**{b}**  \n{a}")

    if st.button("Anladım, başlayalım  →", use_container_width=True, type="primary"):
        git("anlat")


# ===========================================================================
# EKRAN: FİRMALAR İÇİN API — belgeler API.md'den okunur (tek kaynak)
# ===========================================================================
API_SEKMELERI = [("🚀 Hızlı başlangıç", ["1", "2"]), ("📚 Uç noktalar", ["3"]),
                 ("⏱️ Kota ve hatalar", ["4", "5", "7"]), ("🛡️ KVKK ve sorumluluklar", ["6"])]


@st.cache_data(show_spinner=False)
def api_rehberi(yol: str, adres: str, _degisme: float) -> dict[str, tuple[str, str]]:
    """
    API.md'nin iş ortağı kısmını {"1": (başlık, gövde), ...} olarak döndürür.
    "# İşletim rehberi" sonrası (anahtar yönetimi, yayına alma) firmalara gösterilmez.
    _degisme: dosya değişince önbellek tazelensin diye değişiklik zamanı.
    """
    with open(yol, encoding="utf-8") as f:
        ortak = f.read().split("\n# İşletim rehberi")[0]
    if adres:
        ortak = ortak.replace("https://API-ADRESI", adres.rstrip("/"))
    bolumler = {}
    for parca in re.split(r"\n(?=## )", ortak)[1:]:
        baslik, _, govde = parca.partition("\n")
        no = re.match(r"##\s*(\d+)\.\s*(.*)", baslik)
        if no:
            bolumler[no.group(1)] = (no.group(2).strip(),
                                     re.sub(r"(\n\s*---\s*)+$", "", govde.strip()).strip())
    return bolumler


def ekran_api() -> None:
    ust_bar()
    adres = os.getenv("API_ADRESI", "").strip()
    iletisim = os.getenv("API_ILETISIM", "").strip()
    st.markdown('<div class="ekran-baslik">🔌 Firmalar için API</div>', unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">E-ticaret platformları, kooperatifler ve girişimcilik '
                'programları Üretken Kadın\'ın içerik motorunu kendi sistemlerine bağlayabilir — '
                'aynı etik kurallar, aynı insan onayı ilkesiyle.</div>', unsafe_allow_html=True)
    yol = os.path.join(KOK, "API.md")
    try:
        bolumler = api_rehberi(yol, adres, os.path.getmtime(yol))
    except OSError:
        st.warning("API belgesi (API.md) bulunamadı.")
        return

    uc_nokta = len(re.findall(r"^\| `(?:GET|POST)`", bolumler.get("3", ("", ""))[1], re.M))
    kutular = [(uc_nokta, "uç nokta"), ("REST", "JSON · OpenAPI"),
               ("0", "sunucuda saklanan anlatım")]
    st.markdown('<div class="ozet">' + "".join(
        f'<div class="kutu"><div class="deger">{d}</div><div class="etiket">{e}</div></div>'
        for d, e in kutular) + '</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="adimlar">
      <div class="adim"><div class="no">1</div><h4>Başvurun</h4>
        <p>Kurumunuzu ve kullanım amacınızı iletin; size özel API anahtarı ve günlük kota tanımlanır.</p></div>
      <div class="adim"><div class="no">2</div><h4>Deneyin</h4>
        <p>Canlı belgede (/docs) anahtarınızla istekleri deneyin, sonra kendi sunucunuza ekleyin.</p></div>
      <div class="adim"><div class="no">3</div><h4>Üreticilerinize açın</h4>
        <p>Metni üreticiye onaylatarak yayımlayın; sesli anlatım için açık rıza alın.</p></div>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"🔑 **API anahtarı başvurusu:** {iletisim}" if iletisim
            else "🔑 API anahtarı almak için Üretken Kadın ekibiyle iletişime geçin.")
    if adres:
        st.link_button("📖 Canlı API belgesini aç (/docs)", f"{adres.rstrip('/')}/docs",
                       use_container_width=True)

    if not bolumler:
        st.warning("API belgesi okunamadı.")
        return
    sekmeler = st.tabs([ad for ad, _ in API_SEKMELERI])
    for sekme, (_, numaralar) in zip(sekmeler, API_SEKMELERI):
        with sekme:
            for no in numaralar:
                if no in bolumler:
                    baslik, govde = bolumler[no]
                    st.markdown(f"#### {baslik}")
                    st.markdown(govde)


# ===========================================================================
# GELİŞTİRİCİ / RAPOR MODU (capstone kanıtı — kullanıcıdan gizli)
# ===========================================================================
def _olcumler(ig, sh, kategori):
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    return (uret.seo_kapsami(f"{ig} {sh}", kelimeler), len(kelimeler),
            uret.klise_sayisi(f"{ig} {sh}"), uret.kanal_benzerligi(ig, sh))


def ekran_gelistirici() -> None:
    ust_bar()
    st.markdown('<div class="ekran-baslik dev-baslik">🔧 Geliştirici / Rapor</div>',
                unsafe_allow_html=True)
    st.caption("Bu bölüm capstone raporu içindir; son kullanıcı akışında görünmez. "
               "Kenar çubuğundaki geçişten kapatabilirsiniz.")
    t_karsi, t_toplu, t_panel = st.tabs(
        ["Prompt karşılaştırma", "Toplu üretim", "Test paneli & model"])

    TEKNIK = {"few_shot": "few-shot", "zero_shot": "zero-shot",
              "chain_of_thought": "chain-of-thought"}

    # --- Karşılaştır ---
    with t_karsi:
        k_anlatim = st.text_area("Anlatım", height=100, value=ORNEKLER[0][2])
        k_kat = st.selectbox("Kategori", list(prompts.KATEGORI_KELIMELERI.keys()))
        if st.button("Üç tekniği de çalıştır"):
            if len(k_anlatim.split()) < 5:
                st.warning("Daha uzun bir anlatım girin.")
            else:
                sonuclar = {}
                pr = st.progress(0.0)
                for i, tkn in enumerate(TEKNIK, 1):
                    pr.progress(i / 3, text=f"{tkn} ({i}/3)")
                    try:
                        sonuclar[tkn] = uret.icerik_uret(anlatim=k_anlatim,
                                                         kategori=k_kat, teknik=tkn)
                    except Exception as e:
                        sonuclar[tkn] = e
                pr.empty()
                st.session_state.karsilastirma = (sonuclar, k_kat)
        if st.session_state.karsilastirma:
            sonuclar, kk = st.session_state.karsilastirma
            for kol, (tkn, s) in zip(st.columns(3), sonuclar.items()):
                with kol:
                    st.markdown(f"**{TEKNIK[tkn]}**")
                    if isinstance(s, Exception):
                        st.error(str(s)); continue
                    st.caption("Instagram"); st.write(s.instagram)
                    st.caption("Shopier"); st.write(s.shopier)
                    kap, top, kl, bz = _olcumler(s.instagram, s.shopier, kk)
                    st.caption(f"SEO {kap}/{top} · klişe {kl} · benzerlik {bz:.2f}")

    # --- Toplu ---
    with t_toplu:
        st.caption("CSV yükleyin (anlatim sütunu zorunlu, kategori isteğe bağlı).")
        ornek_csv = "anlatim,kategori\nEl örgüsü bebek battaniyesi…,Tekstil / El sanatı\n"
        st.download_button("Örnek şablon indir", data=ornek_csv, file_name="sablon.csv")
        yuk = st.file_uploader("CSV", type=["csv"])
        t_kat = st.selectbox("Varsayılan kategori",
                             list(prompts.KATEGORI_KELIMELERI.keys()), key="tk")
        if yuk is not None:
            try:
                satirlar = list(csv.DictReader(io.StringIO(
                    yuk.getvalue().decode("utf-8-sig"))))
            except Exception as e:
                satirlar = []; st.error(f"Okunamadı: {e}")
            if satirlar and "anlatim" not in satirlar[0]:
                st.error("'anlatim' sütunu yok.")
            elif satirlar and st.button(f"{len(satirlar)} ürün için üret"):
                cikti, pr = [], st.progress(0.0)
                for i, s in enumerate(satirlar, 1):
                    pr.progress(i / len(satirlar), text=f"{i}/{len(satirlar)}")
                    kat = s.get("kategori") or t_kat
                    try:
                        r = uret.icerik_uret(anlatim=s["anlatim"], kategori=kat)
                        cikti.append({"anlatim": s["anlatim"], "kategori": kat,
                                      "instagram": r.instagram, "shopier": r.shopier,
                                      "durum": "✅"})
                    except Exception as e:
                        cikti.append({"anlatim": s["anlatim"], "kategori": kat,
                                      "instagram": "", "shopier": "",
                                      "durum": f"⚠️ {str(e)[:50]}"})
                pr.empty(); st.session_state.toplu_sonuc = cikti
        if st.session_state.toplu_sonuc:
            ba = sum(1 for s in st.session_state.toplu_sonuc if s["durum"] == "✅")
            st.markdown(f"**{ba}/{len(st.session_state.toplu_sonuc)} başarılı**")
            st.dataframe(st.session_state.toplu_sonuc, use_container_width=True,
                         hide_index=True)

    # --- Panel ---
    with t_panel:
        dosyalar = sorted(glob.glob(os.path.join(KOK, "ciktilar", "*.csv")), reverse=True)
        if not dosyalar:
            st.info("Toplu test yok. `python src/toplu_test.py` çalıştırın.")
        else:
            sec = st.selectbox("Sonuç dosyası", [os.path.basename(d) for d in dosyalar])
            with open(os.path.join(KOK, "ciktilar", sec), encoding="utf-8-sig") as f:
                rows = [s for s in csv.DictReader(f) if not s.get("hata")]
            if rows:
                sayi = lambda k: [float(s.get(k) or 0) for s in rows]
                c1, c2, c3 = st.columns(3)
                c1.metric("Başarılı üretim", len(rows))
                c2.metric("SEO kapsamı",
                          f"%{100*sum(sayi('seo_kapsam'))/max(sum(sayi('seo_toplam')),1):.0f}")
                c3.metric("Toplam klişe", f"{sum(sayi('klise')):.0f}")
                st.dataframe(rows, use_container_width=True, hide_index=True)
        st.divider()
        st.markdown("**İçerik kalite modeli** (prototip veri)")
        mj = os.path.join(KOK, "ciktilar", "model", "metrikler.json")
        if os.path.exists(mj):
            m = json.load(open(mj, encoding="utf-8"))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Doğruluk", f"%{m['dogruluk']*100:.0f}")
            c2.metric("F1 (yüksek)", f"{m['f1_yuksek']:.2f}")
            c3.metric("ROC-AUC", f"{m['roc_auc']:.2f}")
            c4.metric("Recall (düşük)", f"{m['duyarlilik_dusuk']:.2f}")
            for kol, dosya in zip(st.columns(3),
                                  ["confusion_matrix.png", "roc_egrisi.png",
                                   "oznitelik_onemi.png"]):
                y = os.path.join(KOK, "ciktilar", "model", dosya)
                if os.path.exists(y):
                    kol.image(y, use_container_width=True)
        else:
            st.info("Model eğitilmemiş: `python src/kalite_egit.py`")


# ---------------------------------------------------------------------------
# YÖNLENDİRİCİ (router)
# ---------------------------------------------------------------------------
if gelistirici:
    ekran_gelistirici()
else:
    ekran = st.session_state.ekran
    if ekran == "karsilama":
        ekran_karsilama()
    elif ekran == "anlat":
        ekran_anlat()
    elif ekran == "sonuc":
        ekran_sonuc()
    elif ekran in ("pano", "iceriklerim"):      # eski bağlantılar da panoya açılsın
        ekran_pano()
    elif ekran == "ton":
        ekran_ton()
    elif ekran == "yardim":
        ekran_yardim()
    elif ekran == "api":
        ekran_api()
    else:
        ekran_karsilama()
