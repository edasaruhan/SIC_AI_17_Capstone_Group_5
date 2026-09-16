# -*- coding: utf-8 -*-
"""
Üretken Kadın — API başvuru formu ("Firmalar için API" sayfası) ve yönetici başvuru listesi (Hesabım).
"""

from __future__ import annotations

import html

import streamlit as st

import basvuru
import kvkk
import takvim

_TUZAK_CSS = """<style>
/* Botlar için tuzak alan: insan görmez, doldurulursa başvuru sessizce yok sayılır */
.st-key-basvuru_tuzak { position:absolute !important; left:-10000px !important; height:0 !important;
  overflow:hidden !important; }
.basvuru-kart { background:#fff; border:2.5px solid var(--ink); border-radius:18px; padding:.8rem 1rem;
  box-shadow:var(--golge-sm); margin:.2rem 0 .6rem; }
.basvuru-kart .ust { display:flex; flex-wrap:wrap; justify-content:space-between; gap:.3rem .8rem; }
.basvuru-kart b { font-family:'Baloo 2'; font-size:1.1rem; }
.basvuru-kart .kucuk { color:var(--muted); font-size:.85rem; font-weight:700; }
.basvuru-kart p { margin:.4rem 0 0; font-size:.92rem; white-space:pre-wrap; overflow-wrap:anywhere; }
</style>"""


def basvuru_formu() -> None:
    st.markdown(_TUZAK_CSS, unsafe_allow_html=True)
    st.markdown('<div class="kart-baslik" id="basvuru">📝 API anahtarı için başvurun</div>', unsafe_allow_html=True)
    no = st.session_state.get("basvuru_no")
    if no:
        st.success(f"🎉 Başvurunuz alındı. Başvuru numaranız: **{no}**. Ekibimiz başvurunuzu inceleyip "
                   "yazdığınız e-posta adresine dönüş yapacak.")
        if st.button("Yeni bir başvuru yap", key="basvuru_yeni"):
            st.session_state.basvuru_no = None
            st.rerun()
        return
    st.caption("Anahtarlar otomatik verilmez: her başvuruyu ekibimiz inceler, uygun kullanımlar için size "
               "özel anahtar ve günlük kota tanımlar.")
    with st.form("basvuru_formu", border=False):
        k1, k2 = st.columns(2)
        kurum = k1.text_input("Kurum adı *", max_chars=120, key="basvuru_kurum")
        tur = k2.selectbox("Kurum türü *", basvuru.KURUM_TURLERI, index=None, placeholder="Seçin",
                           key="basvuru_tur")
        k3, k4 = st.columns(2)
        yetkili = k3.text_input("Yetkili adı soyadı *", max_chars=80, key="basvuru_yetkili")
        eposta = k4.text_input("İş e-postası *", key="basvuru_eposta", autocomplete="email",
                               placeholder="ad@kurum.com")
        web = st.text_input("Web sitesi", max_chars=200, key="basvuru_web", placeholder="www.kurum.com")
        amac = st.text_area("API'yi nasıl kullanmayı planlıyorsunuz? *", max_chars=2000, height=120,
                            key="basvuru_amac",
                            placeholder="Örnek: Pazaryerimizdeki kadın üreticilerin ürün açıklamalarını "
                                        "hazırlamasına yardım etmek istiyoruz; metinler üreticiye "
                                        "onaylatıldıktan sonra yayımlanacak.")
        hacim = st.selectbox("Aylık tahmini istek sayısı *", basvuru.AYLIK_HACIMLER, index=None,
                             placeholder="Seçin", key="basvuru_hacim")
        tuzak = st.text_input("Bu alanı boş bırakın", key="basvuru_tuzak", label_visibility="collapsed")
        with st.expander("🔒 Başvuru bilgileriniz (KVKK) — okumak için açın"):
            st.markdown(kvkk.BASVURU_AYDINLATMA)
        onay = st.checkbox(kvkk.BASVURU_RIZA_ETIKETI, key="basvuru_onay")
        gonder = st.form_submit_button("📨 Başvuruyu gönder", type="primary", use_container_width=True)
    if not gonder:
        return
    if tuzak:                                   # bot: hata göstermeden başarılı gibi davran
        st.session_state.basvuru_no = "ALINDI"
        st.rerun()
    try:
        st.session_state.basvuru_no = basvuru.basvuru_yap(kurum, tur or "", yetkili, eposta, web, amac,
                                                          hacim or "", onay)
    except ValueError as hata:
        st.error(str(hata))
    except Exception as hata:
        st.error(f"Başvuru şu an kaydedilemedi; biraz sonra tekrar deneyin. ({type(hata).__name__})")
    else:
        st.rerun()


def yonetici_paneli() -> None:
    """Yalnızca YONETICI_EPOSTALARI'ndaki hesaplara (çağıran taraf kontrol eder)."""
    with st.expander("📨 API başvuruları (yönetici)"):
        try:
            kayitlar = basvuru.liste()
        except Exception as hata:
            st.error(f"Başvurular okunamadı. ({type(hata).__name__})")
            return
        if not kayitlar:
            st.caption("Henüz başvuru yok.")
            return
        yeni = sum(1 for x in kayitlar if x.durum == "yeni")
        st.caption(f"{len(kayitlar)} başvuru · {yeni} yeni. Onayladığınız firmaya anahtarı "
                   "`python src/api_guvenlik.py` ile üretip e-postayla iletin.")
        for x in kayitlar:
            no = x.id[:8].upper()
            tarih = x.olusturma.astimezone(takvim.TR)
            web = f" · {html.escape(x.web)}" if x.web else ""
            st.markdown(
                f'<div class="basvuru-kart"><div class="ust"><b>{html.escape(x.kurum)}</b>'
                f'<span class="kucuk">{basvuru.DURUMLAR[x.durum]} · #{no} · {tarih:%d.%m.%Y %H:%M}</span></div>'
                f'<div class="kucuk">{html.escape(x.kurum_turu)} · {html.escape(x.yetkili)} · '
                f'{html.escape(x.eposta)}{web} · aylık {html.escape(x.aylik_hacim)}</div>'
                f'<p>{html.escape(x.amac)}</p></div>', unsafe_allow_html=True)
            k1, k2 = st.columns([2, 1])
            durumlar = list(basvuru.DURUMLAR)
            secim = k1.selectbox("Durum", durumlar, index=durumlar.index(x.durum), format_func=basvuru.DURUMLAR.get,
                                 key=f"basvuru_durum_{x.id}", label_visibility="collapsed")
            if secim != x.durum:
                basvuru.durum_degistir(x.id, secim)
                st.rerun()
            if k2.button("🗑️ Sil", key=f"basvuru_sil_{x.id}", use_container_width=True):
                basvuru.sil(x.id)
                st.rerun()
