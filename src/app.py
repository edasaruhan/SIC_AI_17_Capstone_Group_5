# -*- coding: utf-8 -*-
"""
Üretken Kadın — Streamlit arayüzü (HITL: insan onaylı akış)

Çalıştırmak için:
    streamlit run src/app.py
"""

import csv
import glob
import io
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

# Marka renk paleti — semantik tokenler (UI/UX Pro Max "color-semantic" kuralı).
# Metin/arka plan çiftleri WCAG AA (>=4.5:1) olarak sayısal doğrulanmıştır.
KOYU = "#4A2138"; ANA = "#9C4368"; ALTIN = "#C08A2D"
YESIL = "#7E9B85"; ACIK = "#F3ECE4"; ZEMIN = "#FDFBFA"
METIN = "#3D362F"          # ana metin        (beyazda 11.9:1)
METIN_YUM = "#5C5249"      # yumuşak metin     (beyazda 7.6:1)
SOLUK = "#6B5960"          # ikincil/etiket    (beyazda 6.5:1)  eski #8A7A80 = 4.06 idi
YESIL_METIN = "#4F6E57"    # yeşil metin/indir (beyazda 5.7:1)  eski #7E9B85 = 3.04 idi

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Oturum durumu
# ---------------------------------------------------------------------------
varsayilanlar = {
    "sonuc": None, "gecmis": [], "anlatim_metni": "",
    "uslup_ornekleri": [], "karsilastirma": None, "toplu_sonuc": None,
    "reels": None, "foto": None, "ses_rizasi": False,
}
for anahtar, deger in varsayilanlar.items():
    st.session_state.setdefault(anahtar, deger)


# ---------------------------------------------------------------------------
# KENAR ÇUBUĞU — ayarlar ve erişilebilirlik
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Ayarlar")
    buyuk_yazi = st.toggle("♿ Büyük yazı modu", value=False,
                           help="Metinleri büyütür — okuması zor gelenler için.")
    st.divider()

    st.markdown("**🎙️ Ton profiliniz**")
    if st.session_state.uslup_ornekleri:
        st.success(f"Aktif — {len(st.session_state.uslup_ornekleri)} örnek "
                   "kullanılıyor. İçerikleriniz sizin üslubunuzla yazılıyor.")
    else:
        st.info("Henüz tanımlamadınız.\n\n*Ton Profilim* sekmesinden kendi "
                "metinlerinizi ekleyin — sonuçlar size çok daha çok benzesin.")

    st.divider()
    st.markdown("**📈 Bu oturum**")
    st.metric("Üretilen içerik", len(st.session_state.gecmis))
    if st.session_state.gecmis:
        kategoriler_sayac = {}
        for kayit in st.session_state.gecmis:
            kategoriler_sayac[kayit["kategori"]] = \
                kategoriler_sayac.get(kayit["kategori"], 0) + 1
        en_cok = max(kategoriler_sayac, key=kategoriler_sayac.get)
        st.caption(f"En çok: {en_cok}")

    st.divider()
    st.caption("Yayınlamadan önce metinleri mutlaka okuyun — "
               "son karar her zaman sizindir.")

YAZI = "1.2rem" if buyuk_yazi else "0.98rem"
BASLIK = "2.7rem" if buyuk_yazi else "2.2rem"

