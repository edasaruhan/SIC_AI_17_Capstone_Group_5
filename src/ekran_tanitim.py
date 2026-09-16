# -*- coding: utf-8 -*-
"""
Üretken Kadın — tanıtım sayfası (giriş yapmamış ziyaretçinin ilk gördüğü ekran)

Ne yaptığımızı, kimler için olduğunu, araçları ve verilerin nasıl korunduğunu anlatır; sonunda
kayıt / giriş çağrısı vardır. Araçların kendisi girişten sonra açılır (app.py erişim kapısı).
Burada anlatılan her özellik uygulamada bugün çalışır — gelecek vaadi yazılmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import streamlit as st

import ekran_araclar
import ekran_hesap
import logo


@dataclass
class Baglam:
    git: Callable[[str], None]


KIMLER = ["🧶 Örgü ve dikiş", "🪡 Nakış ve dantel", "💍 Takı ve aksesuar", "🍯 Ev yapımı gıda",
          "🧼 Doğal sabun", "🏺 Seramik ve dekor", "🧵 Keçe ve kumaş", "🎨 Tasarım ürünleri"]

# (ikon, ad, açıklama, renk sınıfı)
OZELLIKLER = [
    ("✍️", "İçerik yazar",
     "Anlattığınızdan Instagram gönderisi ve Shopier satış metni; istersen Reels çekim planı, "
     "hikâye, WhatsApp mesajı ve hashtag seti.", "mavi"),
    ("🎙️", "Sesinizi yazıya döker",
     "Yazmak zor mu? Ürününüzü konuşarak anlatın, kendi kelimelerinizle metne çevrilsin.", "sari"),
    ("📸", "Görsel stüdyosu",
     "Fotoğraf kalitesini ölçer, ışığı düzeltir; paylaşıma hazır görsel ve WhatsApp'tan "
     "gönderilebilir PDF katalog hazırlar.", "pembe"),
    ("💰", "Satış araçları",
     "Emeğinizi hesaba katan fiyat önerisi, müşteri mesajlarına kibar cevap, pazaryeri ilanı "
     "ve yaklaşan özel günler için kampanya fikri.", "yesil"),
    ("📅", "Panom ve takvim",
     "Hazırladığınız her şey tek yerde; ne zaman ne paylaşacağınızı takvime koyun.", "mavi"),
    ("🎨", "Sizin gibi yazar",
     "Kendi yazdığınız birkaç gönderiyi gösterin; içerikler sizin üslubunuzla hazırlansın.", "sari"),
]

GUVENCELER = [
    ("🤍", "Uydurmaz", "Yalnızca sizin anlattığınızı kullanır; olmayan özellik ya da abartı eklemez."),
    ("✅", "Son söz sizde", "Her metni okur, dilediğiniz gibi düzeltir, sonra paylaşırsınız."),
    ("🔒", "KVKK'ya uygun", "Fotoğraf ve ses kayıtlarınız saklanmaz; ne işlendiği açıkça yazar."),
    ("🗑️", "Verileriniz sizin", "İçerikleriniz hesabınızda durur; dilediğiniz an indirir ya da silersiniz."),
]

SSS = [
    ("Ücretli mi?", "Hayır. Üretken Kadın'ı ücretsiz kullanabilirsiniz; kayıt olurken kart bilgisi istenmez."),
    ("Bilgisayar ya da yazı konusunda iyi değilim, kullanabilir miyim?",
     "Evet, tam da bunun için yapıldı. Ürününüzü konuşarak anlatabilir, sol menüden yazıları "
     "büyütebilirsiniz. Her adımda ne yapacağınız ekranda yazar."),
    ("Instagram hesabıma kendisi mi paylaşıyor?",
     "Hayır, hesaplarınıza bağlanmaz ve sizin yerinize bir şey paylaşmaz. Hazırlanan metni "
     "kopyalar, kendiniz paylaşırsınız."),
    ("Yazdıklarım ve fotoğraflarım nereye gidiyor?",
     "Metin hazırlamak için anlatımınız Google Gemini yapay zekâsına gönderilir. Hazırlanan "
     "içerikler hesabınızda saklanır; fotoğraf ve ses kayıtları saklanmaz. Ayrıntılar kayıt "
     "ekranındaki aydınlatma metninde."),
]

CSS = """
<style>
.tanitim { animation:gir .5s ease both; }
.tanitim-ust { display:flex; align-items:center; gap:.7rem; }
.tanitim-ust .logo { width:46px; height:46px; flex:none; border-radius:13px; box-shadow:var(--golge-sm); }
.tanitim-ust .logo svg { width:100%; height:100%; display:block; }
.tanitim-ust .ad { font-family:'Baloo 2'; font-weight:800; font-size:1.3rem; line-height:1; }
.tanitim-ust .alt { font-size:.8rem; color:var(--muted); font-weight:700; }
.rozet-ust { display:inline-block; background:#fff; border:2px solid var(--ink); border-radius:999px;
  padding:.2rem .9rem; font-weight:800; font-size:.9rem; box-shadow:var(--golge-sm); margin:.2rem 0 1rem; }
