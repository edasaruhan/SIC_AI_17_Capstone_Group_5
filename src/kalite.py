# -*- coding: utf-8 -*-
"""
Üretken Kadın — İçerik kalite sınıflandırıcısı (öznitelikler + çıkarım)

Bu modül, "Data Prep & Model Exploration" dökümanındaki HITL ÖN-FİLTRESİNİ
somutlaştırır: YZ'nin ürettiği taslağın üreticiye gitmeden ÖNCE "onaya hazır
(yüksek)" mı yoksa "gözden geçir (düşük)" mı olduğunu kestirir. Amaç, üreticinin
inceleme yükünü azaltmak ve halüsinasyon/abartı riskini erken yakalamaktır.

Bu dosya EĞİTİM ve ÇIKARIM tarafından ORTAK kullanılır; böylece öznitelikler her
iki tarafta birebir aynı hesaplanır (train/serve tutarlılığı). Model dosyası:
    models/kalite_modeli.joblib   (kalite_egit.py üretir)

Öznitelikler (dökümandaki gerekçelerle):
    kelime_sayisi   : içerik uzunluğu kaliteyle ilişkili (ne çok kısa ne aşırı uzun)
    seo_kapsami     : içerikteki Google Trends anahtar kelime sayısı — en güçlü sinyal
    seo_orani       : kapsam / toplam anahtar kelime (normalize)
    abarti_isareti  : "en iyi, mucize, garanti" gibi ispatsız iddialar → otantiklik riski
    klise_isareti   : dolgu/klişe kalıp sayısı (prompts.KLISE_KALIPLARI)
    duygu_yogunlugu : aşırı pazarlamacı/yapay ton yoğunluğu (kelime başına)
    hikaye_ipucu    : üretim süreci/öykü içeren ifadeler (otantiklik göstergesi)
    + TF-IDF(500)   : ayırt edici kelime örüntüleri
"""

from __future__ import annotations

import re
from pathlib import Path

import prompts

_KOK = Path(__file__).resolve().parent.parent
MODEL_YOLU = _KOK / "models" / "kalite_modeli.joblib"

# Sayısal özniteliklerin SABİT sırası — eğitim ve çıkarım aynı sırayı kullanmalı.
SAYISAL_OZNITELIKLER = [
    "kelime_sayisi", "seo_kapsami", "seo_orani",
    "abarti_isareti", "klise_isareti", "duygu_yogunlugu", "hikaye_ipucu",
]

# İspatsız/abartılı iddia kalıpları (SISTEM_TALIMATI'ndeki yasaklarla uyumlu).
ABARTI_KALIPLARI = [
    "en iyi", "mucize", "birebir", "garanti", "şifalı", "dünyanın en",
    "en kaliteli", "%100", "yüzde yüz", "kesin sonuç", "eşi benzeri yok",
    "piyasanın en", "rakipsiz", "bir numara", "tek adres",
]

# Aşırı pazarlamacı / yapay duygu tonu (ölçülü pozitif tercih edilir).
DUYGU_KALIPLARI = [
    "harika", "muhteşem", "mükemmel", "inanılmaz", "efsane", "süper",
    "bayılacaksınız", "kaçırmayın", "hemen alın", "acele", "son fırsat",
    "büyük indirim", "hayran kalacaksınız", "tam size göre", "fırsat kaçmaz",
]

# Üretim süreci / kişisel öykü ipuçları (otantiklik göstergesi).
HIKAYE_KALIPLARI = [
    "anneannem", "anneannemden", "annemden", "öğrendiğim", "kendi elimle",
    "kendim", "bahçemiz", "günümü alıyor", "yıllardır", "elde", "el emeği",
    "tek tek", "sabırla", "geleneksel", "mayalıyorum", "topluyorum",
    "kuruttuğum", "diktiğim", "ördüğüm", "yapıyorum",
]