st.markdown(f"""
<style>
  [data-testid="stHeader"] {{ background: transparent; height: 0; }}
  #MainMenu, footer {{ visibility: hidden; }}
  .stApp {{ background: {ZEMIN}; }}
  .block-container {{ padding-top: 1rem; max-width: 1200px; }}
  .stTextArea textarea, .stTextInput input {{ font-size: {YAZI} !important; }}

  /* ---- UI/UX Pro Max: erişilebilirlik, dokunma, hareket ve responsive ---- */
  html {{ font-size: 16px; }}                              /* readable-font-size: 16px taban */
  .stApp, .stApp p, .stApp li {{ line-height: 1.6; }}      /* line-height 1.5-1.75 */
  .stApp {{ overflow-x: hidden; }}                          /* horizontal-scroll engeli */
  .kart p, .hero p {{ overflow-wrap: anywhere; }}           /* uzun kelime taşması */

  /* Görünür klavye odak halkası — focus-states / focus-appearance (CRITICAL) */
  a:focus-visible, button:focus-visible, input:focus-visible,
  textarea:focus-visible, select:focus-visible, [role="tab"]:focus-visible {{
      outline: 3px solid {ALTIN} !important; outline-offset: 2px !important;
      border-radius: 6px; }}

  /* Dokunma hedefi >=44px + imleç + yumuşak geçiş (touch-target-size, cursor-pointer) */
  div.stButton > button, div.stDownloadButton > button {{
      min-height: 44px; cursor: pointer;
      transition: background 160ms ease, transform 120ms ease, box-shadow 160ms ease; }}
  div.stButton > button:hover:not(:disabled),
  div.stDownloadButton > button:hover:not(:disabled) {{
      transform: translateY(-1px); box-shadow: 0 4px 14px rgba(74,33,56,0.18); }}
  div.stButton > button:active:not(:disabled) {{ transform: translateY(0) scale(0.99); }}
  /* Devre dışı durum netliği (disabled-states) */
  div.stButton > button:disabled, div.stDownloadButton > button:disabled {{
      opacity: 0.5; cursor: not-allowed; }}
  .stCheckbox label, [data-testid="stFileUploaderDropzone"] {{ cursor: pointer; }}

  .metrik-deger {{ font-variant-numeric: tabular-nums; }}   /* number-tabular */

  /* Hareket duyarlılığı — reduced-motion (CRITICAL erişilebilirlik) */
  @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ transition: none !important; animation: none !important; }}
  }}

  /* Küçük ekran uyumu — mobile-first / breakpoint-consistency (375-640px) */
  @media (max-width: 640px) {{
      .navbar {{ flex-direction: column; gap: 0.7rem; align-items: flex-start; }}
      .hero {{ padding: 1.6rem 1.1rem; }}
      .hero h1 {{ font-size: 1.7rem; }}
      .cipler {{ gap: 0.4rem; }}
  }}

  .navbar {{ display: flex; align-items: center; justify-content: space-between;
      background: {KOYU}; padding: 0.85rem 1.6rem; border-radius: 14px;
      margin-bottom: 1.2rem; box-shadow: 0 4px 18px rgba(74,33,56,0.18); }}
  .nav-brand {{ display: flex; align-items: center; gap: 0.6rem; }}
  .nav-logo {{ width: 34px; height: 34px; border-radius: 9px; background: {ANA};
      display: flex; align-items: center; justify-content: center; font-size: 1.1rem; }}
  .nav-title {{ color: #fff; font-weight: 700; font-size: 1.2rem; }}
  .nav-sub {{ color: #D9C4CC; font-size: 0.78rem; margin-top: -2px; }}
  .nav-links {{ display: flex; align-items: center; gap: 1.4rem; }}
  .nav-links a {{ color: #E8DBE0; text-decoration: none; font-size: 0.92rem;
      font-weight: 500; }}
  .nav-links a:hover {{ color: {ALTIN}; }}
  .nav-rozet {{ background: rgba(255,255,255,0.12); color: #fff;
      padding: 0.3rem 0.75rem; border-radius: 20px; font-size: 0.74rem;
      font-weight: 600; }}

  .hero {{ background: linear-gradient(135deg, {ACIK} 0%, #FBF1EC 55%, #F6E6E9 100%);
      border-radius: 16px; padding: 2.4rem 2.2rem 2rem; margin-bottom: 1.3rem;
      border: 1px solid #EBDDE2; text-align: center; }}
  .hero h1 {{ color: {KOYU}; font-size: {BASLIK}; margin: 0 0 0.6rem 0;
      line-height: 1.2; letter-spacing: -0.5px; }}
  .hero .vurgu {{ color: {ANA}; }}
  .hero p {{ color: {METIN_YUM}; font-size: {YAZI}; margin: 0 auto 1.3rem;
      max-width: 620px; line-height: 1.6; }}
  .cipler {{ display: flex; gap: 0.6rem; flex-wrap: wrap;
      justify-content: center; }}
  .cip {{ background: #fff; border: 1px solid #E5D5DB; color: {KOYU};
      padding: 0.4rem 0.95rem; border-radius: 20px; font-size: 0.88rem;
      font-weight: 500; }}

  .adim {{ display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.7rem; }}
  .adim-no {{ width: 25px; height: 25px; border-radius: 50%; background: {ANA};
      color: #fff; display: flex; align-items: center; justify-content: center;
      font-size: 0.8rem; font-weight: 700; }}
  .adim-no.yesil {{ background: {YESIL}; }}
  .adim-yazi {{ color: {KOYU}; font-weight: 700; font-size: 1.02rem;
      letter-spacing: 0.4px; }}

  .kart {{ background: #fff; border: 1px solid #EADCE1; border-radius: 12px;
      padding: 1.05rem 1.25rem; margin-bottom: 0.85rem;
      box-shadow: 0 2px 10px rgba(74,33,56,0.05); }}
  .kart-baslik {{ color: {ANA}; font-weight: 700; font-size: 0.98rem;
      margin-bottom: 0.5rem; }}
  .kart p {{ color: #514840; font-size: {YAZI}; line-height: 1.55; margin: 0; }}

  .metrik {{ background: #fff; border: 1px solid #EADCE1; border-radius: 11px;
      padding: 0.8rem 1rem; text-align: center; }}
  .metrik-deger {{ color: {ANA}; font-size: 1.6rem; font-weight: 700;
      line-height: 1.1; }}
  .metrik-etiket {{ color: {SOLUK}; font-size: 0.82rem; margin-top: 0.25rem; }}

  div.stButton > button {{ background: {ANA}; color: #fff; border: none;
      border-radius: 9px; font-weight: 600; padding: 0.6rem 1rem;
      font-size: 0.98rem; }}
  div.stButton > button:hover {{ background: {KOYU}; color: #fff; }}
  div.stDownloadButton > button {{ background: #fff; color: {YESIL_METIN};
      border: 1.5px solid {YESIL}; border-radius: 9px; font-weight: 600; }}

  .stTabs [data-baseweb="tab-list"] {{ gap: 0.3rem; flex-wrap: wrap; }}
  .stTabs [data-baseweb="tab"] {{ border-radius: 9px 9px 0 0;
      padding: 0.55rem 1rem; font-weight: 600; font-size: 0.94rem; }}
  .stTabs [aria-selected="true"] {{ background: {ACIK}; color: {KOYU} !important; }}

  .ifsa {{ background: #FBF6F2; border: 1px dashed #DCC9CF; border-radius: 10px;
      color: {SOLUK}; font-size: 0.88rem; text-align: center; padding: 0.7rem;
      margin-top: 1.5rem; }}
  .altbilgi {{ color: {SOLUK}; font-size: 0.84rem; text-align: center;
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
  </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def adim_basligi(no: str, yazi: str, yesil: bool = False) -> None:
    sinif = "adim-no yesil" if yesil else "adim-no"
    st.markdown(f'<div class="adim"><div class="{sinif}">{no}</div>'
                f'<div class="adim-yazi">{yazi}</div></div>', unsafe_allow_html=True)


def metrik_satiri(veriler: list[tuple]) -> None:
    kolonlar = st.columns(len(veriler))
    for kol, (deger, etiket) in zip(kolonlar, veriler):
        kol.markdown(f'<div class="metrik"><div class="metrik-deger">{deger}</div>'
                     f'<div class="metrik-etiket">{etiket}</div></div>',
                     unsafe_allow_html=True)


def olcumler(ig: str, sh: str, kategori: str) -> tuple:
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    return (uret.seo_kapsami(f"{ig} {sh}", kelimeler), len(kelimeler),
            uret.klise_sayisi(f"{ig} {sh}"), uret.kanal_benzerligi(ig, sh))


# Prompt tekniklerinin kullanıcıya gösterilen adları.
# Teknik terimler parantez içinde, önce anlaşılır Türkçe karşılığı.
TEKNIK_ADLARI = {
    "few_shot": "Örneklerle yazdır  (few-shot)",
    "zero_shot": "Örneksiz yazdır  (zero-shot)",
    "chain_of_thought": "Adım adım düşündür  (chain-of-thought)",
}


ORNEKLER = [
    ("🧶 Bebek battaniyesi", "Tekstil / El sanatı",
     "El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, "
     "tamamen elde örüyorum. Bir tanesi yaklaşık üç günümü alıyor. Anneannemden "
     "öğrendiğim bir desen kullanıyorum."),
    ("🍅 Domates salçası", "Gıda",
     "Ev yapımı domates salçası. Kendi bahçemizin domatesi, güneşte kurutuyorum. "
     "Hiçbir katkı maddesi yok, sadece domates ve tuz. 700 gramlık kavanozlarda "
     "satıyorum."),
    ("💍 Gümüş kolye", "Takı / Aksesuar",
     "Gümüş tel sarma tekniğiyle kolye yapıyorum. 925 ayar gümüş tel kullanıyorum, "
     "taşları doğal taş. Her kolye tek, aynısından ikinci bir tane olmuyor."),
]


# ---------------------------------------------------------------------------
# SEKMELER
# ---------------------------------------------------------------------------
(s_uret, s_karsi, s_ton, s_toplu,
 s_gecmis, s_panel, s_nasil, s_etik) = st.tabs([
    "✍️  İçerik Üret", "⚖️  Karşılaştır", "🎙️  Ton Profilim", "📦  Toplu Üretim",
    "📁  Geçmişim", "📊  Panel", "💡  Nasıl Çalışır", "🛡️  Etik & KVKK",
])


# ===========================================================================
# 1 — İÇERİK ÜRET
# ===========================================================================
with s_uret:
    st.markdown("""
    <div class="hero">
      <h1>Emeğinizin bir hikâyesi var.<br>
          <span class="vurgu">Duyulmasını sağlayalım.</span></h1>
      <p>Ürününüzü kendi cümlelerinizle anlatın — Instagram gönderiniz,
         satış sayfası metniniz ve video çekim planınız dakikalar içinde hazır.</p>
      <div class="cipler">
        <div class="cip">✓ Sizin üslubunuz korunur</div>
        <div class="cip">✓ Abartı ve uydurma yok</div>
        <div class="cip">✓ Son karar her zaman sizde</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**🎯 Hemen denemek ister misiniz?** Hazır bir örnek seçin:")
    o1, o2, o3 = st.columns(3)
    for kol, (etiket, ornek_kat, metin) in zip((o1, o2, o3), ORNEKLER):
        if kol.button(etiket, use_container_width=True, key=f"ornek_{etiket}"):
            st.session_state.anlatim_metni = metin
            st.rerun()

    st.divider()
    sol, sag = st.columns([1, 1], gap="large")

    with sol:
        adim_basligi("1", "ÜRÜNÜNÜZÜ ANLATIN")

        yazarak, sesli = st.tabs(["⌨️  Yazarak anlat", "🎙️  Sesli anlat"])

        with sesli:
            st.caption("Yazmak zor geliyorsa konuşun — sesinizi metne çeviririz. "
                       "Kendi kelimeleriniz korunur, cümleleriniz değiştirilmez.")

            # --- KVKK aydınlatma + açık rıza kapısı (ses özel nitelikli olabilir) ---
            with st.expander("🔒  Verileriniz nasıl işlenir? (KVKK)", expanded=False):
                st.markdown(kvkk.SES_AYDINLATMA)
            st.session_state.ses_rizasi = st.checkbox(
                kvkk.SES_RIZA_ETIKETI, value=st.session_state.ses_rizasi)

            ses_kaydi = st.audio_input("Kaydı başlatmak için mikrofona basın")
            cevir = st.button("🎙️  Sesimi metne çevir", use_container_width=True,
                              disabled=not st.session_state.ses_rizasi)
            if ses_kaydi is not None and not st.session_state.ses_rizasi:
                st.info("Devam etmek için yukarıdaki **açık rıza** kutusunu "
                        "işaretleyin — ya da yazarak anlatın.")
            if ses_kaydi is not None and st.session_state.ses_rizasi and cevir:
                with st.spinner("Ses kaydınız yazıya dökülüyor…"):
                    try:
                        metin = uret.sesten_metne(ses_kaydi.getvalue(), "audio/wav")
                        if metin:
                            st.session_state.anlatim_metni = metin
                            st.success("Metne çevrildi — soldaki kutuda "
                                       "düzenleyebilirsiniz.")
                            st.rerun()
                        else:
                            st.warning("Ses anlaşılamadı, tekrar dener misiniz?")
                    except Exception as hata:
                        st.error(f"Ses çevrilemedi: {hata}")

        with yazarak:
            anlatim = st.text_area(
                "Anlatım", height=175, key="anlatim_metni",
                placeholder="Ne ürettiğinizi, nasıl yaptığınızı ve ne kadar "
                            "sürdüğünü anlatın.\n\nÖrnek: El örgüsü bebek "
                            "battaniyesi yapıyorum…",
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

        with st.expander("⚙️  Gelişmiş ayarlar (rapor / karşılaştırma için)"):
            teknik = st.radio(
                "Yapay zekâya nasıl yazdıralım?",
                ["few_shot", "zero_shot", "chain_of_thought"],
                format_func=lambda t: TEKNIK_ADLARI[t],
                captions=[
                    "Örnek metinler göstererek — varsayılan, en iyi sonucu verir",
                    "Hiç örnek göstermeden — diğerleriyle kıyaslamak için kullanılır",
                    "Yazmadan önce adım adım düşünmesini isteyerek",
                ])

            st.divider()
            st.caption("SEO anahtar kelimeleri Google Trends'ten canlı çekilir; "
                       "ulaşılamazsa sabit listeye düşülür.")
            if st.button("🔎  Bu kategori için Trends kelimelerini göster"):
                with st.spinner("Google Trends sorgulanıyor…"):
                    ts = trends.trend_getir(kategori)
                etiket = {"trends": "Google Trends (canlı)",
                          "önbellek": "Google Trends (önbellek)",
                          "varsayılan": "Varsayılan liste (Trends'e ulaşılamadı)"}
                st.info(f"**Kaynak:** {etiket[ts.kaynak]}\n\n"
                        + ", ".join(ts.kelimeler))

        if st.button("✦   İçerik Üret", use_container_width=True, type="primary"):
            if not anlatim.strip():
                st.warning("Önce ürününüzü birkaç cümleyle anlatın.")
            elif len(anlatim.split()) < 5:
                st.warning("Biraz daha ayrıntı verin — en az bir iki cümle yazın.")
            else:
                with st.spinner("İçeriğiniz hazırlanıyor…"):
                    try:
                        sonuc = uret.icerik_uret(
                            anlatim=anlatim, kategori=kategori, ton=ton,
                            teknik=teknik,
                            uslup_ornekleri=st.session_state.uslup_ornekleri or None)
                        st.session_state.sonuc = sonuc
                        st.session_state.gecmis.insert(0, {
                            "saat": datetime.now().strftime("%H:%M"),
                            "kategori": kategori, "anlatim": anlatim,
                            "instagram": sonuc.instagram, "shopier": sonuc.shopier})
                    except Exception as hata:
                        st.session_state.sonuc = None
                        st.error(f"İçerik üretilemedi: {hata}")

    with sag:
        adim_basligi("2", "DÜZENLEYİN VE ONAYLAYIN", yesil=True)
        sonuc = st.session_state.sonuc

        if sonuc is None:
            st.markdown("""
            <div class="kart">
              <div class="kart-baslik">Henüz içerik üretilmedi</div>
              <p>Soldaki kutuya ürününüzü anlatıp <b>İçerik Üret</b> düğmesine basın.
              Size iki ayrı metin hazırlayacağız:</p><br>
              <p>📱 <b>Instagram gönderisi</b> — kısa, dikkat çeken, hikâyenizi anlatan<br>
              🛍️ <b>Shopier açıklaması</b> — aranınca bulunan, bilgi veren</p>
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
                if st.button("✓   Onayla", use_container_width=True):
                    st.success("Onaylandı! Aşağıdan kopyalayabilirsiniz.")
            with b2:
                st.download_button("⬇  Metinleri indir",
                                   data=f"INSTAGRAM\n{ig}\n\nSHOPIER\n{sh}",
                                   file_name="uretken_kadin_icerik.txt",
                                   use_container_width=True)

            with st.expander("📋  Kopyalamak için tıklayın"):
                st.caption("Instagram gönderisi"); st.code(ig, language=None)
                st.caption("Shopier açıklaması"); st.code(sh, language=None)

            kapsam, toplam, klise, benzerlik = olcumler(ig, sh, kategori)
            st.markdown("<br>", unsafe_allow_html=True)
            metrik_satiri([(f"{kapsam}/{toplam}", "SEO anahtar kelime"),
                           (str(klise), "klişe ifade"),
                           (f"{benzerlik:.2f}", "kanal benzerliği")])

            # ---------- KALİTE ÖN-FİLTRESİ (HITL yardımcısı) ----------
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
                st.caption("Bu bir yardımcı tahmindir (içerik kalite modeli), "
                           "karar değil. Metni siz onaylarsınız.")

            # ---------------- EK İÇERİKLER ----------------
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
                                anlatim=st.session_state.anlatim_metni,
                                kategori=kategori)
                        except Exception as hata:
                            st.error(f"Rehber üretilemedi: {hata}")

            if st.session_state.get("reels"):
                with st.expander("🎬  Reels / TikTok çekim planı", expanded=True):
                    st.markdown(st.session_state.reels)
                    st.download_button("⬇  Senaryoyu indir",
                                       data=st.session_state.reels,
                                       file_name="reels_senaryosu.md",
                                       key="ind_reels")
            if st.session_state.get("foto"):
                with st.expander("📸  Fotoğraf çekim rehberi", expanded=True):
                    st.markdown(st.session_state.foto)
                    st.download_button("⬇  Rehberi indir",
                                       data=st.session_state.foto,
                                       file_name="fotograf_rehberi.md",
                                       key="ind_foto")

    st.markdown('<div class="ifsa">Bu içerik yapay zekâ ile üretilmiştir · '
                'yayınlamadan önce okuyup düzenleyin — son karar her zaman sizindir'
                '</div>', unsafe_allow_html=True)


# ===========================================================================
# 2 — KARŞILAŞTIR
# ===========================================================================
with s_karsi:
    st.markdown("### ⚖️ Prompt tekniklerini karşılaştırın")
    st.write("Aynı anlatım, üç farklı yöntemle işlenir. Hangi yaklaşımın daha iyi "
             "sonuç verdiğini yan yana görebilirsiniz — bu karşılaştırma proje "
             "raporundaki *prompt tasarımı* bölümünün kanıtıdır.")

    k_anlatim = st.text_area(
        "Karşılaştırılacak anlatım", height=110,
        value=ORNEKLER[0][2],
        help="Üç teknik de bu metin üzerinde çalıştırılacak.")
    kk1, kk2 = st.columns([1, 2])
    with kk1:
        k_kategori = st.selectbox("Kategori", list(prompts.KATEGORI_KELIMELERI.keys()),
                                  key="karsi_kat")

    if st.button("⚖️  Üç tekniği de çalıştır", type="primary"):
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
            ilerheme_bitti = ilerleme.empty()
            st.session_state.karsilastirma = (sonuclar, k_kategori)

    if st.session_state.karsilastirma:
        sonuclar, k_kat = st.session_state.karsilastirma
        basliklar = TEKNIK_ADLARI
        kolonlar = st.columns(3, gap="medium")
        for kol, (tkn, sonuc) in zip(kolonlar, sonuclar.items()):
            with kol:
                st.markdown(f'<div class="kart-baslik">{basliklar[tkn]}</div>',
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
            st.markdown("#### 📈 Özet karşılaştırma")
            satirlar = []
            for tkn, sonuc in basarililar.items():
                kapsam, toplam, klise, benzerlik = olcumler(
                    sonuc.instagram, sonuc.shopier, k_kat)
                satirlar.append({
                    "Teknik": basliklar[tkn],
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
    st.markdown("### 🎙️ Kendi üslubunuzu öğretin")
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
        kaydet = st.form_submit_button("🎙️  Ton profilimi kaydet", type="primary")

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
        st.markdown("#### ✅ Aktif ton profiliniz")
        for i, ornek in enumerate(st.session_state.uslup_ornekleri, 1):
            st.markdown(f'<div class="kart"><div class="kart-baslik">Örnek {i}</div>'
                        f'<p>{ornek}</p></div>', unsafe_allow_html=True)
        if st.button("🗑  Ton profilini sil"):
            st.session_state.uslup_ornekleri = []
            st.rerun()
    else:
        st.info("Şu an ton profiliniz yok — varsayılan örnekler kullanılıyor. "
                "Kendi metinlerinizi eklerseniz sonuçlar size çok daha çok benzer.")


# ===========================================================================
# 4 — TOPLU ÜRETİM
# ===========================================================================
with s_toplu:
    st.markdown("### 📦 Birden fazla ürün için tek seferde içerik")
    st.write("Çok ürününüz varsa hepsini tek tek yazmanıza gerek yok. "
             "Ürün anlatımlarınızı içeren bir **CSV dosyası** yükleyin, "
             "tümü için içerik üretelim.")

    st.markdown('<div class="kart"><div class="kart-baslik">📄 Dosya biçimi</div>'
                '<p>CSV dosyanızda <b>anlatim</b> sütunu bulunmalı. İsteğe bağlı '
                'olarak <b>kategori</b> sütunu da ekleyebilirsiniz.</p></div>',
                unsafe_allow_html=True)

    ornek_csv = "anlatim,kategori\nEl örgüsü bebek battaniyesi yapıyorum…,Tekstil / El sanatı\n"
    st.download_button("⬇  Örnek CSV şablonunu indir", data=ornek_csv,
                       file_name="ornek_sablon.csv")

    yuklenen = st.file_uploader("CSV dosyanızı seçin", type=["csv"])
    t_kategori = st.selectbox("Varsayılan kategori (dosyada yoksa kullanılır)",
                              list(prompts.KATEGORI_KELIMELERI.keys()),
                              key="toplu_kat")

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
            if st.button(f"📦  {len(satirlar)} ürün için içerik üret", type="primary"):
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
    st.markdown("### 📁 Bu oturumda ürettikleriniz")
    if not st.session_state.gecmis:
        st.info("Henüz içerik üretmediniz. **İçerik Üret** sekmesinden başlayın.")
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
        if st.button("🗑  Geçmişi temizle"):
            st.session_state.gecmis = []
            st.rerun()


# ===========================================================================
# 6 — PANEL
# ===========================================================================
with s_panel:
    st.markdown("### 📊 Test sonuçları paneli")
    st.write("`ciktilar/` klasöründeki toplu test sonuçları — projenin ölçülebilir "
             "kanıtı. Her çalıştırma ayrı bir dosyaya kaydedilir.")

    dosyalar = sorted(glob.glob(os.path.join(KOK, "ciktilar", "*.csv")), reverse=True)
    if not dosyalar:
        st.info("Henüz toplu test çalıştırılmamış.\n\n"
                "Terminalden `python src/toplu_test.py` komutuyla çalıştırabilirsiniz.")
    else:
        secilen = st.selectbox("Sonuç dosyası",
                               [os.path.basename(d) for d in dosyalar])
        yol = os.path.join(KOK, "ciktilar", secilen)
        with open(yol, encoding="utf-8-sig") as f:
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
                              "Shopier": ort("sh_kelime")}, height=260, color=YESIL)

            with st.expander("📄  Ham veriyi göster"):
                st.dataframe(satirlar, use_container_width=True, hide_index=True)

    # ---------- İÇERİK KALİTE MODELİ ----------
    st.divider()
    st.markdown("### 🤖 İçerik kalite modeli")
    st.write("İçeriğin *onaya hazır* mı yoksa *revizyon gerek* mi olduğunu kestiren "
             "sınıflandırıcı (HITL ön-filtresi). Metrikler prototip veri setinde "
             "hesaplanmıştır; saha pilotunda güncellenecektir.")
    metrik_yolu = os.path.join(KOK, "ciktilar", "model", "metrikler.json")
    if not os.path.exists(metrik_yolu):
        st.info("Model henüz eğitilmemiş.\n\n"
                "Terminalden: `python src/kalite_veri_uret.py` sonra "
                "`python src/kalite_egit.py`")
    else:
        import json as _json
        with open(metrik_yolu, encoding="utf-8") as f:
            m = _json.load(f)
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
    st.markdown("### 💡 Üç adımda içeriğiniz hazır")
    st.write("")
    a1, a2, a3 = st.columns(3, gap="medium")
    for kol, no, baslik, aciklama in [
        (a1, "1", "Siz anlatın",
         "Ürününüzü kendi cümlelerinizle yazın. Teknik bilgi, pazarlama dili ya da "
         "özel bir yazım biçimi gerekmez — nasıl konuşuyorsanız öyle yazın."),
        (a2, "2", "Yapay zekâ düzenlesin",
         "Anlatımınız iki farklı kanala uygun metne dönüştürülür: Instagram için "
         "kısa ve dikkat çekici, Shopier için aranınca bulunan bir metin."),
        (a3, "3", "Siz onaylayın",
         "Metinleri okur, beğenmediğiniz yeri değiştirir ve onaylarsınız. Sizin "
         "onayınız olmadan hiçbir içerik kullanılmaz."),
    ]:
        kol.markdown(f"""
        <div class="kart" style="min-height: 215px;">
          <div class="adim"><div class="adim-no">{no}</div>
          <div class="adim-yazi">{baslik.upper()}</div></div>
          <p>{aciklama}</p>
        </div>""", unsafe_allow_html=True)

    st.write("")
    st.markdown("#### Neden iki ayrı metin?")
    n1, n2 = st.columns(2, gap="medium")
    n1.markdown("""
    <div class="kart"><div class="kart-baslik">📱 Instagram gönderisi</div>
      <p><b>Amacı:</b> kaydırırken durdurmak.<br><br>
      Kısa cümleler, sizin sesiniz ve ürününüzün en ilginç detayıyla başlayan bir
      açılış. Malzeme listesi burada yer almaz.</p></div>""", unsafe_allow_html=True)
    n2.markdown("""
    <div class="kart"><div class="kart-baslik">🛍️ Shopier ürün açıklaması</div>
      <p><b>Amacı:</b> arayan kişinin bulması.<br><br>
      Ürünün adı, malzemesi, süresi ve kime uygun olduğu açıkça yazılır. İnsanların
      aramada kullandığı kelimeler doğal biçimde geçer.</p></div>""",
                unsafe_allow_html=True)

    st.write("")
    st.markdown("#### Diğer özellikler")
    d1, d2, d3 = st.columns(3, gap="medium")
    for kol, ikon, ad, aciklama in [
        (d1, "🎙️", "Sesli anlatım",
         "Yazmak zor geliyorsa konuşun — sesiniz metne çevrilir, kelimeleriniz korunur."),
        (d2, "📦", "Toplu Üretim",
         "CSV yükleyin, tüm ürünleriniz için tek seferde içerik alın."),
        (d3, "🎬", "Reels ve fotoğraf",
         "Video çekim planı ve ürününüze özel fotoğraf rehberi alın."),
    ]:
        kol.markdown(f'<div class="kart" style="min-height:120px;">'
                     f'<div class="kart-baslik">{ikon}  {ad}</div>'
                     f'<p>{aciklama}</p></div>', unsafe_allow_html=True)


# ===========================================================================
# 8 — ETİK
# ===========================================================================
with s_etik:
    st.markdown("### 🛡️ Güçlendiriyoruz, sömürmüyoruz")
    st.write("Yapay zekâyı burada bir *yazar* olarak değil, sizin sesinizi görünür "
             "kılan bir *araç* olarak kullanıyoruz.")
    st.write("")

    ilkeler = [
        ("🔍", "Şeffaflık",
         "Her içerikte yapay zekâ ile üretildiği açıkça belirtilir. Bunu gizlemeyiz."),
        ("🎙️", "Otantiklik",
         "Sizin anlatımınız temel alınır. Yapay zekâ hikâye uydurmaz, kullandığınız "
         "somut kelimeleri korur."),
        ("⚖️", "Abartısızlık",
         "“Mucize”, “garanti”, “en iyi” gibi ispatsız iddialar üretilmez. Gıda "
         "ürünlerinde sağlık iddiası kurulmaz."),
        ("✋", "İnsan onayı",
         "Hiçbir içerik sizin onayınız olmadan kullanılmaz. Son karar her zaman "
         "üreticidedir (human-in-the-loop)."),
        ("🔒", "Veri gizliliği",
         "Anlatımınız yalnızca içerik üretmek için kullanılır. KVKK kapsamında açık "
         "rıza olmadan saklanmaz veya paylaşılmaz."),
        ("🌱", "Önyargı kontrolü",
         "Üretilen metinler klişe ve kalıplaşmış dil açısından ölçülür; tek tip "
         "anlatım dayatılmaz."),
    ]
    for i in range(0, len(ilkeler), 2):
        kol1, kol2 = st.columns(2, gap="medium")
        for kol, (ikon, baslik, aciklama) in zip((kol1, kol2), ilkeler[i:i + 2]):
            kol.markdown(f'<div class="kart" style="min-height:128px;">'
                         f'<div class="kart-baslik">{ikon}  {baslik}</div>'
                         f'<p>{aciklama}</p></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🔒 KVKK — Kişisel verileriniz")
    st.write("Sesli/yazılı anlatımınız içerik üretmek için Google Gemini'ye "
             "gönderilir. Bunun ne anlama geldiğini açıkça anlatıyoruz:")
    for i in range(0, len(kvkk.POLITIKA_MADDELERI), 2):
        kol1, kol2 = st.columns(2, gap="medium")
        for kol, (baslik, aciklama) in zip((kol1, kol2),
                                           kvkk.POLITIKA_MADDELERI[i:i + 2]):
            kol.markdown(f'<div class="kart" style="min-height:130px;">'
                         f'<div class="kart-baslik">{baslik}</div>'
                         f'<p>{aciklama}</p></div>', unsafe_allow_html=True)

    st.markdown('<div class="altbilgi">Üretken Kadın · Emeğin dijital sesi</div>',
                unsafe_allow_html=True)