.bolum-baslik { font-family:'Baloo 2','Nunito',sans-serif; font-weight:800; font-size:1.75rem; line-height:1.15;
  text-align:center; margin:2.4rem 0 .3rem; color:var(--ink); }
.bolum-alt { text-align:center; color:var(--muted); font-weight:600; margin:0 auto 1.1rem; max-width:560px; }
.kisa-not { text-align:center; color:var(--muted); font-size:.9rem; font-weight:700; margin:.5rem 0 0; }
.kimler { display:flex; flex-wrap:wrap; justify-content:center; gap:.5rem; }
.kimler span { background:#fff; border:2px solid var(--line); border-radius:999px; padding:.3rem .85rem;
  font-weight:800; font-size:.92rem; }
.ornek { display:grid; grid-template-columns:1fr auto 1fr; gap:.8rem; align-items:center; }
.ornek .balon { background:#fff; border:2.5px solid var(--ink); border-radius:20px; padding:1rem 1.1rem;
  box-shadow:var(--golge); font-size:.95rem; line-height:1.55; }
.ornek .balon.once { background:var(--yellow-soft); border-bottom-left-radius:6px; }
.ornek .balon.sonra { background:var(--blue-soft); }
.ornek .etiket { display:block; font-family:'Baloo 2'; font-weight:800; font-size:.95rem; color:var(--plum);
  margin-bottom:.35rem; }
.ornek .ok { font-size:1.8rem; font-weight:800; text-align:center; }
.ornek .etiketler { color:var(--plum); font-weight:700; }
.ozellikler { display:grid; grid-template-columns:repeat(3,1fr); gap:.85rem; }
.ozellik { border:2.5px solid var(--ink); border-radius:20px; padding:1rem; box-shadow:var(--golge);
  transition:transform .2s ease; }
.ozellik:hover { transform:translateY(-4px) rotate(-1deg); }
.ozellik.mavi { background:var(--blue-soft); } .ozellik.sari { background:var(--yellow-soft); }
.ozellik.pembe { background:var(--pink-soft); } .ozellik.yesil { background:var(--mint-soft); }
.ozellik .ikon { font-size:1.7rem; line-height:1; }
.ozellik h4 { font-family:'Baloo 2'; font-weight:800; font-size:1.15rem; margin:.4rem 0 .2rem; }
.ozellik p { margin:0; font-size:.9rem; color:var(--ink-2); line-height:1.45; }
.guvenceler { display:grid; grid-template-columns:repeat(2,1fr); gap:.7rem; }
.guvence { display:flex; gap:.7rem; align-items:flex-start; background:#fff; border:2.5px dashed var(--plum);
  border-radius:18px; padding:.8rem .95rem; }