# ---------------------------------------------------------------------------
# Metin temizleme (dökümandaki adımlar)
# ---------------------------------------------------------------------------
def metni_temizle(s: str) -> str:
    """Küçük harf, link/mention/hashtag ve noktalama/emoji temizliği."""
    s = (s or "").lower()
    s = re.sub(r"http\S+|@\w+|#\w+", " ", s)     # link, mention, hashtag
    s = re.sub(r"[^\wğüşıöç\s]", " ", s)          # noktalama/emoji (TR harfleri kalır)
    return re.sub(r"\s+", " ", s).strip()


def _kalip_say(metin_kucuk: str, kaliplar: list[str]) -> int:
    return sum(metin_kucuk.count(k) for k in kaliplar)


# ---------------------------------------------------------------------------
# Sayısal öznitelikler
# ---------------------------------------------------------------------------
def sayisal_oznitelikler(metin: str, kategori: str = "") -> dict:
    """Bir içerik metninden dökümandaki sayısal öznitelikleri çıkarır."""
    kucuk = (metin or "").lower()
    kelimeler = kucuk.split()
    n = max(len(kelimeler), 1)

    anahtarlar = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    kapsam = sum(1 for k in anahtarlar if k.lower() in kucuk)
    toplam = max(len(anahtarlar), 1)

    return {
        "kelime_sayisi": len(kelimeler),
        "seo_kapsami": kapsam,
        "seo_orani": round(kapsam / toplam, 3),
        "abarti_isareti": _kalip_say(kucuk, ABARTI_KALIPLARI),
        "klise_isareti": _kalip_say(kucuk, prompts.KLISE_KALIPLARI),
        "duygu_yogunlugu": round(_kalip_say(kucuk, DUYGU_KALIPLARI) / n, 4),
        "hikaye_ipucu": _kalip_say(kucuk, HIKAYE_KALIPLARI),
    }


def oznitelik_vektoru(metin: str, kategori: str = "") -> list[float]:
    """Sayısal öznitelikleri SAYISAL_OZNITELIKLER sırasında liste olarak verir."""
    d = sayisal_oznitelikler(metin, kategori)
    return [float(d[ad]) for ad in SAYISAL_OZNITELIKLER]


# ---------------------------------------------------------------------------
# Çıkarım — eğitilmiş modeli yükleyip tahmin üretir
# ---------------------------------------------------------------------------
class KaliteModeli:
    """
    Eğitilmiş modeli (model + TF-IDF + scaler) yükler ve tahmin üretir.

    Model dosyası yoksa sessizce devre dışı kalır (mevcut() == False); arayüz
    bu durumu kontrol edip özelliği gizler — çekirdek üretim akışı etkilenmez.
    """

    def __init__(self, yol: Path | str = MODEL_YOLU):
        self.yol = Path(yol)
        self._paket = None
        try:
            import joblib
            if self.yol.exists():
                self._paket = joblib.load(self.yol)
        except Exception:
            self._paket = None
        # Model dosyası yoksa (ör. Streamlit Cloud — joblib gitignore'da) etiketli
        # CSV'den kendi kendine eğit. Sklearn yoksa/CSV yoksa sessizce devre dışı.
        if self._paket is None:
            self._paket = egit_bellekte()

    def mevcut(self) -> bool:
        return self._paket is not None

    def tahmin(self, metin: str, kategori: str = "") -> dict:
        """
        Dönüş:
            {
              "hazir": bool,          # True → onaya hazır (yüksek)
              "olasilik": float,      # 'yüksek' sınıfı olasılığı (0-1)
              "etiket": str,          # "Onaya hazır" | "Gözden geçirin"
              "gerekceler": list[str] # düşük olasılığı açıklayan sinyaller
            }
        Model yoksa {"hazir": None, ...} döner.
        """
        oz = sayisal_oznitelikler(metin, kategori)
        gerekceler = self._gerekceler(oz)

        if not self.mevcut():
            return {"hazir": None, "olasilik": None,
                    "etiket": "Model yok", "gerekceler": gerekceler}

        import numpy as np
        from scipy.sparse import hstack

        model = self._paket["model"]
        vekt = self._paket["vektorizer"]
        scaler = self._paket["scaler"]

        temiz = metni_temizle(metin)
        X_txt = vekt.transform([temiz])
        X_num = scaler.transform([[oz[a] for a in SAYISAL_OZNITELIKLER]])
        X = hstack([X_txt, X_num])

        olasilik = float(model.predict_proba(X)[0][1])
        hazir = olasilik >= self._paket.get("esik", 0.5)
        return {
            "hazir": hazir,
            "olasilik": round(olasilik, 3),
            "etiket": "Onaya hazır" if hazir else "Gözden geçirin",
            "gerekceler": gerekceler,
        }

    @staticmethod
    def _gerekceler(oz: dict) -> list[str]:
        """İnsan-okur açıklama: hangi sinyaller kaliteyi düşürüyor?"""
        g = []
        if oz["abarti_isareti"] > 0:
            g.append(f"{oz['abarti_isareti']} abartı/ispatsız ifade")
        if oz["klise_isareti"] > 0:
            g.append(f"{oz['klise_isareti']} klişe kalıp")
        if oz["duygu_yogunlugu"] > 0.03:
            g.append("aşırı pazarlamacı ton")
        if oz["seo_kapsami"] == 0:
            g.append("hiç SEO anahtar kelimesi yok")
        if oz["kelime_sayisi"] < 15:
            g.append("içerik çok kısa")
        if oz["hikaye_ipucu"] == 0:
            g.append("üretim/öykü ipucu yok")
        return g


