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
import io
import json
import os
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import kalite
import kvkk
import prompts
import trends
import uret

# ---------------------------------------------------------------------------
st.set_page_config(page_title="Üretken Kadın — Emeğin dijital sesi",
                   page_icon="🧵", layout="centered",
                   initial_sidebar_state="collapsed")

# Streamlit Cloud'da API anahtarı "secret" olarak gelir; uret.py os.getenv okur.
try:
    for _a in ("GEMINI_API_KEY", "GEMINI_MODEL"):
        if _a in st.secrets:
            os.environ.setdefault(_a, str(st.secrets[_a]))
except Exception:
    pass

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
EKRANLAR = ("karsilama", "anlat", "sonuc", "iceriklerim", "ton", "yardim")

varsayilanlar = {
    "ekran": "karsilama", "yigin": [], "sonuc": None, "gecmis": [],
    "anlatim_metni": "", "kategori_key": "Tekstil / El sanatı",
    "uslup_ornekleri": [], "reels": None, "foto": None, "ses_rizasi": False,
    "karsilastirma": None, "toplu_sonuc": None,
}
for a, d in varsayilanlar.items():
    st.session_state.setdefault(a, d)


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
    st.divider()
    st.caption("Ton profiliniz")
    if st.session_state.uslup_ornekleri:
        st.success(f"Aktif ({len(st.session_state.uslup_ornekleri)} örnek)")
    else:
        st.caption("Tanımlı değil.")
    if st.button("Sizin gibi yazmasını öğretin", use_container_width=True):
        git("ton")
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
#MainMenu, footer, [data-testid="stToolbar"] {{ display:none !important; }}
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

@keyframes gir {{ from {{opacity:0; transform:translateY(10px);}} to {{opacity:1; transform:none;}} }}
@media (prefers-reduced-motion: reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; }} }}
@media (max-width:640px) {{
  .adimlar {{ grid-template-columns:1fr; }}
  .karsilama h1 {{ font-size:1.75rem; }}
  .block-container {{ padding-left:.9rem; padding-right:.9rem; }}
  /* Yan yana düğmeler (gezinme, eylemler) mobilde alt alta yığılmasın */
  [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:.4rem !important; }}
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
    if k[2].button("📁 İçeriklerim", use_container_width=True, key="nav_gec"):
        git("iceriklerim")
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
                        ton="sıcak ve samimi", teknik="few_shot",
                        uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                    st.session_state.sonuc = sonuc
                    st.session_state.reels = st.session_state.foto = None
                    st.session_state.gecmis.insert(0, {
                        "saat": datetime.now().strftime("%H:%M"),
                        "kategori": st.session_state.kategori_key, "anlatim": anlatim,
                        "instagram": sonuc.instagram, "shopier": sonuc.shopier})
                    git("sonuc")
                except Exception as e:
                    st.error(f"İçerik hazırlanamadı: {e}")


# ===========================================================================
# EKRAN: SONUÇ
# ===========================================================================
def ekran_sonuc() -> None:
    ust_bar()
    sonuc = st.session_state.sonuc
    if sonuc is None:
        git("anlat"); return
    kategori = st.session_state.kategori_key

    st.markdown('<div class="ekran-baslik">İşte içerikleriniz 🎉</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">Beğenmediğiniz yeri doğrudan '
                'düzeltebilirsiniz. Hazır olunca kopyalayıp paylaşın.</div>',
                unsafe_allow_html=True)

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

    b1, b2 = st.columns(2)
    with b1:
        st.download_button("⬇  İkisini de indir",
                           data=f"INSTAGRAM\n{ig}\n\nSHOPIER\n{sh}",
                           file_name="uretken_kadin_icerik.txt",
                           use_container_width=True)
    with b2:
        if st.button("＋  Yeni ürün anlat", use_container_width=True, type="primary"):
            git("anlat")

    # İsteğe bağlı ekstralar
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    with st.expander("✨ İsterseniz: video ve fotoğraf yardımı"):
        e1, e2 = st.columns(2)
        if e1.button("🎬 Video çekim planı", use_container_width=True):
            with st.spinner("Çekim planı hazırlanıyor…"):
                try:
                    st.session_state.reels = uret.reels_uret(
                        anlatim=st.session_state.anlatim_metni, kategori=kategori,
                        uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                except Exception as e:
                    st.error(f"Hazırlanamadı: {e}")
        if e2.button("📸 Fotoğraf önerileri", use_container_width=True):
            with st.spinner("Öneriler hazırlanıyor…"):
                try:
                    st.session_state.foto = uret.foto_rehberi_uret(
                        anlatim=st.session_state.anlatim_metni, kategori=kategori)
                except Exception as e:
                    st.error(f"Hazırlanamadı: {e}")
        if st.session_state.get("reels"):
            st.markdown(st.session_state.reels)
        if st.session_state.get("foto"):
            st.markdown(st.session_state.foto)

    st.markdown('<div class="ifsa">Bu içerik yapay zekâ yardımıyla hazırlandı · '
                'paylaşmadan önce okuyun — son karar sizindir.</div>',
                unsafe_allow_html=True)


# ===========================================================================
# EKRAN: İÇERİKLERİM
# ===========================================================================
def ekran_iceriklerim() -> None:
    ust_bar()
    st.markdown('<div class="ekran-baslik">İçerikleriniz</div>', unsafe_allow_html=True)
    if not st.session_state.gecmis:
        st.markdown('<div class="bos"><div class="ik">📁</div>'
                    '<p>Henüz içerik hazırlamadınız.</p></div>', unsafe_allow_html=True)
        if st.button("İlk içeriğimi hazırlayayım  →", use_container_width=True, type="primary"):
            git("anlat")
        return
    st.markdown('<div class="ekran-alt">Bu oturumda hazırladıklarınız. '
                '(Sayfayı kapatınca sıfırlanır.)</div>', unsafe_allow_html=True)
    for kayit in st.session_state.gecmis:
        baslik = kayit["anlatim"][:60].replace("\n", " ")
        with st.expander(f"{kayit['saat']} · {baslik}…"):
            g1, g2 = st.columns(2)
            g1.markdown("**📱 Instagram**"); g1.write(kayit["instagram"])
            g2.markdown("**🛍️ Shopier**"); g2.write(kayit["shopier"])
    if st.button("Geçmişi temizle", use_container_width=True):
        st.session_state.gecmis = []
        st.rerun()


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
    elif ekran == "iceriklerim":
        ekran_iceriklerim()
    elif ekran == "ton":
        ekran_ton()
    elif ekran == "yardim":
        ekran_yardim()
    else:
        ekran_karsilama()
