# -*- coding: utf-8 -*-
"""
Üretken Kadın — "Nasıl kullanılır?" tanıtım videosu

Video YouTube'da (liste dışı) barındırılır; bağlantı aşağıdaki VIDEO_ADRESI sabitinde durur.
Render'da TANITIM_VIDEO ortam değişkeni tanımlıysa o öncelikli olur — böylece video değişince
kod güncellemeye gerek kalmaz.

Bağlantı tanımlı değilse video bölümü hiç gösterilmez; uygulama bozulmaz.
"""

from __future__ import annotations

import os

import streamlit as st

VIDEO_ADRESI = "https://youtu.be/8xRvJpisx9o"      # YouTube, liste dışı
SURE = "1,5 dakika"
ETIKET = f"▶️ Nasıl kullanılır? ({SURE})"


def kaynak() -> str:
    return (os.getenv("TANITIM_VIDEO", "").strip() or VIDEO_ADRESI).strip()


def var_mi() -> bool:
    return bool(kaynak())


def oynat() -> None:
    yol = kaynak()
    if not yol:
        return
    st.video(yol)
    st.caption("Videoda hesap açmaktan içerik hazırlamaya kadar tüm adımlar var. "
               "Alt yazı için oynatıcıdaki **CC** düğmesine dokunabilirsiniz.")


def dugme(anahtar: str, etiket: str = ETIKET) -> None:
    """Videoyu açıp kapatan düğme; bağlantı tanımlı değilse hiçbir şey çizmez."""
    if not var_mi():
        return
    durum = f"{anahtar}_acik"
    acik = bool(st.session_state.get(durum))
    if st.button("✖️ Videoyu kapat" if acik else etiket, key=anahtar, use_container_width=True):
        st.session_state[durum] = not acik
        st.rerun()
    if st.session_state.get(durum):
        oynat()
