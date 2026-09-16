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

import ekran_araclar
import ekran_basvuru
import ekran_hesap
import ekran_tanitim
import kalite
import kvkk
import logo
import prompts
import takvim
import trends
import uret

# ---------------------------------------------------------------------------
st.set_page_config(page_title="Üretken Kadın — Emeğin dijital sesi",
                   page_icon=logo.page_icon(), layout="centered",
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

# Çıkış ya da hesap silme istendiyse oturum, hiçbir bileşen çizilmeden temizlenir.
if st.session_state.get("_oturumu_kapat"):
    _veda = st.session_state["_oturumu_kapat"]
    for _a in list(st.session_state.keys()):
        del st.session_state[_a]
    st.query_params["ekran"] = "karsilama"
    st.toast(_veda, icon="👋")

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
EKRANLAR = ("karsilama", "anlat", "sonuc", "pano", "iceriklerim", "ton", "yardim", "api",
            "araclar", "gorsel", "satis", "giris", "hesap")

varsayilanlar = {
    "ekran": "karsilama", "yigin": [], "sonuc": None, "gecmis": [],
    "anlatim_metni": "", "kategori_key": "Tekstil / El sanatı",
    "uslup_ornekleri": [], "ses_rizasi": False,
    "aktif_id": None, "plan": [], "pano_mesaj": None,
    "karsilastirma": None, "toplu_sonuc": None,
}
for a, d in varsayilanlar.items():
    st.session_state.setdefault(a, d)
# Araç ekranlarının durumu; listeler kopyalanır ki oturumlar aynı nesneyi paylaşmasın.
for a, d in (*ekran_araclar.VARSAYILANLAR.items(), *ekran_hesap.VARSAYILANLAR.items(), ("basvuru_no", None)):
    st.session_state.setdefault(a, list(d) if isinstance(d, list) else d)
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
# Tanıtım sayfası ziyaretçi içindir; giriş yapmış kullanıcı doğrudan araç kutusuna girer.
if st.session_state.kullanici and st.session_state.ekran == "karsilama":
    st.session_state.ekran = "araclar"
    _url_yaz("araclar")


# ---------------------------------------------------------------------------
# KENAR ÇUBUĞU — her şey düğme: aç/kapa ayarlarının durumu düğmenin üzerinde yazar
# ---------------------------------------------------------------------------
for _a in ("buyuk_yazi", "ozenli", "gelistirici"):
    st.session_state.setdefault(_a, False)


def _ayar_degistir(anahtar: str) -> None:
    st.session_state[anahtar] = not st.session_state[anahtar]


def ayar_dugmesi(anahtar: str, etiket: str, yardim: str) -> None:
    """Açık/kapalı ayar: açıkken vurgulu düğme; durum ekran okuyucuya da etikette okunur."""
    acik = st.session_state[anahtar]
    st.button(f"{etiket} · {'Açık ✓' if acik else 'Kapalı'}", key=f"ayar_{anahtar}",
              type="primary" if acik else "secondary", use_container_width=True,
              help=yardim, on_click=_ayar_degistir, args=(anahtar,))


with st.sidebar:
    if st.session_state.kullanici:
        st.markdown(f'<div class="kenar-hesap">👤 {html.escape(st.session_state.kullanici["ad"])}</div>',
                    unsafe_allow_html=True)
        if st.button("👤 Hesabım", use_container_width=True, key="kenar_hesabim"):
            git("hesap")
    elif st.button("🔑 Giriş yap / Kayıt ol", use_container_width=True, key="kenar_giris", type="primary"):
        git("giris")
    st.markdown('<div class="kenar-baslik">⚙️ Ayarlar</div>', unsafe_allow_html=True)
    ayar_dugmesi("buyuk_yazi", "🔠 Büyük yazı",
                 "Tüm yazıları büyütür — okuması zor gelenler için.")
    # İçerik ayarları ve geliştirici modu yalnızca giriş yapmış kullanıcıya gösterilir.
    if st.session_state.kullanici:
        ayar_dugmesi("ozenli", "✍️ Daha özenli yaz",
                     "İçerikler biraz daha yavaş hazırlanır ama daha özenli yazılır. "
                     "Kapalıyken birkaç saniyede hazır olur.")

        st.markdown('<div class="kenar-bolum">🎨 Ton profiliniz</div>', unsafe_allow_html=True)
        _ornek = len(st.session_state.uslup_ornekleri)
        st.markdown(f'<div class="durum-cip{" acik" if _ornek else ""}">'
                    f'{f"Aktif · {_ornek} örnek" if _ornek else "Henüz tanımlı değil"}</div>',
                    unsafe_allow_html=True)
        if st.button("✏️ Sizin gibi yazmasını öğretin", use_container_width=True, key="kenar_ton"):
            git("ton")

    st.markdown('<div class="kenar-bolum">🏢 Firmalar ve kurumlar için</div>',
                unsafe_allow_html=True)
    if st.button("🔌 API ile entegrasyon", use_container_width=True, key="kenar_api",
                 help="Üretken Kadın'ı kendi platformunuza bağlamak için belgeler"):
        git("api")

    if st.session_state.kullanici:
        st.markdown('<div class="kenar-bolum">📊 Capstone raporu</div>', unsafe_allow_html=True)
        ayar_dugmesi("gelistirici", "🔧 Geliştirici modu",
                     "Prompt karşılaştırma, test paneli ve model metrikleri — capstone "
                     "raporu içindir.")
    st.markdown('<div class="kenar-not">Yayınlamadan önce metinleri okuyun — son karar '
                'her zaman sizindir.</div>', unsafe_allow_html=True)

buyuk_yazi = st.session_state.buyuk_yazi
ozenli = st.session_state.ozenli
gelistirici = st.session_state.gelistirici

TABAN = "18.5px" if buyuk_yazi else "16.5px"


# ---------------------------------------------------------------------------
# TASARIM SİSTEMİ (CSS) — "Oyunbaz" (C yönü): kalın çizgi, sert gölge, canlı renkler
# Erişilebilirlik: pembe dolgularda koyu yazı (5,4:1), büyük dokunma hedefleri,
# görünür odak halkası, "hareketi azalt" tercihinde animasyon/konfeti kapalı.
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Nunito:wght@400;600;700;800&display=swap');
:root {{
  --bg:#FFF8FC; --surface:#FFFFFF; --ink:#2B1638; --ink-2:#4B3659; --muted:#6D4F7E;
  --pink:#FF5C8A; --pink-2:#FF7AA0; --pink-soft:#FFE3EE; --plum:#8A2A6B; --plum-soft:#F6E3F0;
  --yellow:#FFD34D; --yellow-soft:#FFF1C9; --blue-soft:#E6F4FF; --mint-soft:#E3FBE9;
  --green:#17773A; --line:#EED9F2;
  --golge-sm:3px 3px 0 var(--ink); --golge:4px 4px 0 var(--ink); --golge-lg:6px 6px 0 var(--ink);
}}
html {{ font-size:{TABAN}; }}
.stApp {{ background-color:var(--bg); overflow-x:hidden;
  background-image:radial-gradient(rgba(138,42,107,.08) 1.2px, transparent 1.2px);
  background-size:18px 18px; }}
.stApp, .stApp p, .stApp li, .stApp label, input, textarea, select, button {{
  font-family:'Nunito',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:var(--ink); }}
.stApp p, .stApp li {{ line-height:1.65; }}
h1,h2,h3,h4,.ekran-baslik,.kart-baslik,.gun-baslik,.dev-baslik,.kenar-baslik {{
  font-family:'Baloo 2','Nunito',sans-serif; color:var(--ink); }}
[data-testid="stHeader"] {{ background:transparent; height:0; }}
/* Araç çubuğu açık kalır: kenar çubuğunu açan ok onun içinde. Yalnız menü ve Deploy gizli. */
#MainMenu, footer, [data-testid="stMainMenu"], [data-testid="stAppDeployButton"] {{ display:none !important; }}
.block-container {{ padding-top:1.2rem; padding-bottom:3.5rem; max-width:780px; }}
.kart p {{ overflow-wrap:anywhere; }}
a {{ color:var(--plum); font-weight:700; }}

a:focus-visible, button:focus-visible, input:focus-visible,
textarea:focus-visible, select:focus-visible, summary:focus-visible {{
  outline:3px solid var(--plum) !important; outline-offset:3px !important; }}

/* Kenar çubuğunu açan/kapatan ok: küçük çip */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button {{
  background:#fff !important; border:2px solid var(--ink) !important; border-radius:12px !important;
  box-shadow:var(--golge-sm); color:var(--ink) !important; }}

/* Üst bar */
.ustbar {{ display:flex; align-items:center; gap:.75rem; margin-bottom:.9rem; }}
.ustbar .logo {{ width:48px; height:48px; flex:none; border-radius:13px; box-shadow:var(--golge-sm);
  animation:salla 3.2s ease-in-out infinite; }}
.ustbar .logo svg, .karsilama .amblem svg {{ width:100%; height:100%; display:block; }}
.ustbar .ad {{ font-family:'Baloo 2'; font-weight:800; font-size:1.35rem; line-height:1; color:var(--ink); }}
.ustbar .alt {{ font-size:.82rem; color:var(--muted); font-weight:700; }}

/* Adım göstergesi: Anlat → Hazırla → Paylaş */
.ilerleme {{ display:flex; align-items:center; gap:.45rem; flex-wrap:wrap; margin:.1rem 0 .9rem; }}
.ilerleme .adim-cip {{ display:flex; align-items:center; gap:.45rem; padding:.28rem .85rem .28rem .3rem;
  border-radius:999px; background:#fff; border:2px solid var(--line); font-weight:800; font-size:.92rem;
  color:var(--muted); }}
.ilerleme .adim-cip b {{ width:1.75rem; height:1.75rem; border-radius:50%; display:grid; place-items:center;
  background:var(--plum-soft); color:var(--plum); font-family:'Baloo 2'; }}
.ilerleme .adim-cip.aktif {{ background:var(--plum); border-color:var(--ink); color:#fff; box-shadow:var(--golge-sm); }}
.ilerleme .adim-cip.aktif b {{ background:var(--yellow); color:var(--ink); }}
.ilerleme .adim-cip.bitti {{ background:var(--mint-soft); border-color:var(--green); color:var(--green); }}
.ilerleme .adim-cip.bitti b {{ background:var(--green); color:#fff; }}
.ilerleme .cizgi {{ width:1.4rem; height:3px; border-radius:3px; background:var(--line); }}
.ilerleme .cizgi.dolu {{ background:var(--green); }}

/* Karşılama */
.karsilama {{ text-align:center; padding:.6rem 0 0; animation:gir .5s ease both; }}
.karsilama .amblem {{ width:100px; height:100px; border-radius:27px; margin:0 auto 1.1rem;
  box-shadow:var(--golge-lg); animation:zipla 2.4s ease-in-out infinite; }}
.karsilama h1 {{ font-size:2.6rem; font-weight:800; line-height:1.12; color:var(--ink);
  margin:0 0 .8rem; letter-spacing:-.5px; }}
.karsilama .vurgu {{ background:var(--pink); padding:0 .4rem; border-radius:12px;
  -webkit-box-decoration-break:clone; box-decoration-break:clone;
  box-shadow:inset 0 0 0 2.5px var(--ink), 3px 3px 0 var(--ink); }}
.karsilama .aciklama {{ color:var(--ink-2); font-size:1.12rem; max-width:560px; margin:0 auto 1.4rem; }}
.adimlar {{ display:grid; grid-template-columns:repeat(3,1fr); gap:.9rem; margin:1.4rem 0; text-align:left; }}
.adim {{ background:#fff; border:2.5px solid var(--ink); border-radius:20px; padding:1.1rem;
  box-shadow:var(--golge); transition:transform .2s ease; }}
.adim:nth-child(1) {{ background:var(--blue-soft); }}
.adim:nth-child(2) {{ background:var(--yellow-soft); }}
.adim:nth-child(3) {{ background:var(--pink-soft); }}
.adim:hover {{ transform:translateY(-5px) rotate(-1deg); }}
.adim .no {{ width:2.3rem; height:2.3rem; border-radius:50%; background:#fff; border:2.5px solid var(--ink);
  display:grid; place-items:center; font-family:'Baloo 2'; font-weight:800; font-size:1.15rem; margin-bottom:.55rem; }}
.adim h4 {{ margin:0 0 .2rem; font-size:1.25rem; font-weight:800; }}
.adim p {{ margin:0; font-size:.96rem; color:var(--ink-2); }}
.guven {{ background:#fff; border:2.5px dashed var(--plum); border-radius:18px; padding:.9rem 1.1rem;
  color:var(--ink-2); font-size:.98rem; margin:1rem 0 1.4rem; }}

/* Başlıklar / kartlar */
.ekran-baslik {{ font-size:2.1rem; font-weight:800; line-height:1.1; margin:.15rem 0 .25rem; }}
.ekran-baslik .yumak {{ display:inline-block; animation:zipla 1.9s ease-in-out infinite; }}
.ekran-alt {{ color:var(--muted); font-size:1.05rem; font-weight:600; margin-bottom:1.1rem; }}
.kart {{ background:#fff; border:2.5px solid var(--ink); border-radius:20px; padding:1.1rem 1.25rem;
  margin-bottom:1rem; box-shadow:var(--golge); animation:gir .35s ease both; }}
.kart-baslik {{ font-weight:800; font-size:1.22rem; margin:.5rem 0 .45rem; }}
.kart p {{ color:var(--ink-2); margin:0; }}
.bos {{ text-align:center; padding:2rem 1rem; color:var(--muted); font-weight:600; }}
.bos .ik {{ font-size:2.6rem; display:inline-block; animation:zipla 2.2s ease-in-out infinite; }}

/* Kutlama bandı + konfeti (sonuç ekranı) */
.kutlama {{ display:flex; align-items:center; gap:.85rem; background:var(--mint-soft);
  border:2.5px solid var(--ink); border-radius:20px; padding:.8rem 1rem; box-shadow:var(--golge);
  margin:.3rem 0 1.1rem; animation:pop .55s cubic-bezier(.3,1.6,.5,1) both; }}
.kutlama .rozet {{ flex:none; background:var(--green); color:#fff; font-family:'Baloo 2'; font-weight:800;
  padding:.2rem .8rem; border-radius:999px; border:2px solid var(--ink); }}
.kutlama b {{ font-family:'Baloo 2'; font-size:1.1rem; }}
.konfeti {{ position:fixed; top:-24px; height:14px; border-radius:3px; z-index:9999; pointer-events:none;
  animation:dus 2.4s ease-in forwards; }}

/* Butonlar — kalın çizgi, sert gölge, basınca çöker */
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button,
a[data-testid^="stBaseLinkButton"] {{
  background:#fff; color:var(--ink) !important; border:2.5px solid var(--ink) !important;
  border-radius:16px !important; font-family:'Baloo 2','Nunito',sans-serif; font-weight:700;
  font-size:1.08rem; min-height:52px; padding:.5rem 1.1rem; box-shadow:var(--golge); cursor:pointer;
  transition:transform .12s ease, box-shadow .12s ease, background-color .15s ease; }}
.stButton button p, .stDownloadButton button p, [data-testid="stFormSubmitButton"] button p,
a[data-testid^="stBaseLinkButton"] p {{ font-family:'Baloo 2','Nunito',sans-serif; font-weight:700;
  color:var(--ink) !important; font-size:inherit; }}
.stButton button:hover:not(:disabled), .stDownloadButton button:hover:not(:disabled),
[data-testid="stFormSubmitButton"] button:hover:not(:disabled), a[data-testid^="stBaseLinkButton"]:hover {{
  transform:translate(-2px,-2px); box-shadow:var(--golge-lg); background:var(--pink-soft); }}
.stButton button:active:not(:disabled), .stDownloadButton button:active:not(:disabled),
[data-testid="stFormSubmitButton"] button:active:not(:disabled) {{
  transform:translate(3px,3px); box-shadow:1px 1px 0 var(--ink); }}
.stButton button:disabled {{ opacity:.5; cursor:not-allowed; }}
.stDownloadButton button {{ background:var(--mint-soft); }}
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {{
  background:var(--pink); font-size:1.2rem; min-height:58px; }}
.stButton button[kind="primary"] p, .stButton button[data-testid="stBaseButton-primary"] p {{ font-weight:800; }}
.stButton button[kind="primary"]:hover:not(:disabled),
.stButton button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{ background:var(--pink-2); }}

/* Girdiler */
[data-baseweb="textarea"], [data-baseweb="input"], [data-baseweb="select"] > div {{
  border:2.5px solid var(--ink) !important; border-radius:14px !important; background:#fff !important;
  box-shadow:var(--golge-sm); }}
[data-baseweb="textarea"]:focus-within, [data-baseweb="input"]:focus-within,
[data-baseweb="select"] > div:focus-within {{ box-shadow:0 0 0 4px var(--yellow), var(--golge-sm); }}
.stTextArea textarea, .stTextInput input {{ font-size:1.05rem !important; background:#fff !important; color:var(--ink) !important; }}
[data-testid="stWidgetLabel"] p {{ font-weight:800; }}

/* Kategori ve giriş yöntemi kutuları */
[data-testid="stButtonGroup"] > div {{ gap:.5rem !important; flex-wrap:wrap; }}
[data-testid="stButtonGroup"] button {{
  min-height:48px; font-size:1rem; border-radius:16px !important; border:2.5px solid var(--line) !important;
  background:#fff !important; box-shadow:none; transition:transform .15s ease, box-shadow .15s ease; }}
[data-testid="stButtonGroup"] button p {{ font-family:'Nunito',sans-serif; font-weight:800; color:var(--ink) !important; }}
[data-testid="stButtonGroup"] button:hover {{ transform:translateY(-3px) rotate(-1.5deg); border-color:var(--plum) !important; }}
[data-testid="stButtonGroup"] button[data-testid$="Active"],
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-pressed="true"] {{
  background:var(--yellow) !important; border-color:var(--ink) !important; box-shadow:var(--golge-sm); }}

/* Açılır bölümler, uyarılar, sekmeler, kod kutuları */
[data-testid="stExpander"] details {{ border:2.5px solid var(--ink) !important; border-radius:18px !important;
  background:#fff; box-shadow:var(--golge-sm); overflow:hidden; }}
[data-testid="stExpander"] summary {{ font-weight:800; }}
[data-testid="stExpander"] summary:hover {{ background:var(--pink-soft); }}
[data-testid="stAlertContainer"] {{ border:2.5px solid var(--ink); border-radius:16px; box-shadow:var(--golge-sm); }}
[data-testid="stAlertContainer"] p {{ font-weight:600; }}
.stTabs [data-baseweb="tab-list"] {{ gap:.5rem; flex-wrap:wrap; }}
.stTabs [data-baseweb="tab"] {{ font-family:'Baloo 2'; font-weight:700; font-size:1.02rem; height:auto;
  border:2.5px solid var(--ink); border-radius:14px; padding:.3rem .9rem; background:#fff; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ background:var(--yellow); box-shadow:var(--golge-sm); }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}
[data-testid="stCode"] pre {{ border:2px solid var(--ink); border-radius:14px; }}

[data-testid="stHorizontalBlock"] .stButton button p {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
@media (max-width:1000px) {{ .ustbar {{ padding-left:2.9rem; }} }}
.ifsa {{ background:#fff; border:2.5px dashed var(--plum); border-radius:16px; color:var(--muted);
  font-size:.9rem; text-align:center; padding:.8rem; margin-top:1.6rem; font-weight:600; }}

/* Kenar çubuğu: ayarlar da düğme */
[data-testid="stSidebar"] {{ background:#FFF1F7; border-right:3px solid var(--ink); }}
[data-testid="stSidebar"] .kenar-baslik {{ font-weight:800; font-size:1.45rem; margin:.1rem 0 .7rem; }}
[data-testid="stSidebar"] .kenar-bolum {{ font-weight:800; font-size:.92rem; color:var(--plum); margin:1.1rem 0 .45rem; }}
[data-testid="stSidebar"] .stButton button {{ font-size:1rem; min-height:50px; box-shadow:var(--golge-sm); }}
[data-testid="stSidebar"] .stButton button > div {{ justify-content:flex-start; }}
[data-testid="stSidebar"] .durum-cip {{ display:inline-block; font-weight:800; font-size:.85rem; padding:.2rem .7rem;
  border-radius:999px; background:#fff; border:2px solid var(--line); color:var(--muted); margin-bottom:.5rem; }}
[data-testid="stSidebar"] .durum-cip.acik {{ background:var(--mint-soft); border-color:var(--green); color:var(--green); }}
[data-testid="stSidebar"] .kenar-not {{ margin-top:1.3rem; font-size:.85rem; color:var(--muted); font-weight:600;
  border-top:2px dashed var(--line); padding-top:.8rem; }}

/* Geliştirici modu */
.dev-baslik {{ font-weight:800; }}

/* Pano */
.ozet {{ display:grid; grid-template-columns:repeat(3,1fr); gap:.7rem; margin:.3rem 0 1.1rem; }}
.ozet .kutu {{ background:#fff; border:2.5px solid var(--ink); border-radius:18px; padding:.8rem .9rem;
  box-shadow:var(--golge); animation:gir .35s ease both; }}
.ozet .kutu:nth-child(1) {{ background:var(--blue-soft); }}
.ozet .kutu:nth-child(2) {{ background:var(--yellow-soft); }}
.ozet .kutu:nth-child(3) {{ background:var(--pink-soft); }}
.ozet .deger {{ font-family:'Baloo 2'; font-weight:800; font-size:1.6rem; line-height:1.15; overflow-wrap:anywhere; }}
.ozet .etiket {{ font-size:.88rem; color:var(--ink-2); font-weight:700; margin-top:.1rem; }}
.gun-baslik {{ font-weight:800; font-size:1.15rem; color:var(--plum); margin:1.1rem 0 .35rem; }}
/* Araç kartları, çipler, kalite kartı, fiyat çubuğu, özel gün kartları */
.arac-karti {{ border:2.5px solid var(--ink); border-radius:20px; padding:.9rem 1rem; box-shadow:var(--golge);
  margin-bottom:.55rem; min-height:9.4rem; transition:transform .2s ease; }}
.arac-karti:hover {{ transform:translateY(-4px) rotate(-1deg); }}
.arac-karti.mavi {{ background:var(--blue-soft); }}
.arac-karti.sari {{ background:var(--yellow-soft); }}
.arac-karti.pembe {{ background:var(--pink-soft); }}
.arac-karti.yesil {{ background:var(--mint-soft); }}
.arac-karti .ikon {{ font-size:1.8rem; line-height:1; }}
.arac-karti .ad {{ font-family:'Baloo 2'; font-weight:800; font-size:1.2rem; margin:.35rem 0 .15rem; }}
.arac-karti p {{ margin:0; font-size:.9rem; color:var(--ink-2); line-height:1.4; }}
.cip {{ display:inline-block; font-family:'Nunito',sans-serif; font-weight:800; font-size:.8rem; padding:.08rem .6rem;
  border-radius:999px; background:#fff; border:2px solid var(--line); color:var(--ink-2); margin:0 .3rem .3rem 0;
  vertical-align:middle; }}
.cipler {{ margin:.2rem 0 .3rem; }}
.kalite-kart {{ display:flex; gap:1rem; align-items:flex-start; background:#fff; border:2.5px solid var(--ink);
  border-radius:20px; padding:1rem; box-shadow:var(--golge); margin:.8rem 0 1rem; }}
.kalite-kart .puan {{ flex:none; width:4.6rem; height:4.6rem; border-radius:50%; border:3px solid var(--ink);
  display:flex; flex-direction:column; align-items:center; justify-content:center; font-family:'Baloo 2'; line-height:1; }}
.kalite-kart .puan b {{ font-size:1.6rem; font-weight:800; }}
.kalite-kart .puan small {{ font-size:.72rem; font-weight:700; }}
.kalite-kart .puan.iyi {{ background:var(--mint-soft); }}
.kalite-kart .puan.orta {{ background:var(--yellow-soft); }}
.kalite-kart .puan.zayif {{ background:var(--pink-soft); }}
.kalite-kart ul {{ margin:.2rem 0 0; padding-left:1.1rem; }}
.kalite-kart li, .kalite-kart p {{ font-size:.95rem; margin:0 0 .2rem; }}
.fiyat-cubugu {{ display:flex; height:2.3rem; border:2.5px solid var(--ink); border-radius:14px; overflow:hidden;
  box-shadow:var(--golge-sm); margin:.3rem 0 .6rem; }}
.fiyat-cubugu span + span {{ border-left:2px solid var(--ink); }}
.fiyat-cubugu .mavi, .lejant i.mavi {{ background:#9ED8FF; }}
.fiyat-cubugu .sari, .lejant i.sari {{ background:var(--yellow); }}
.fiyat-cubugu .yesil, .lejant i.yesil {{ background:#7BE495; }}
.fiyat-cubugu .pembe, .lejant i.pembe {{ background:var(--pink); }}
.fiyat-cubugu .gri, .lejant i.gri {{ background:#CDBBDA; }}
.lejant {{ list-style:none; padding:0; margin:0 0 1rem; display:flex; flex-wrap:wrap; gap:.3rem 1rem; }}
.lejant li {{ font-size:.9rem; display:flex; align-items:center; gap:.35rem; margin:0; }}
.lejant i {{ width:.95rem; height:.95rem; border-radius:4px; border:2px solid var(--ink); display:inline-block; }}
.gun-kartlari {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(10.5rem,1fr)); gap:.6rem; margin:.3rem 0 .8rem; }}
.gun-karti {{ display:flex; gap:.6rem; align-items:center; background:#fff; border:2.5px solid var(--ink);
  border-radius:16px; padding:.55rem .7rem; box-shadow:var(--golge-sm); }}
.gun-karti.yakin {{ background:var(--yellow-soft); }}
.gun-karti .tarih {{ flex:none; width:3rem; text-align:center; border-right:2px dashed var(--line); padding-right:.5rem;
  font-size:.78rem; font-weight:800; color:var(--plum); line-height:1.1; }}
.gun-karti .tarih b {{ display:block; font-family:'Baloo 2'; font-size:1.45rem; color:var(--ink); }}
.gun-karti .ad {{ font-weight:800; font-size:.92rem; line-height:1.2; }}
.gun-karti .kalan {{ font-size:.78rem; color:var(--muted); font-weight:700; }}
.st-key-basvuru_kutusu {{ background:#fff; border:2.5px solid var(--ink) !important; border-radius:20px !important;
  box-shadow:var(--golge); padding:.6rem 1rem 1rem !important; margin:.4rem 0 1rem; }}
/* Hesap */
.hesap-cip {{ margin-left:auto; font-weight:800; font-size:.9rem; background:#fff; border:2.5px solid var(--ink);
  border-radius:999px; padding:.25rem .8rem; box-shadow:var(--golge-sm); white-space:nowrap; max-width:45%;
  overflow:hidden; text-overflow:ellipsis; }}
[data-testid="stSidebar"] .kenar-hesap {{ font-weight:800; font-size:1.05rem; margin:.1rem 0 .5rem; }}
.hesap-karti {{ background:#fff; border:2.5px solid var(--ink); border-radius:20px; padding:.6rem 1.2rem;
  box-shadow:var(--golge); margin:.4rem 0 1rem; }}
.hesap-karti .satir {{ display:flex; justify-content:space-between; gap:1rem; padding:.45rem 0;
  border-bottom:2px dashed var(--line); overflow-wrap:anywhere; }}
.hesap-karti .satir:last-child {{ border-bottom:0; }}
.hesap-karti .etiket {{ color:var(--muted); font-weight:700; }}
/* Geniş Markdown tabloları (API belgesi) dar ekranda sayfayı değil yalnız kendini kaydırsın */
[data-testid="stMarkdownContainer"] table {{ display:block; max-width:100%; overflow-x:auto; }}

@keyframes gir {{ from {{opacity:0; transform:translateY(10px);}} to {{opacity:1; transform:none;}} }}
@keyframes pop {{ from {{opacity:0; transform:scale(.75);}} to {{opacity:1; transform:none;}} }}
@keyframes zipla {{ 0%,100% {{transform:none;}} 50% {{transform:translateY(-7px) rotate(-8deg);}} }}
@keyframes salla {{ 0%,100% {{transform:none;}} 50% {{transform:rotate(-9deg);}} }}
@keyframes dus {{ to {{transform:translateY(110vh) rotate(720deg); opacity:.3;}} }}
@media (prefers-reduced-motion: reduce) {{
  *,*::before,*::after {{ animation:none !important; transition:none !important; }}
  .konfeti {{ display:none !important; }}
}}
/* Çok dar telefonlarda üst menü 2×2 dizilir; dört düğme tek satırda yazıları kesiyordu */
@media (max-width:430px) {{
  .st-key-ust_menu [data-testid="stHorizontalBlock"] {{ flex-wrap:wrap !important; row-gap:.55rem !important; }}
  .st-key-ust_menu [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ flex:1 1 calc(50% - .5rem) !important; }}
}}
@media (max-width:640px) {{
  .adimlar {{ grid-template-columns:1fr; }}
  .karsilama h1 {{ font-size:1.95rem; }}
  .ekran-baslik {{ font-size:1.7rem; }}
  .ozet {{ gap:.45rem; }}
  .ozet .kutu {{ padding:.6rem .55rem; }}
  .ozet .deger {{ font-size:1.1rem; }}
  .ozet .etiket {{ font-size:.78rem; }}
  .ilerleme .adim-cip {{ font-size:.82rem; padding-right:.6rem; }}
  .ilerleme .cizgi {{ width:.7rem; }}
  .arac-karti {{ min-height:10.5rem; padding:.7rem .75rem; }}
  .arac-karti .ad {{ font-size:1.02rem; }}
  .arac-karti p {{ font-size:.8rem; }}
  .kalite-kart {{ gap:.7rem; padding:.8rem; }}
  .kalite-kart .puan {{ width:3.8rem; height:3.8rem; }}
  .block-container {{ padding-left:.9rem; padding-right:.9rem; }}
  /* Yan yana düğmeler (gezinme, eylemler) mobilde alt alta yığılmasın */
  [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:.45rem !important; }}
  /* Streamlit dar ekranda her sütuna %100 en küçük genişlik verir; nowrap ile birleşince
     sütunlar ekran dışına taşar (375px'te "Panom"/"Yardım" görünmüyordu). Eşit paylaştır. */
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width:0 !important; width:auto !important; flex:1 1 0 !important; }}
  [data-testid="stHorizontalBlock"] .stButton button {{
    font-size:.9rem; padding:.4rem .3rem; min-height:46px; box-shadow:var(--golge-sm); }}
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Ortak parçalar
# ---------------------------------------------------------------------------
def ust_bar() -> None:
    """Sade üst bar: logo + geri düğmesi + gezinme."""
    kullanici = st.session_state.get("kullanici")
    hesap_cipi = (f'<div class="hesap-cip" title="{html.escape(kullanici["eposta"])}">👤 '
                  f'{html.escape(kullanici["ad"].split()[0])}</div>' if kullanici else "")
    st.markdown(
        f'<div class="ustbar"><div class="logo">{logo.SVG}</div>'
        '<div><div class="ad">Üretken Kadın</div>'
        '<div class="alt">Emeğin dijital sesi</div></div>' + hesap_cipi + '</div>',
        unsafe_allow_html=True)
    k = st.container(key="ust_menu").columns([1, 1, 1.15, 0.95])
    if k[0].button("← Geri", use_container_width=True, key="nav_geri",
                   help="Bir önceki ekrana dön"):
        geri()
    if k[1].button("🧰 Araçlar", use_container_width=True, key="nav_araclar",
                   help="İçerik yaz, görsel stüdyosu, satış araçları"):
        git("araclar")
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


ADIMLAR = ("Anlat", "Hazırla", "Paylaş")


def adim_gostergesi(aktif: int) -> None:
    """Anlat → Hazırla → Paylaş ilerleme göstergesi; aktif: 0, 1 ya da 2."""
    parcalar = []
    for i, ad in enumerate(ADIMLAR):
        if i:
            parcalar.append(f'<span class="cizgi{" dolu" if i <= aktif else ""}"></span>')
        durum = " bitti" if i < aktif else (" aktif" if i == aktif else "")
        mevcut = ' aria-current="step"' if i == aktif else ""
        parcalar.append(f'<span class="adim-cip{durum}"{mevcut}>'
                        f'<b>{"✓" if i < aktif else i + 1}</b>{ad}</span>')
    st.markdown('<div class="ilerleme" aria-label="İlerleme">' + "".join(parcalar) + "</div>",
                unsafe_allow_html=True)


def konfeti() -> None:
    """İçerik ilk hazırlandığında bir kez düşen konfeti (hareketi azalt tercihinde gizlenir)."""
    renkler = ["#FF5C8A", "#FFD34D", "#4DD4FF", "#7BE495", "#8A2A6B"]
    parcalar = "".join(
        f'<i class="konfeti" style="left:{(i * 37) % 100}%;background:{renkler[i % 5]};'
        f'animation-delay:{(i % 7) * 0.09:.2f}s;width:{8 + (i % 3) * 3}px"></i>'
        for i in range(36))
    st.markdown(f'<div aria-hidden="true">{parcalar}</div>', unsafe_allow_html=True)


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
    """Ziyaretçiye tanıtım sayfası (giriş yapmış kullanıcı buraya gelmeden araç kutusuna yönlenir)."""
    ekran_tanitim.tanitim_sayfasi(ekran_tanitim.Baglam(git=git))


# ===========================================================================
# EKRAN: ANLAT
# ===========================================================================
def ekran_anlat() -> None:
    ust_bar()
    adim_gostergesi(0)
    st.markdown('<div class="ekran-baslik">Ne ürettiniz? '
                '<span class="yumak" aria-hidden="true">🧶</span></div>',
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
                    st.session_state.kutlama = True          # sonuç ekranında bir kez konfeti
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

    adim_gostergesi(2)
    if st.session_state.pop("kutlama", False):
        konfeti()
    st.markdown('<div class="ekran-baslik">İşte içerikleriniz 🎉</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="kutlama"><span class="rozet">✓ Hazır</span><div>'
                '<b>İçerikleriniz hazırlandı.</b><br>Okuyun, dilediğiniz yeri düzeltin, '
                'sonra kopyalayıp paylaşın.</div></div>', unsafe_allow_html=True)
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

    # Aynı ürün için araçlara doğrudan geçiş (ürün ve sekme hazır seçili gelir)
    st.markdown('<div class="kart-baslik" style="margin-top:1.2rem">🧰 Bu ürün için</div>',
                unsafe_allow_html=True)
    hedefler = (("📸 Görsel", "gorsel", "gs_sekme", ekran_araclar.GS_SEKMELER[0]),
                ("🛒 İlan", "satis", "satis_sekme", ekran_araclar.SATIS_SEKMELER[2]),
                ("💰 Fiyat", "satis", "satis_sekme", ekran_araclar.SATIS_SEKMELER[0]))
    for i, (kol, (etiket, hedef, sekme_anahtari, sekme)) in enumerate(zip(st.columns(3), hedefler)):
        if kol.button(etiket, key=f"bu_urun_{i}", use_container_width=True):
            st.session_state.secili_kayit_id = kayit["id"]
            ekran_araclar.sekme_sec(sekme_anahtari, sekme)
            git(hedef)

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

    st.markdown('<div class="ekran-alt">İçerikleriniz ve paylaşım takviminiz tek yerde; '
                'hesabınızda otomatik olarak saklanır.</div>',
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
        ("🔒 Verileriniz güvende", "Anlatımınız yalnızca içerik hazırlamak ve hesabınızda "
         "saklamak için kullanılır; fotoğraflar saklanmaz. Hesabınızı istediğiniz an tüm "
         "verileriyle silebilirsiniz (KVKK)."),
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
        <p>Aşağıdaki formu doldurun; ekibimiz inceleyip size özel API anahtarı ve günlük kota tanımlar.</p></div>
      <div class="adim"><div class="no">2</div><h4>Deneyin</h4>
        <p>Canlı belgede (/docs) anahtarınızla istekleri deneyin, sonra kendi sunucunuza ekleyin.</p></div>
      <div class="adim"><div class="no">3</div><h4>Üreticilerinize açın</h4>
        <p>Metni üreticiye onaylatarak yayımlayın; sesli anlatım için açık rıza alın.</p></div>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True, key="basvuru_kutusu"):
        ekran_basvuru.basvuru_formu()
    if iletisim:
        st.caption(f"Sorularınız için: {iletisim}")
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
               "Kenar çubuğundaki düğmeden kapatabilirsiniz.")
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


def _baglam_hesap() -> ekran_hesap.Baglam:
    return ekran_hesap.Baglam(ust_bar=ust_bar, git=git)


def _baglam() -> ekran_araclar.Baglam:
    """Araç ekranlarına (ekran_araclar.py) app.py'nin ortak parçalarını verir."""
    return ekran_araclar.Baglam(ust_bar=ust_bar, git=git, kayit_bul=kayit_bul,
                                kategoriler=KATEGORILER, ozenli=ozenli)


# ---------------------------------------------------------------------------
# YÖNLENDİRİCİ (router)
# ---------------------------------------------------------------------------
ekran = st.session_state.ekran
if not st.session_state.kullanici and (gelistirici or ekran not in ekran_hesap.KORUMASIZ_EKRANLAR):
    # Araçlar girişten sonra; giriş yapınca istenen ekrana dönülür.
    if ekran not in ekran_hesap.KORUMASIZ_EKRANLAR:
        st.session_state.giris_sonrasi = ekran
    ekran_hesap.giris_ekrani(_baglam_hesap())
elif gelistirici:
    ekran_gelistirici()
else:
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
    elif ekran == "araclar":
        ekran_araclar.arac_kutusu(_baglam())
    elif ekran == "gorsel":
        ekran_araclar.gorsel_studyosu(_baglam())
    elif ekran == "satis":
        ekran_araclar.satis_araclari(_baglam())
    elif ekran == "giris":
        if st.session_state.kullanici:          # zaten giriş yapılmışsa araç kutusuna
            git("araclar")
        ekran_hesap.giris_ekrani(_baglam_hesap())
    elif ekran == "hesap":
        ekran_hesap.hesabim_ekrani(_baglam_hesap())
    else:
        ekran_karsilama()

# Giriş yapmış kullanıcının içerikleri değiştiyse hesabına kaydedilir (yalnızca değişiklik varsa).
ekran_hesap.kaydet_gerekirse()