.guvence .ikon { font-size:1.5rem; line-height:1.2; }
.guvence b { font-family:'Baloo 2'; font-size:1.05rem; display:block; }
.guvence p { margin:0; font-size:.9rem; color:var(--ink-2); line-height:1.45; }
.son-cagri { text-align:center; background:var(--plum); color:#fff; border:2.5px solid var(--ink);
  border-radius:24px; padding:1.6rem 1.2rem 1.2rem; box-shadow:var(--golge-lg); margin:2.6rem 0 .9rem; }
.son-cagri h3 { color:#fff !important; font-family:'Baloo 2'; font-weight:800; font-size:1.7rem; margin:0 0 .3rem; }
.son-cagri p { color:#FBE9F5 !important; margin:0; font-weight:600; }
@media (max-width:640px) {
  .ornek { grid-template-columns:1fr; }
  .ornek .ok { transform:rotate(90deg); }
  .ozellikler { grid-template-columns:1fr 1fr; gap:.55rem; }
  .ozellik { padding:.75rem; }
  .ozellik p { font-size:.82rem; }
  .guvenceler { grid-template-columns:1fr; }
  .bolum-baslik { font-size:1.45rem; }
}
@media (max-width:400px) { .ozellikler { grid-template-columns:1fr; } }
</style>
"""


def _kayit_ol(b: Baglam) -> None:
    ekran_araclar.sekme_sec("giris_sekme", ekran_hesap.GIRIS_SEKMELERI[1])
    b.git("giris")


def _giris_yap(b: Baglam) -> None:
    ekran_araclar.sekme_sec("giris_sekme", ekran_hesap.GIRIS_SEKMELERI[0])
    b.git("giris")


def _cagri_dugmeleri(b: Baglam, anahtar: str) -> None:
    k1, k2 = st.columns([1.35, 1])
    if k1.button("✨ Ücretsiz hesap oluştur", type="primary", use_container_width=True, key=f"{anahtar}_kayit"):
        _kayit_ol(b)
    if k2.button("🔑 Giriş yap", use_container_width=True, key=f"{anahtar}_giris"):
        _giris_yap(b)


def tanitim_sayfasi(b: Baglam) -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    # Üst: logo + giriş
    sol, sag = st.columns([3, 1.1], vertical_alignment="center")
    sol.markdown(f'<div class="tanitim-ust"><div class="logo">{logo.SVG}</div><div>'
                 '<div class="ad">Üretken Kadın</div><div class="alt">Emeğin dijital sesi</div></div></div>',
                 unsafe_allow_html=True)
    if sag.button("🔑 Giriş yap", use_container_width=True, key="tanitim_menu_giris"):
        _giris_yap(b)

    # Karşılama
    st.markdown(
        f'<div class="karsilama tanitim" style="margin-top:1.4rem"><div class="amblem" aria-hidden="true">'
        f'{logo.SVG}</div><div class="rozet-ust">Kadın üreticiler için ücretsiz yapay zekâ asistanı</div>'
        '<h1>El emeğinizi, <span class="vurgu">arayanların bulacağı</span> bir dile çeviriyoruz.</h1>'
        '<p class="aciklama">Ürününüzü kendi cümlelerinizle anlatın; Instagram gönderinizi, satış metninizi, '
        'fotoğrafınızı ve fiyatınızı birlikte hazırlayalım. Yazı yazmayı ya da pazarlamayı bilmenize gerek yok.'
        '</p></div>', unsafe_allow_html=True)
    _cagri_dugmeleri(b, "tanitim_ust")
    st.markdown('<p class="kisa-not">Kart bilgisi istemez · Bir dakikada hesap</p>', unsafe_allow_html=True)

    # Kimler için
    st.markdown('<div class="bolum-baslik">Kimler için?</div>'
                '<p class="bolum-alt">Evde, atölyede ya da kooperatifte üretip satan her kadın için.</p>'
                '<div class="kimler">' + "".join(f"<span>{k}</span>" for k in KIMLER) + "</div>",
                unsafe_allow_html=True)

    # Nasıl çalışır
    st.markdown("""
    <div class="bolum-baslik">Nasıl çalışır?</div>
    <p class="bolum-alt">Üç adımda paylaşıma hazır içerik.</p>
    <div class="adimlar">
      <div class="adim"><div class="no">1</div><h4>Siz anlatın</h4>
        <p>Ürününüzü yazarak ya da sesli anlatın. Nasıl konuşuyorsanız öyle.</p></div>
      <div class="adim"><div class="no">2</div><h4>Biz hazırlayalım</h4>
        <p>Sizin sözlerinizden hazır metinler çıkarırız — dakikalar içinde.</p></div>
      <div class="adim"><div class="no">3</div><h4>Siz onaylayın</h4>
        <p>Okur, beğendiğiniz gibi düzeltir ve paylaşırsınız. Söz hep sizde.</p></div>
    </div>
    """, unsafe_allow_html=True)

    # Örnek
    st.markdown("""
    <div class="bolum-baslik">Bir örnek</div>
    <p class="bolum-alt">Sizin birkaç cümleniz, paylaşıma hazır bir gönderiye dönüşür.</p>
    <div class="ornek">
      <div class="balon once"><span class="etiket">🗣️ Sizin anlattığınız</span>
        El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, bir tanesi üç günümü
        alıyor. Renklerini siparişe göre seçiyorum.</div>
      <div class="ok" aria-hidden="true">→</div>
      <div class="balon sonra"><span class="etiket">📱 Hazırlanan gönderi</span>
        Üç günün her ilmeğinde bir dua var 🤍 Organik pamuk ipliğiyle, tamamen elde ördüğüm bu
        battaniye bebeğinizin hassas cildi için. Rengini siz seçin, ben sizin için öreyim.
        Sipariş için mesaj atabilirsiniz.<br>
        <span class="etiketler">#elörgüsü #bebekbattaniyesi #organikpamuk</span></div>
    </div>
    <p class="kisa-not">Örnek metindir; her içerik sizin anlattıklarınıza göre yeniden hazırlanır.</p>
    """, unsafe_allow_html=True)

    # Özellikler
    st.markdown('<div class="bolum-baslik">Neler yapabilirsiniz?</div>'
                '<p class="bolum-alt">Hesabınızı açınca hepsi tek yerde sizi bekliyor.</p>'
                '<div class="ozellikler">' + "".join(
                    f'<div class="ozellik {renk}"><div class="ikon" aria-hidden="true">{ikon}</div>'
                    f'<h4>{ad}</h4><p>{aciklama}</p></div>' for ikon, ad, aciklama, renk in OZELLIKLER)
                + "</div>", unsafe_allow_html=True)

    # Güvence
    st.markdown('<div class="bolum-baslik">Gönül rahatlığıyla kullanın</div>'
                '<p class="bolum-alt">Yapay zekâ yalnızca yardımcı olur; hikâye ve karar sizindir.</p>'
                '<div class="guvenceler">' + "".join(
                    f'<div class="guvence"><div class="ikon" aria-hidden="true">{ikon}</div>'
                    f'<div><b>{ad}</b><p>{aciklama}</p></div></div>' for ikon, ad, aciklama in GUVENCELER)
                + "</div>", unsafe_allow_html=True)

    # SSS
    st.markdown('<div class="bolum-baslik">Sık sorulanlar</div>', unsafe_allow_html=True)
    for soru, cevap in SSS:
        with st.expander(soru):
            st.markdown(cevap)

    # Son çağrı
    st.markdown('<div class="son-cagri"><h3>Emeğinizin sesini duyurmaya hazır mısınız?</h3>'
                '<p>Hesabınızı oluşturun, ilk içeriğinizi birkaç dakikada hazırlayın.</p></div>',
                unsafe_allow_html=True)
    _cagri_dugmeleri(b, "tanitim_alt")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
    k1, k2 = st.columns(2)
    if k1.button("❓ Nasıl kullanılır?", use_container_width=True, key="tanitim_yardim"):
        b.git("yardim")
    if k2.button("🏢 Firmalar için API", use_container_width=True, key="tanitim_api"):
        b.git("api")