# ---------------------------------------------------------------------------
def egit_bellekte(veri_yolu: Path | str | None = None) -> dict | None:
    """
    Model dosyası yoksa etiketli CSV'den hızlıca (grafik/GridSearch/eval olmadan)
    bir model eğitip paket sözlüğü döndürür. Streamlit Cloud gibi model ikilisinin
    repoda bulunmadığı ortamlarda kalite ön-filtresini kendi kendine kurar.

    Ayrıntılı eğitim/değerlendirme için kalite_egit.py kullanılır; bu yalnızca
    çalışır bir model için hafif yedektir. sklearn/CSV yoksa None döner (rozet gizlenir).
    """
    veri_yolu = Path(veri_yolu or (_KOK / "data" / "kalite_etiketli.csv"))
    if not veri_yolu.exists():
        return None
    try:
        import numpy as np
        import pandas as pd
        from scipy.sparse import hstack
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import StandardScaler

        df = (pd.read_csv(veri_yolu)
              .dropna(subset=["metin", "hedef"]).drop_duplicates(subset=["metin"]))
        vekt = TfidfVectorizer(max_features=500, ngram_range=(1, 2), min_df=2)
        X_txt = vekt.fit_transform(df["metin"].map(metni_temizle))
        X_num = np.array([oznitelik_vektoru(m, k)
                          for m, k in zip(df["metin"], df["kategori"])], dtype=float)
        scaler = StandardScaler()
        X = hstack([X_txt, scaler.fit_transform(X_num)])
        model = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                       random_state=42)
        model.fit(X, df["hedef"].astype(int).values)
        return {"model": model, "vektorizer": vekt, "scaler": scaler, "esik": 0.5,
                "sayisal_oznitelikler": SAYISAL_OZNITELIKLER}
    except Exception:
        return None


# Modül düzeyinde tek örnek (arayüz tekrar tekrar yüklemesin diye).
_model_ornegi: KaliteModeli | None = None


def model_al() -> KaliteModeli:
    global _model_ornegi
    if _model_ornegi is None:
        _model_ornegi = KaliteModeli()
    return _model_ornegi


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ornekler = [
        ("El örgüsü bebek battaniyesi. Anneannemden öğrendiğim desenle tamamen "
         "elde örüyorum, bir tanesi üç günümü alıyor. Organik pamuk ipliği "
         "kullanıyorum.", "Tekstil / El sanatı"),
        ("Dünyanın en iyi battaniyesi! Mucize gibi, garantili, kaçırmayın, "
         "hemen alın, son fırsat!", "Tekstil / El sanatı"),
    ]
    m = model_al()
    print("Model mevcut mu?", m.mevcut(), "\n")
    for metin, kat in ornekler:
        print(">", metin[:60], "…")
        print(" ", m.tahmin(metin, kat), "\n")
