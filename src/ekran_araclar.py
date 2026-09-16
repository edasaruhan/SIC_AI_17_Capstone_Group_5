# -*- coding: utf-8 -*-
"""
Üretken Kadın — araç ekranları (Streamlit): Araç kutusu, Görsel stüdyosu, Satış araçları

app.py'nin ortak parçaları (üst bar, gezinme, ayarlar) `Baglam` ile verilir; böylece bu ekranlar
ayrı dosyada durur ve app.py'ye döngüsel bağımlılık gerekmez. İş mantığı gorsel.py ve satis.py'dedir;
bu dosya yalnızca arayüzdür.

Sekmeler st.tabs yerine seçim kutusuyla (segmented control) yapılır: böylece başka ekrandan
("Bu ürün için: İlan") doğrudan istenen sekmeye gidilebilir.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import asdict, dataclass
from typing import Callable

import streamlit as st

import gorsel
import kvkk
import prompts
import satis
import takvim
import uret

GS_SEKMELER = ["✨ Güzelleştir", "🔍 Fotoğraftan anlatım", "🖼️ Paylaşım görseli", "📒 Katalog"]
SATIS_SEKMELER = ["💰 Fiyat hesapla", "💬 Müşteriye cevap", "🛒 Pazaryeri ilanı", "🎉 Özel günler"]

# app.py oturum varsayılanlarına eklenir
VARSAYILANLAR = {
    "gs_sekme": GS_SEKMELER[0], "satis_sekme": SATIS_SEKMELER[0], "secili_kayit_id": None,
    "gs_foto": None, "gs_foto_kimlik": None, "gs_duzeltilmis": None, "gs_yz": None,
    "gs_anlatim": None, "gs_paylasim": None, "kat_pdf": None,
    "mc_cevap": None, "ilan_sonuc": None, "ilan_ceviri": None, "og_oneri": None, "ozel_gunler_ek": [],
}

ARACLAR = [
    ("anlat", "✍️", "İçerik yaz", "Anlatımınızdan Instagram ve satış sayfası metni", "mavi"),
    ("gorsel", "📸", "Görsel stüdyosu", "Fotoğraf güzelleştir, paylaşım görseli, katalog", "sari"),
    ("satis", "💰", "Satış araçları", "Fiyat hesapla, müşteriye cevap, ilan, özel günler", "pembe"),
    ("pano", "🏠", "Panom", "İçerikleriniz ve paylaşım takviminiz", "yesil"),
]


@dataclass
class Baglam:
    ust_bar: Callable[[], None]
    git: Callable[[str], None]
    kayit_bul: Callable[[str | None], dict | None]
    kategoriler: dict[str, str]           # kullanıcıya görünen etiket → prompts anahtarı
    ozenli: bool


# ---------------------------------------------------------------------------
# Ortak parçalar
# ---------------------------------------------------------------------------
def _baslik(metin: str, ikon: str, alt: str) -> None:
    st.markdown(f'<div class="ekran-baslik">{metin} <span class="yumak" aria-hidden="true">{ikon}</span></div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="ekran-alt">{alt}</div>', unsafe_allow_html=True)


def _hata_goster(hata: Exception, ne: str = "hazırlanamadı") -> None:
    if isinstance(hata, ValueError):
        st.warning(str(hata))
    elif isinstance(hata, RuntimeError) and "GEMINI_API_KEY" in str(hata):
        st.error("Yapay zekâ anahtarı tanımlı değil; uygulama yöneticisine haber verin.")
    elif uret._gecici_hata_mi(hata):
        st.warning("Yapay zekâ şu an yoğun; biraz sonra tekrar deneyin.")
    else:
        st.error(f"Şu an {ne}; biraz sonra tekrar deneyin. ({type(hata).__name__})")


def sekme_sec(anahtar: str, sekme: str) -> None:
    """Başka ekrandan belirli bir sekmeyi açmak için (ör. sonuç ekranı → "İlan")."""
    st.session_state[anahtar] = sekme
    st.session_state.pop(f"{anahtar}_secim", None)        # seçim kutusu yeni varsayılanla açılsın


def sekme_kutusu(anahtar: str, sekmeler: list[str]) -> str:
    """
    Sekme seçimi. Seçili sekme `anahtar` altında (widget olmayan durum) tutulur; seçim kutusu ona
    `default` ile bağlanır. Değeri widget anahtarına önceden yazmak Streamlit'te seçili görünümü
    ekrana yansıtmıyordu.
    """
    if st.session_state.get(anahtar) not in sekmeler:
        st.session_state[anahtar] = sekmeler[0]
    kutu = f"{anahtar}_secim"

    def degisti() -> None:
        if st.session_state.get(kutu):
            st.session_state[anahtar] = st.session_state[kutu]

    secim = st.segmented_control("Bölüm", sekmeler, default=st.session_state[anahtar], key=kutu,
                                 on_change=degisti, label_visibility="collapsed")
    return secim or st.session_state[anahtar]


def _urun_kaynagi(b: Baglam, anahtar: str, etiket: str = "Hangi ürün için?",
                  zorunlu: bool = True) -> tuple[str, str, dict | None]:
    """Hazırlanmış içeriklerden birini seçtirir ya da yeni anlatım yazdırır: (anlatım, kategori, kayıt)."""
    gecmis = st.session_state.gecmis
    adlar = {k["id"]: f"📦 {takvim.baslik_uret(k['anlatim'])}" for k in gecmis}
    adlar["__yeni__"] = "✍️ Başka bir ürünü burada anlatacağım" if zorunlu else "✍️ Ürün seçmeden devam et"
    secenekler = list(adlar)
    secili = st.session_state.get("secili_kayit_id")
    secim = st.selectbox(etiket, secenekler, format_func=adlar.get, key=f"{anahtar}_urun",
                         index=secenekler.index(secili) if secili in adlar else 0)
    if secim != "__yeni__":
        kayit = b.kayit_bul(secim)
        return kayit["anlatim"], kayit.get("kategori") or "Tekstil / El sanatı", kayit
    anlatim = st.text_area("Ürün anlatımı", height=110, key=f"{anahtar}_anlatim",
                           placeholder="Örnek: El örgüsü bebek battaniyesi yapıyorum. Organik pamuk "
                                       "ipliği kullanıyorum, bir tanesi üç günümü alıyor.")
    etiketler = list(b.kategoriler)
    kat = st.pills("Kategori", etiketler, default=etiketler[0], key=f"{anahtar}_kat",
                   label_visibility="collapsed")
    return anlatim, b.kategoriler[kat or etiketler[0]], None


def arac_kartlari(b: Baglam, anahtar: str) -> None:
    for i in range(0, len(ARACLAR), 2):
        for kol, (ekran, ikon, ad, aciklama, renk) in zip(st.columns(2), ARACLAR[i:i + 2]):
            with kol:
                st.markdown(f'<div class="arac-karti {renk}"><div class="ikon" aria-hidden="true">{ikon}</div>'
                            f'<div class="ad">{ad}</div><p>{aciklama}</p></div>', unsafe_allow_html=True)
                if st.button(f"{ad} →", key=f"{anahtar}_{ekran}", use_container_width=True):
                    b.git(ekran)


# ===========================================================================
# ARAÇ KUTUSU
# ===========================================================================
def arac_kutusu(b: Baglam) -> None:
    b.ust_bar()
    _baslik("Araç kutunuz", "🧰", "Ne yapmak istersiniz? Bir araç seçin.")
    arac_kartlari(b, "kutu")


# ===========================================================================
# GÖRSEL STÜDYOSU
# ===========================================================================
def _kalite_karti(r: gorsel.KaliteRaporu) -> str:
    seviye = "iyi" if r.puan >= 80 else ("orta" if r.puan >= 50 else "zayif")
    iyi = "".join(f'<span class="cip">✓ {html.escape(e)}</span>' for e in r.iyi_yanlar)
    uyarilar = "".join(f"<li>{html.escape(u)}</li>" for u in r.uyarilar)
    govde = f"<ul>{uyarilar}</ul>" if uyarilar else "<p>Bu fotoğraf paylaşıma uygun görünüyor 👏</p>"
    return (f'<div class="kalite-kart"><div class="puan {seviye}"><b>{r.puan}</b><small>/100</small></div>'
            f'<div class="govde"><div class="kart-baslik" style="margin:0 0 .3rem">Fotoğraf kalitesi</div>'
            f'<div class="cipler">{iyi}</div>{govde}</div></div>')


def _once_sonra(once: bytes, sonra: bytes) -> None:
    k1, k2 = st.columns(2)
    k1.image(once, caption="Önce", use_container_width=True)
    k2.image(sonra, caption="Sonra", use_container_width=True)


def _foto_al() -> None:
    kaynak = st.segmented_control("Fotoğraf kaynağı", ["📁 Fotoğraf yükle", "📷 Kamerayla çek"],
                                  default="📁 Fotoğraf yükle", key="gs_kaynak",
                                  label_visibility="collapsed")
    if kaynak == "📷 Kamerayla çek":
        dosya = st.camera_input("Ürününüzün fotoğrafını çekin", key="gs_kamera")
    else:
        dosya = st.file_uploader("Ürün fotoğrafınız (JPG, PNG, WEBP · en fazla 10 MB)",
                                 type=["jpg", "jpeg", "png", "webp"], key="gs_dosya")
    st.caption("🔒 " + kvkk.FOTO_AYDINLATMA)
    if dosya is None:
        return
    bayt = dosya.getvalue()
    kimlik = hashlib.sha256(bayt).hexdigest()
    if kimlik == st.session_state.gs_foto_kimlik:
        return
    try:
        img = gorsel.foto_ac(bayt)
    except ValueError as hata:
        st.warning(str(hata))
        return
    st.session_state.update(gs_foto=gorsel.jpeg(img, 92), gs_foto_kimlik=kimlik, gs_duzeltilmis=None,
                            gs_yz=None, gs_anlatim=None, gs_paylasim=None)


def gorsel_studyosu(b: Baglam) -> None:
    b.ust_bar()
    _baslik("Görsel stüdyosu", "📸",
            "Telefonla çektiğiniz fotoğrafı güzelleştirin, fotoğraftan anlatım çıkarın, paylaşıma "
            "hazır görsel ve katalog hazırlayın.")
    sekme = sekme_kutusu("gs_sekme", GS_SEKMELER)
    if sekme == "📒 Katalog":
        _katalog(b)
        return

    _foto_al()
    if not st.session_state.gs_foto:
        st.markdown('<div class="bos"><div class="ik">📸</div><p>Başlamak için bir ürün fotoğrafı '
                    'yükleyin ya da çekin.</p></div>', unsafe_allow_html=True)
        return
    img = gorsel.foto_ac(st.session_state.gs_foto)
    st.image(st.session_state.gs_foto, width=320)
    st.markdown(_kalite_karti(gorsel.kalite_olc(img)), unsafe_allow_html=True)
    if st.button("🗑️ Fotoğrafı kaldır", key="gs_kaldir"):
        st.session_state.update({k: None for k in ("gs_foto", "gs_foto_kimlik", "gs_duzeltilmis", "gs_yz",
                                                   "gs_anlatim", "gs_paylasim")})
        st.rerun()

    if sekme == "✨ Güzelleştir":
        _guzellestir(img)
    elif sekme == "🔍 Fotoğraftan anlatım":
        _foto_anlatim(b, img)
    else:
        _paylasim_gorseli(b)


def _guzellestir(img) -> None:
    st.markdown('<div class="kart-baslik">✨ Hızlı düzeltme <span class="cip">ücretsiz</span></div>',
                unsafe_allow_html=True)
    st.caption("Işığı ve kontrastı dengeler, hafifçe keskinleştirir. Ürünün rengine dokunmaz.")
    kare = st.checkbox("Kare kırp (Instagram için)", key="gs_kare")
    if st.button("✨ Hızlı düzelt", key="gs_hizli", use_container_width=True):
        st.session_state.gs_duzeltilmis = gorsel.jpeg(gorsel.hizli_duzelt(img, kare=kare), 92)
    if st.session_state.gs_duzeltilmis:
        _once_sonra(st.session_state.gs_foto, st.session_state.gs_duzeltilmis)
        st.download_button("⬇️ Düzeltilmiş fotoğrafı indir", st.session_state.gs_duzeltilmis,
                           file_name="uretken_kadin_duzeltilmis.jpg", mime="image/jpeg",
                           key="gs_duz_indir", use_container_width=True)

    st.markdown('<div class="kart-baslik" style="margin-top:1.4rem">🪄 Arka planı değiştir '
                '<span class="cip">yapay zekâ</span></div>', unsafe_allow_html=True)
    st.caption("Ürününüz aynen kalır, yalnızca arka plan değişir. Bu özellik Google Gemini'nin "
               "ücretli katmanını gerektirir.")
    sahneler = list(prompts.ARKA_PLAN_SAHNELERI)
    sahne = st.pills("Sahne", sahneler, default=sahneler[0], key="gs_sahne",
                     label_visibility="collapsed") or sahneler[0]
    if st.button("🪄 Arka planı değiştir", key="gs_yz_btn", use_container_width=True):
        kaynak = gorsel.foto_ac(st.session_state.gs_duzeltilmis or st.session_state.gs_foto)
        with st.spinner("Yeni arka plan hazırlanıyor… (yarım dakikayı bulabilir)"):
            try:
                st.session_state.gs_yz = gorsel.jpeg(gorsel.arka_plan_degistir(kaynak, sahne), 92)
                st.session_state.gs_onay = False
            except gorsel.GorselKotaHatasi as hata:
                if hata.args and hata.args[0] == "ucretsiz":
                    st.info("🔒 **Bu özellik şu an kapalı.** Görsel üreten yapay zekâ modelleri Google "
                            "Gemini'nin ücretsiz katmanında kullanılamıyor. Proje ekibi Google AI "
                            "Studio'da faturalandırmayı açtığında bu düğme çalışır. O zamana kadar "
                            "**Hızlı düzeltme**'yi kullanabilirsiniz.")
                else:
                    st.warning("Görsel hazırlama kotası şu an dolu; biraz sonra tekrar deneyin.")
            except Exception as hata:
                _hata_goster(hata, "görsel hazırlanamadı")
    if st.session_state.gs_yz:
        _once_sonra(st.session_state.gs_duzeltilmis or st.session_state.gs_foto, st.session_state.gs_yz)
        if st.checkbox("Ürünümün değişmediğini kontrol ettim (şekli, rengi, deseni aynı)", key="gs_onay"):
            st.download_button("⬇️ Yeni fotoğrafı indir", st.session_state.gs_yz,
                               file_name="uretken_kadin_yz_duzenlendi.jpg", mime="image/jpeg",
                               key="gs_yz_indir", use_container_width=True)
            st.caption("Paylaşırken fotoğrafın yapay zekâ ile düzenlendiğini belirtmeniz önerilir.")
        else:
            st.caption("İndirmek için önce ürünün değişmediğini kontrol edin.")


def _foto_anlatim(b: Baglam, img) -> None:
    st.caption("Yapay zekâ fotoğrafa bakar ve yalnızca gördüğünü yazar; malzeme ya da süre gibi "
               "bilgileri size sorar.")
    etiketler = list(b.kategoriler)
    kat = st.pills("Ürün türü", etiketler, default=etiketler[0], key="gs_kat",
                   label_visibility="collapsed") or etiketler[0]
    if st.button("🔍 Fotoğrafa bak, anlatım taslağı çıkar", type="primary", key="gs_anlatim_btn",
                 use_container_width=True):
        with st.spinner("Fotoğrafınıza bakılıyor…"):
            try:
                st.session_state.gs_anlatim = asdict(gorsel.foto_anlatim_uret(img, b.kategoriler[kat],
                                                                             ozenli=b.ozenli))
            except Exception as hata:
                _hata_goster(hata)
    a = st.session_state.gs_anlatim
    if not a:
        return
    cipler = "".join(f'<span class="cip">{html.escape(x)}</span>' for x in a["gorunen_ozellikler"] + a["renkler"])
    st.markdown(f'<div class="kart"><div class="kart-baslik" style="margin-top:0">👀 Gördüklerim: '
                f'{html.escape(a["urun"])}</div><div class="cipler">{cipler}</div></div>',
                unsafe_allow_html=True)
    st.markdown("**Anlatım taslağı** · köşeli parantezli yerleri siz doldurun")
    taslak = st.text_area("Anlatım taslağı", value=a["anlatim_taslagi"], height=110, key="gs_taslak",
                          label_visibility="collapsed")
    if a["sorular"]:
        st.markdown("**Fotoğraftan anlaşılmayanlar — anlatımınıza ekleyin:**\n" +
                    "\n".join(f"- {s}" for s in a["sorular"]))
    if st.button("✍️ Bu taslakla içerik hazırlamaya geç", key="gs_taslak_git", use_container_width=True):
        st.session_state.anlatim_metni = taslak
        st.session_state.kategori_key = b.kategoriler[kat]
        b.git("anlat")


def _paylasim_gorseli(b: Baglam) -> None:
    fotolar = {"Orijinal": st.session_state.gs_foto}
    if st.session_state.gs_duzeltilmis:
        fotolar["Hızlı düzeltilmiş"] = st.session_state.gs_duzeltilmis
    if st.session_state.gs_yz and st.session_state.get("gs_onay"):
        fotolar["Yapay zekâ ile düzenlenmiş"] = st.session_state.gs_yz
    hangi = st.radio("Hangi fotoğraf?", list(fotolar), horizontal=True, key="gs_pay_foto")
    kayit = b.kayit_bul(st.session_state.get("secili_kayit_id") or st.session_state.get("aktif_id"))
    baslik = st.text_input("Başlık", value=takvim.baslik_uret(kayit["anlatim"]) if kayit else "",
                           max_chars=80, key="gs_pay_baslik", placeholder="El örgüsü bebek battaniyesi")
    alt = st.text_input("Alt yazı (isteğe bağlı)", max_chars=90, key="gs_pay_alt",
                        placeholder="Sipariş için mesaj atın")
    rozet = st.text_input("Köşe etiketi", value="El emeği", max_chars=20, key="gs_pay_rozet")
    bicimler, temalar = list(gorsel.BICIMLER), list(gorsel.TEMALAR)
    bicim = st.segmented_control("Biçim", bicimler, default=bicimler[0], key="gs_pay_bicim") or bicimler[0]
    tema = st.pills("Renk", temalar, default=temalar[0], key="gs_pay_tema") or temalar[0]
    if st.button("🖼️ Görseli hazırla", type="primary", key="gs_pay_btn", use_container_width=True):
        if not baslik.strip():
            st.warning("Görsele yazılacak bir başlık girin.")
        else:
            st.session_state.gs_paylasim = gorsel.png(gorsel.paylasim_gorseli(
                gorsel.foto_ac(fotolar[hangi]), baslik, alt, bicim=bicim, tema=tema, rozet=rozet))
    if st.session_state.gs_paylasim:
        st.image(st.session_state.gs_paylasim, width=360)
        st.download_button("⬇️ Görseli indir (PNG)", st.session_state.gs_paylasim,
                           file_name="uretken_kadin_paylasim.png", mime="image/png",
                           key="gs_pay_indir", use_container_width=True)


def _katalog(b: Baglam) -> None:
    gecmis = st.session_state.gecmis
    st.caption("Hazırladığınız ürünlerden, WhatsApp'ta paylaşabileceğiniz bir PDF katalog oluşturur.")
    if not gecmis:
        st.markdown('<div class="bos"><div class="ik">📒</div><p>Katalog, hazırladığınız içeriklerden '
                    'oluşur. Önce bir ürününüzü anlatın.</p></div>', unsafe_allow_html=True)
        if st.button("✍️ Ürün anlat", key="kat_anlat", type="primary", use_container_width=True):
            b.git("anlat")
        return
    baslik = st.text_input("Katalog başlığı", value="Ürün kataloğum", max_chars=40, key="kat_baslik")
    alt = st.text_input("Alt başlık / iletişim (isteğe bağlı)", max_chars=60, key="kat_alt",
                        placeholder="Sipariş için Instagram: @atolyem")
    st.caption("İletişim bilgisi yalnızca indirdiğiniz PDF'e yazılır, saklanmaz.")
    temalar = list(gorsel.TEMALAR)
    tema = st.pills("Renk", temalar, default=temalar[0], key="kat_tema") or temalar[0]

    for kayit in gecmis:
        kid = kayit["id"]
        with st.expander(f"📦 {takvim.baslik_uret(kayit['anlatim'])}"):
            st.checkbox("Kataloğa ekle", value=True, key=f"kat_dahil_{kid}")
            st.text_input("Ürün adı", value=takvim.baslik_uret(kayit["anlatim"], 40), max_chars=40,
                          key=f"kat_ad_{kid}")
            kayit["fiyat"] = st.number_input(
                "Fiyat (TL) · 0 bırakırsanız \"Fiyat için yazın\" yazılır", min_value=0.0, step=10.0,
                value=float(kayit.get("fiyat") or 0), key=f"kat_fiyat_{kid}") or None
            foto = st.file_uploader("Ürün fotoğrafı (isteğe bağlı)", type=["jpg", "jpeg", "png", "webp"],
                                    key=f"kat_foto_{kid}")
            if foto is not None:
                try:
                    kucuk = gorsel.foto_ac(foto.getvalue())
                    kucuk.thumbnail((800, 800))
                    kayit["katalog_foto"] = gorsel.jpeg(kucuk, 85)
                except ValueError as hata:
                    st.warning(str(hata))
            if st.session_state.gs_foto and st.button("📸 Stüdyodaki fotoğrafı kullan", key=f"kat_studyo_{kid}"):
                kayit["katalog_foto"] = st.session_state.gs_duzeltilmis or st.session_state.gs_foto
            if kayit.get("katalog_foto"):
                st.image(kayit["katalog_foto"], width=160, caption="Katalogdaki fotoğraf")

    if st.button("📒 Katalog PDF'ini hazırla", type="primary", key="kat_btn", use_container_width=True):
        urunler = []
        for kayit in gecmis:
            kid = kayit["id"]
            if not st.session_state.get(f"kat_dahil_{kid}", True):
                continue
            ilk_cumle = (kayit.get("shopier") or kayit["anlatim"]).split(". ")[0].strip()
            urunler.append({"ad": st.session_state.get(f"kat_ad_{kid}") or takvim.baslik_uret(kayit["anlatim"], 40),
                            "aciklama": ilk_cumle[:140], "fiyat": kayit.get("fiyat"),
                            "foto": gorsel.foto_ac(kayit["katalog_foto"]) if kayit.get("katalog_foto") else None})
        try:
            st.session_state.kat_pdf = gorsel.katalog_pdf(urunler, baslik, alt, tema)
        except ValueError as hata:
            st.warning(str(hata))
    if st.session_state.kat_pdf:
        st.success("Kataloğunuz hazır 📒")
        st.download_button("⬇️ Kataloğu indir (PDF)", st.session_state.kat_pdf,
                           file_name="uretken_kadin_katalog.pdf", mime="application/pdf",
                           key="kat_indir", use_container_width=True)


# ===========================================================================
# SATIŞ ARAÇLARI
# ===========================================================================
def satis_araclari(b: Baglam) -> None:
    b.ust_bar()
    _baslik("Satış araçları", "💰", "Fiyatınızı hesaplayın, müşterilere cevap verin, pazaryeri ilanı "
                                   "ve özel gün kampanyası hazırlayın.")
    sekme = sekme_kutusu("satis_sekme", SATIS_SEKMELER)
    if sekme == "💰 Fiyat hesapla":
        _fiyat(b)
    elif sekme == "💬 Müşteriye cevap":
        _musteri(b)
    elif sekme == "🛒 Pazaryeri ilanı":
        _ilan(b)
    else:
        _ozel_gunler(b)


def _fiyat_cubugu(d: satis.FiyatDokumu) -> str:
    parcalar = [("Malzeme + ambalaj", d.malzeme_ambalaj, "mavi"), ("Emeğiniz", d.emek_karsiligi, "sari"),
                ("Kâr", max(d.kar, 0), "yesil"), ("Komisyon", d.komisyon, "pembe"), ("Kargo", d.kargo, "gri")]
    parcalar = [p for p in parcalar if p[1] > 0]
    toplam = sum(p[1] for p in parcalar) or 1
    cubuk = "".join(f'<span class="{renk}" style="flex:{deger / toplam:.4f}"></span>'
                    for _, deger, renk in parcalar)
    lejant = "".join(f'<li><i class="{renk}"></i>{ad}: <b>{gorsel.tl_metni(deger)}</b></li>'
                     for ad, deger, renk in parcalar)
    return (f'<div class="fiyat-cubugu" role="img" aria-label="Satış fiyatının dağılımı">{cubuk}</div>'
            f'<ul class="lejant">{lejant}</ul>')


def _fiyat(b: Baglam) -> None:
    st.caption("Emeğinizi de sayan, komisyonu ve kargoyu içeren bir satış fiyatı hesaplayalım. "
               "Hesap yapay zekâ kullanmaz; formül açıktır.")
    k1, k2 = st.columns(2)
    malzeme = k1.number_input("Malzeme (TL)", min_value=0.0, value=150.0, step=10.0, key="fy_malzeme")
    ambalaj = k2.number_input("Ambalaj (TL)", min_value=0.0, value=15.0, step=5.0, key="fy_ambalaj")
    emek = k1.number_input("Emek (saat)", min_value=0.0, value=6.0, step=0.5, key="fy_emek")
    ucret = k2.number_input("Saatlik ücretiniz (TL)", min_value=0.0, value=100.0, step=10.0, key="fy_ucret",
                            help="Emeğinize biçtiğiniz saatlik ücret. Asgari ücretin saatlik karşılığını "
                                 "referans alabilirsiniz; karar sizin.")
    kargo = k1.number_input("Kargo (TL) · alıcı ödüyorsa 0", min_value=0.0, value=0.0, step=5.0, key="fy_kargo")
    komisyon = k2.number_input("Komisyon (%)", min_value=0.0, max_value=99.0, value=0.0, step=0.5,
                               key="fy_komisyon",
                               help="Satış platformu ve ödeme hizmeti oranlarının toplamı. Güncel oranı "
                                    "kendi satıcı panelinizden ya da sözleşmenizden kontrol edin.")
    kar = st.slider("Kâr payı (%)", min_value=0, max_value=100, value=20, step=5, key="fy_kar")
    girdi = satis.FiyatGirdisi(malzeme=malzeme, emek_saat=emek, saat_ucreti=ucret, ambalaj=ambalaj,
                               kargo=kargo, komisyon_yuzde=komisyon, kar_yuzde=kar)
    try:
        d = satis.fiyat_oner(girdi)
    except ValueError as hata:
        st.warning(str(hata))
        return
    saatlik = gorsel.tl_metni(d.gercek_saatlik) if d.gercek_saatlik is not None else "—"
    st.markdown(f'<div class="ozet"><div class="kutu"><div class="deger">{gorsel.tl_metni(d.satis_fiyati)}</div>'
                f'<div class="etiket">önerilen satış fiyatı</div></div><div class="kutu"><div class="deger">'
                f'{gorsel.tl_metni(d.eline_gecen)}</div><div class="etiket">elinize geçen</div></div>'
                f'<div class="kutu"><div class="deger">{saatlik}</div><div class="etiket">saatlik kazancınız'
                f'</div></div></div>', unsafe_allow_html=True)
    st.markdown(_fiyat_cubugu(d), unsafe_allow_html=True)

    mevcut = st.number_input("Şu an kaça satıyorsunuz? (isteğe bağlı, kontrol için)", min_value=0.0,
                             value=0.0, step=10.0, key="fy_mevcut")
    if mevcut > 0:
        m = satis.dokum(girdi, mevcut)
        if m.gercek_saatlik is not None and m.gercek_saatlik < ucret:
            st.warning(f"Bu fiyatla emeğinizin saati **{gorsel.tl_metni(m.gercek_saatlik)}** ediyor; "
                       f"hedeflediğiniz {gorsel.tl_metni(ucret)} ücretin altında. Elinize "
                       f"{gorsel.tl_metni(m.eline_gecen)} geçiyor.")
        else:
            st.success(f"Bu fiyat emeğinizi karşılıyor 👏 Elinize {gorsel.tl_metni(m.eline_gecen)} geçiyor.")
    st.caption("Vergi ve yasal yükümlülükleriniz için bir muhasebeciye danışın.")

    if st.session_state.gecmis:
        adlar = {k["id"]: takvim.baslik_uret(k["anlatim"]) for k in st.session_state.gecmis}
        secili = st.session_state.get("secili_kayit_id")
        kid = st.selectbox("Bu fiyatı hangi ürüne kaydedelim? (katalogda kullanılır)", list(adlar),
                           format_func=adlar.get, key="fy_urun",
                           index=list(adlar).index(secili) if secili in adlar else 0)
        if st.button(f"💾 {gorsel.tl_metni(d.satis_fiyati)} fiyatını kaydet", key="fy_kaydet",
                     use_container_width=True):
            b.kayit_bul(kid)["fiyat"] = d.satis_fiyati
            st.success(f"Kaydedildi: {adlar[kid]} · {gorsel.tl_metni(d.satis_fiyati)}")


def _musteri(b: Baglam) -> None:
    mod = st.segmented_control("Cevap türü", ["📋 Hazır cevaplar", "🪄 Mesaja özel cevap"],
                               default="📋 Hazır cevaplar", key="mc_mod",
                               label_visibility="collapsed") or "📋 Hazır cevaplar"
    if mod == "📋 Hazır cevaplar":
        durumlar = list(satis.HAZIR_CEVAPLAR)
        durum = st.pills("Durum", durumlar, default=durumlar[0], key="mc_durum",
                         label_visibility="collapsed") or durumlar[0]
        metin = satis.HAZIR_CEVAPLAR[durum]
        st.code(metin, language=None, wrap_lines=True)
        st.caption("Göndermeden önce doldurun: " + ", ".join(f"[{y}]" for y in satis.yer_tutucular(metin)))
        if durum == "↩️ İade / değişim":
            st.caption("İade ve değişim koşullarınızı yasal düzenlemelere uygun belirleyin.")
        return

    mesaj = st.text_area("Müşterinin mesajı", height=110, key="mc_mesaj",
                         placeholder="Merhaba, bu battaniyenin başka rengi var mı? Kargo ne kadar sürer?")
    st.caption("Müşterinin adını, telefonunu ya da adresini yapıştırmayın; buna gerek yok.")
    anlatim, _, _ = _urun_kaynagi(b, "mc", "Hangi ürün hakkında? (cevap bu bilgiye dayanır)", zorunlu=False)
    tonlar = list(satis.TONLAR)
    ton = st.pills("Ton", tonlar, default=tonlar[0], key="mc_ton", label_visibility="collapsed") or tonlar[0]
    if st.button("🪄 Cevap taslağı hazırla", type="primary", key="mc_btn", use_container_width=True):
        with st.spinner("Cevap hazırlanıyor…"):
            try:
                st.session_state.mc_cevap = satis.musteri_cevabi_uret(mesaj, anlatim, ton, ozenli=b.ozenli)
            except Exception as hata:
                _hata_goster(hata, "cevap hazırlanamadı")
    if st.session_state.mc_cevap:
        st.code(st.session_state.mc_cevap, language=None, wrap_lines=True)
        doldur = satis.yer_tutucular(st.session_state.mc_cevap)
        if doldur:
            st.caption("Göndermeden önce doldurun: " + ", ".join(f"[{y}]" for y in doldur))
        st.caption("Bu bir taslaktır; okuyup dilediğiniz gibi düzenleyerek gönderin.")


def _ilan(b: Baglam) -> None:
    anlatim, kategori, _ = _urun_kaynagi(b, "ilan")
    platformlar = list(satis.PLATFORMLAR)
    platform = st.pills("Platform", platformlar, default=platformlar[0], key="ilan_platform",
                        label_visibility="collapsed") or platformlar[0]
    if st.button("🛒 İlanı hazırla", type="primary", key="ilan_btn", use_container_width=True):
        with st.spinner("İlan hazırlanıyor…"):
            try:
                st.session_state.ilan_sonuc = asdict(satis.pazaryeri_ilani_uret(anlatim, kategori, platform,
                                                                               ozenli=b.ozenli))
            except Exception as hata:
                _hata_goster(hata, "ilan hazırlanamadı")
    ilan = st.session_state.ilan_sonuc
    if ilan:
        sinir = satis.ETSY_BASLIK if satis.PLATFORMLAR.get(ilan["platform"]) == "en" else satis.TR_BASLIK
        st.markdown(f'<div class="kart-baslik">{html.escape(ilan["platform"])} ilanınız</div>',
                    unsafe_allow_html=True)
        st.markdown(f"**Başlık** · {len(ilan['baslik'])}/{sinir} karakter")
        st.code(ilan["baslik"], language=None, wrap_lines=True)
        if ilan["ozellikler"]:
            st.markdown("**Özellikler**")
            st.code("\n".join(f"• {x}" for x in ilan["ozellikler"]), language=None, wrap_lines=True)
        st.markdown("**Açıklama**")
        st.code(ilan["aciklama"], language=None, wrap_lines=True)
        if ilan["etiketler"]:
            st.markdown(f"**Etiketler** · {len(ilan['etiketler'])} adet")
            st.code(", ".join(ilan["etiketler"]), language=None, wrap_lines=True)
        if ilan["eksik_bilgiler"]:
            st.warning("📝 İlanda olması gereken ama anlatımınızda olmayan bilgiler: **" +
                       ", ".join(ilan["eksik_bilgiler"]) + "**. Bunları ilana siz ekleyin.")
        if ilan["cikarilan_etiketler"]:
            st.caption("🛡️ Anlatımınızda olmayan bir iddia taşıdığı için çıkarılan etiketler: " +
                       ", ".join(ilan["cikarilan_etiketler"]))

    with st.expander("🌍 Herhangi bir metni İngilizceye çevir"):
        metin = st.text_area("Çevrilecek metin", height=110, key="ilan_ceviri_metin",
                             placeholder="Instagram metninizi ya da ürün açıklamanızı yapıştırın")
        if st.button("🌍 İngilizceye çevir", key="ilan_ceviri_btn", use_container_width=True):
            with st.spinner("Çevriliyor…"):
                try:
                    st.session_state.ilan_ceviri = satis.cevir(metin)
                except Exception as hata:
                    _hata_goster(hata, "çevrilemedi")
        if st.session_state.ilan_ceviri:
            st.code(st.session_state.ilan_ceviri, language=None, wrap_lines=True)


def _gun_kartlari(gunler: list[satis.OzelGun], bugun) -> str:
    kartlar = []
    for g in gunler[:8]:
        kalan = (g.tarih - bugun).days
        kartlar.append(
            f'<div class="gun-karti{" yakin" if kalan <= 30 else ""}"><div class="tarih"><b>{g.tarih.day}</b>'
            f'{takvim.AYLAR[g.tarih.month - 1][:3]}</div><div><div class="ad">{html.escape(g.ad)}</div>'
            f'<div class="kalan">{"bugün" if kalan == 0 else f"{kalan} gün kaldı"}'
            f'{" · yaklaşık" if g.yaklasik else ""}</div></div></div>')
    return f'<div class="gun-kartlari">{"".join(kartlar)}</div>'


def _ozel_gunler(b: Baglam) -> None:
    bugun = takvim.simdi().date()
    gunler = sorted(satis.yaklasan_ozel_gunler(bugun) +
                    [g for g in st.session_state.ozel_gunler_ek if g.tarih >= bugun], key=lambda g: g.tarih)
    st.markdown(_gun_kartlari(gunler, bugun), unsafe_allow_html=True)
    st.caption("Dini bayramlar her yıl ay takvimine göre kaydığı için listede yok; aşağıdan kendiniz "
               "ekleyebilirsiniz.")
    with st.expander("➕ Kendi özel gününüzü ekleyin"):
        ad = st.text_input("Gün adı", max_chars=40, key="og_ek_ad", placeholder="Ramazan Bayramı")
        tarih = st.date_input("Tarih", min_value=bugun, format="DD.MM.YYYY", key="og_ek_tarih")
        if st.button("➕ Ekle", key="og_ek_btn"):
            if ad.strip():
                st.session_state.ozel_gunler_ek.append(satis.OzelGun(ad.strip(), tarih, "Kendi eklediğiniz gün"))
                st.rerun()
            st.warning("Gün adını yazın.")
    if not gunler:
        return
    secenekler = {f"{g.ad} · {satis.tarih_metni(g)}": g for g in gunler}
    secim = st.selectbox("Hangi özel gün için kampanya hazırlayalım?", list(secenekler), key="og_gun")
    anlatim, kategori, kayit = _urun_kaynagi(b, "og", "Hangi ürün için?")
    if st.button("🎉 Kampanya önerisi hazırla", type="primary", key="og_btn", use_container_width=True):
        with st.spinner("Kampanya önerisi hazırlanıyor…"):
            try:
                st.session_state.og_oneri = {"gun": secim, "icerik_id": kayit["id"] if kayit else "",
                                             "metin": satis.kampanya_onerisi_uret(secenekler[secim], anlatim,
                                                                                  kategori, ozenli=b.ozenli)}
            except Exception as hata:
                _hata_goster(hata, "öneri hazırlanamadı")
    oneri = st.session_state.og_oneri
    if oneri and oneri["gun"] in secenekler:
        st.markdown(f'<div class="kart-baslik">🎉 {html.escape(oneri["gun"])}</div>', unsafe_allow_html=True)
        st.markdown(oneri["metin"])
        if st.button("📅 Üç hatırlatmayı takvimime ekle", key="og_takvim", use_container_width=True):
            yeni = satis.kampanya_plani(secenekler[oneri["gun"]], oneri["metin"], oneri["icerik_id"])
            st.session_state.plan = st.session_state.plan + yeni
            if yeni:
                st.success(f"{len(yeni)} hatırlatma takvime eklendi. 🏠 Panom'dan telefon takviminize aktarabilirsiniz.")
            else:
                st.info("Bu özel güne çok az kaldığı için eklenecek hatırlatma zamanı kalmadı.")
