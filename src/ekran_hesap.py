# -*- coding: utf-8 -*-
"""
Üretken Kadın — giriş / kayıt ve Hesabım ekranları (Streamlit)

Oturum: st.session_state.kullanici = {"id", "eposta", "ad", "olusturma"}; giriş yoksa None.
Kalıcı veri akışı:
  • Girişte hesap.verileri_yukle → içerikler, takvim ve ton profili oturuma alınır.
  • app.py her çizimin sonunda kaydet_gerekirse() çağırır: yalnızca değişiklik varsa veritabanına yazar.
  • Çıkış ve hesap silmede oturum, app.py'nin başında (hiçbir bileşen çizilmeden) temizlenir.
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import streamlit as st

import ekran_araclar
import hesap
import kvkk
import takvim

KORUMASIZ_EKRANLAR = ("karsilama", "yardim", "api", "giris")
GIRIS_SEKMELERI = ["🔑 Giriş yap", "✨ Kayıt ol"]
VARSAYILANLAR = {"kullanici": None, "giris_sonrasi": None, "veri_ozeti": None,
                 "giris_sekme": GIRIS_SEKMELERI[0]}


@dataclass
class Baglam:
    ust_bar: Callable[[], None]
    git: Callable[[str], None]


# ---------------------------------------------------------------------------
# Oturum
# ---------------------------------------------------------------------------
def oturumu_baslat(k: hesap.Kullanici) -> None:
    icerikler, plan, uslup = hesap.verileri_yukle(k.id)
    st.session_state.kullanici = {"id": k.id, "eposta": k.eposta, "ad": k.ad,
                                  "olusturma": k.olusturma.isoformat()}
    st.session_state.gecmis = icerikler
    st.session_state.plan = plan
    st.session_state.uslup_ornekleri = uslup
    st.session_state.veri_ozeti = hesap.degisiklik_ozeti(icerikler, plan, uslup)
    st.session_state.giris_sonrasi = None


def oturumu_kapat(mesaj: str) -> None:
    """Oturum bir sonraki çizimin başında temizlenir (app.py), sonra karşılamaya dönülür."""
    st.session_state["_oturumu_kapat"] = mesaj
    st.rerun()


def kaydet_gerekirse() -> None:
    k = st.session_state.get("kullanici")
    if not k:
        return
    gecmis, plan, uslup = st.session_state.gecmis, st.session_state.plan, st.session_state.uslup_ornekleri
    ozet = hesap.degisiklik_ozeti(gecmis, plan, uslup)
    if ozet == st.session_state.get("veri_ozeti"):
        return
    try:
        hesap.verileri_kaydet(k["id"], hesap.belge(gecmis, plan, uslup))
        st.session_state.veri_ozeti = ozet
    except ValueError as hata:
        st.toast(str(hata), icon="⚠️")
    except Exception as hata:
        st.toast(f"İçerikleriniz şu an kaydedilemedi; bir sonraki değişiklikte yeniden denenecek. "
                 f"({type(hata).__name__})", icon="⚠️")


def _kalicilik_uyarisi() -> None:
    if os.getenv("RENDER") and not hesap.kalici_mi():
        st.warning("⚠️ Veritabanı henüz bağlanmadı: bu sunucuda açılan hesaplar ve içerikler bir sonraki "
                   "güncellemede silinir. (Proje ekibi için: Render'da DATABASE_URL tanımlanmalı.)")


# ---------------------------------------------------------------------------
# Giriş / kayıt
# ---------------------------------------------------------------------------
def giris_ekrani(b: Baglam) -> None:
    b.ust_bar()
    st.markdown('<div class="ekran-baslik">Hoş geldiniz <span class="yumak" aria-hidden="true">👋</span></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">Araçları kullanmak ve hazırladığınız içerikleri saklamak için '
                'hesabınıza girin. Hesabınız yoksa bir dakikada oluşturabilirsiniz.</div>',
                unsafe_allow_html=True)
    if st.session_state.giris_sonrasi:
        st.info("🔒 Bu bölüm için önce giriş yapın; giriş yapınca kaldığınız yere döneceksiniz.")
    _kalicilik_uyarisi()
    hedef = st.session_state.giris_sonrasi or "araclar"

    if ekran_araclar.sekme_kutusu("giris_sekme", GIRIS_SEKMELERI) == GIRIS_SEKMELERI[0]:
        with st.form("giris_formu", border=False):
            eposta = st.text_input("E-posta", key="giris_eposta", autocomplete="email",
                                   placeholder="ornek@eposta.com")
            sifre = st.text_input("Şifre", type="password", key="giris_sifre", autocomplete="current-password")
            gonder = st.form_submit_button("🔑 Giriş yap", type="primary", use_container_width=True)
        if gonder:
            try:
                with st.spinner("Giriş yapılıyor…"):
                    oturumu_baslat(hesap.giris_yap(eposta, sifre))
            except ValueError as hata:
                st.error(str(hata))
            except Exception as hata:
                st.error(f"Şu an giriş yapılamıyor; biraz sonra tekrar deneyin. ({type(hata).__name__})")
            else:
                st.toast(f"Hoş geldiniz, {st.session_state.kullanici['ad']} 🌸")
                b.git(hedef)
        st.caption("Şifrenizi unuttuysanız proje ekibine yazın; size geçici bir şifre verelim.")
        return

    with st.form("kayit_formu", border=False):
        ad = st.text_input("Adınız", max_chars=60, key="kayit_ad", autocomplete="name", placeholder="Ayşe")
        eposta = st.text_input("E-posta", key="kayit_eposta", autocomplete="email",
                               placeholder="ornek@eposta.com")
        sifre = st.text_input(f"Şifre (en az {hesap.SIFRE_EN_AZ} karakter)", type="password", key="kayit_sifre",
                              autocomplete="new-password")
        tekrar = st.text_input("Şifre (tekrar)", type="password", key="kayit_tekrar", autocomplete="new-password")
        with st.expander("🔒 Hesabınız ve verileriniz (KVKK) — okumak için açın"):
            st.markdown(kvkk.HESAP_AYDINLATMA)
        onay = st.checkbox(kvkk.HESAP_RIZA_ETIKETI, key="kayit_onay")
        gonder = st.form_submit_button("✨ Hesabımı oluştur", type="primary", use_container_width=True)
    if gonder:
        try:
            with st.spinner("Hesabınız oluşturuluyor…"):
                oturumu_baslat(hesap.kayit_ol(eposta, ad, sifre, tekrar, onay))
        except ValueError as hata:
            st.error(str(hata))
        except Exception as hata:
            st.error(f"Şu an hesap oluşturulamıyor; biraz sonra tekrar deneyin. ({type(hata).__name__})")
        else:
            st.toast(f"Hesabınız hazır, {st.session_state.kullanici['ad']} 🎉")
            b.git(hedef)


# ---------------------------------------------------------------------------
# Hesabım
# ---------------------------------------------------------------------------
def _tarih(iso: str) -> str:
    try:
        an = datetime.fromisoformat(iso).astimezone(takvim.TR)
        return f"{an.day} {takvim.AYLAR[an.month - 1]} {an.year}"
    except (TypeError, ValueError):
        return "—"


def hesabim_ekrani(b: Baglam) -> None:
    b.ust_bar()
    k = st.session_state.kullanici
    st.markdown('<div class="ekran-baslik">Hesabım <span class="yumak" aria-hidden="true">👤</span></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ekran-alt">İçerikleriniz, takviminiz ve ton profiliniz hesabınızda otomatik '
                'olarak saklanır.</div>', unsafe_allow_html=True)
    _kalicilik_uyarisi()
    satirlar = [("Ad", k["ad"]), ("E-posta", k["eposta"]), ("Üyelik", _tarih(k["olusturma"])),
                ("Hazır içerik", str(len(st.session_state.gecmis))),
                ("Planlı paylaşım", str(len(st.session_state.plan)))]
    st.markdown('<div class="hesap-karti">' + "".join(
        f'<div class="satir"><span class="etiket">{e}</span><b>{html.escape(d)}</b></div>' for e, d in satirlar)
        + "</div>", unsafe_allow_html=True)

    st.download_button("⬇️ Verilerimi indir", hesap.belge(st.session_state.gecmis, st.session_state.plan,
                                                          st.session_state.uslup_ornekleri).encode("utf-8"),
                       file_name=f"uretken_kadin_verilerim_{takvim.simdi():%Y-%m-%d}.json",
                       mime="application/json", use_container_width=True, key="hesap_indir")
    st.caption("İndirdiğiniz dosyayı 🏠 Panom → Kaydet / yükle bölümünden geri yükleyebilirsiniz.")

    with st.expander("🔒 Şifremi değiştir"):
        with st.form("sifre_formu", border=False):
            eski = st.text_input("Mevcut şifre", type="password", key="sifre_eski", autocomplete="current-password")
            yeni = st.text_input("Yeni şifre", type="password", key="sifre_yeni", autocomplete="new-password")
            tekrar = st.text_input("Yeni şifre (tekrar)", type="password", key="sifre_tekrar",
                                   autocomplete="new-password")
            degistir = st.form_submit_button("🔒 Şifremi değiştir", use_container_width=True)
        if degistir:
            try:
                hesap.sifre_degistir(k["id"], eski, yeni, tekrar)
                st.success("Şifreniz değiştirildi.")
            except ValueError as hata:
                st.error(str(hata))
            except Exception as hata:
                st.error(f"Şu an değiştirilemedi; biraz sonra tekrar deneyin. ({type(hata).__name__})")

    if st.button("🚪 Çıkış yap", use_container_width=True, key="hesap_cikis"):
        kaydet_gerekirse()
        oturumu_kapat("Çıkış yaptınız. Görüşmek üzere 🌸")

    with st.expander("🗑️ Hesabımı sil"):
        st.warning("Hesabınız ve hazırladığınız **tüm içerikler, takviminiz ve ton profiliniz kalıcı olarak "
                   "silinir.** Bu işlem geri alınamaz. İsterseniz önce yukarıdan verilerinizi indirin.")
        with st.form("silme_formu", border=False):
            sifre = st.text_input("Şifreniz", type="password", key="silme_sifre", autocomplete="current-password")
            onay = st.text_input("Onaylamak için büyük harflerle SİL yazın", key="silme_onay")
            sil = st.form_submit_button("🗑️ Hesabımı kalıcı olarak sil", use_container_width=True)
        if sil:
            if onay.strip() not in ("SİL", "SIL"):
                st.error("Onaylamak için SİL yazın.")
            else:
                try:
                    hesap.hesabi_sil(k["id"], sifre)
                except ValueError as hata:
                    st.error(str(hata))
                except Exception as hata:
                    st.error(f"Şu an silinemedi; biraz sonra tekrar deneyin. ({type(hata).__name__})")
                else:
                    oturumu_kapat("Hesabınız ve tüm verileriniz silindi.")
