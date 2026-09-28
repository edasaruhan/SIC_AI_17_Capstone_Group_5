# -*- coding: utf-8 -*-
"""
Üretken Kadın — İçerik kalite modeli EĞİTİMİ

"Data Prep & Model Exploration" dökümanındaki hattı gerçek kodla kurar:
  1. Veri yükle (data/kalite_etiketli.csv) ve temizle
  2. Öznitelik mühendisliği: sayısal öznitelikler (kalite.py) + TF-IDF(500)
  3. Dönüşüm: StandardScaler (sayısal) + TF-IDF (metin) → hstack
  4. Model: RandomForest + GridSearchCV + StratifiedKFold(5), skor = F1
  5. Değerlendirme: accuracy / precision / recall / F1 / ROC-AUC,
     confusion matrix ve ROC eğrisi (PNG), sınıflandırma raporu
  6. Modeli kaydet: models/kalite_modeli.joblib  (kalite.py bunu yükler)

Kullanım:
    python src/kalite_egit.py
    python src/kalite_egit.py --hizli      # küçük ızgara (hızlı deneme)

Not: Metrikler prototip veri seti üzerinde hesaplanır; saha pilotunda gerçek
insan etiketleriyle güncellenecektir (bkz. kalite_veri_uret.py).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler

import matplotlib
matplotlib.use("Agg")            # başsız (grafik penceresi açmadan kaydet)
import matplotlib.pyplot as plt

import joblib

import kalite

_KOK = Path(__file__).resolve().parent.parent
VERI = _KOK / "data" / "kalite_etiketli.csv"
MODEL_DIZINI = _KOK / "models"
CIKTI_DIZINI = _KOK / "ciktilar" / "model"

ANA = "#9C4368"; KOYU = "#4A2138"        # arayüzle uyumlu renkler


# ---------------------------------------------------------------------------
def veri_yukle() -> pd.DataFrame:
    if not VERI.exists():
        raise FileNotFoundError(
            f"{VERI} yok. Önce çalıştırın: python src/kalite_veri_uret.py")
    df = pd.read_csv(VERI)
    df = df.dropna(subset=["metin", "hedef"]).drop_duplicates(subset=["metin"])
    df["metin_temiz"] = df["metin"].apply(kalite.metni_temizle)
    # aşırı kısa aykırıları at (dökümandaki temizlik adımı) — ama sınıf dengesini koru
    df = df[df["metin_temiz"].str.split().apply(len) >= 2].reset_index(drop=True)
    return df


def oznitelik_matrisi(df: pd.DataFrame):
    """TF-IDF (metin) + ölçeklenmiş sayısal öznitelikleri birleştirir."""
    vekt = TfidfVectorizer(max_features=500, ngram_range=(1, 2), min_df=2)
    X_txt = vekt.fit_transform(df["metin_temiz"])

    sayisal = np.array([
        kalite.oznitelik_vektoru(m, k)
        for m, k in zip(df["metin"], df["kategori"])
    ], dtype=float)
    scaler = StandardScaler()
    X_num = scaler.fit_transform(sayisal)

    X = hstack([X_txt, X_num])
    y = df["hedef"].astype(int).values
    return X, y, vekt, scaler


# ---------------------------------------------------------------------------
def egit(hizli: bool = False):
    df = veri_yukle()
    print(f"Veri: {len(df)} örnek  ·  yüksek {int(df['hedef'].sum())}  ·  "
          f"düşük {int((df['hedef'] == 0).sum())}")

    X, y, vekt, scaler = oznitelik_matrisi(df)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y,
                                          random_state=42)

    izgara = ({"n_estimators": [200], "max_depth": [None, 12]} if hizli else
              {"n_estimators": [200, 400], "max_depth": [None, 12, 20]})
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    arama = GridSearchCV(
        RandomForestClassifier(class_weight="balanced", random_state=42),
        izgara, cv=cv, scoring="f1", n_jobs=-1)
    arama.fit(Xtr, ytr)
    model = arama.best_estimator_
    print("En iyi parametreler:", arama.best_params_)

    # ---- Değerlendirme ----
    tahmin = model.predict(Xte)
    olasilik = model.predict_proba(Xte)[:, 1]
    metrikler = {
        "dogruluk": round(accuracy_score(yte, tahmin), 3),
        "kesinlik_yuksek": round(precision_score(yte, tahmin), 3),
        "duyarlilik_yuksek": round(recall_score(yte, tahmin), 3),
        "f1_yuksek": round(f1_score(yte, tahmin), 3),
        "duyarlilik_dusuk": round(recall_score(yte, tahmin, pos_label=0), 3),
        "roc_auc": round(roc_auc_score(yte, olasilik), 3),
        "en_iyi_parametreler": arama.best_params_,
        "egitim_boyutu": int(Xtr.shape[0]),
        "test_boyutu": int(Xte.shape[0]),
    }

    print("\n" + "=" * 55 + "\nDEĞERLENDİRME (test seti)\n" + "=" * 55)
    for k, v in metrikler.items():
        if k not in ("en_iyi_parametreler",):
            print(f"  {k:<22}: {v}")
    print("\n" + classification_report(yte, tahmin,
                                       target_names=["Düşük", "Yüksek"]))

    # ---- Grafikler ----
    CIKTI_DIZINI.mkdir(parents=True, exist_ok=True)
    _confusion_ciz(yte, tahmin)
    _roc_ciz(yte, olasilik, metrikler["roc_auc"])
    _oznitelik_onemi_ciz(model, vekt)

    # ---- Kaydet ----
    MODEL_DIZINI.mkdir(parents=True, exist_ok=True)
    paket = {"model": model, "vektorizer": vekt, "scaler": scaler,
             "esik": 0.5, "sayisal_oznitelikler": kalite.SAYISAL_OZNITELIKLER,
             "metrikler": metrikler}
    joblib.dump(paket, kalite.MODEL_YOLU)
    (CIKTI_DIZINI / "metrikler.json").write_text(
        json.dumps(metrikler, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nKaydedildi:")
    print(f"  {kalite.MODEL_YOLU.relative_to(_KOK)}   (arayüz bunu yükler)")
    print(f"  {(CIKTI_DIZINI / 'metrikler.json').relative_to(_KOK)}")
    print(f"  {CIKTI_DIZINI.relative_to(_KOK)}/*.png   (confusion, ROC, öznitelik önemi)")
    return metrikler


# ---------------------------------------------------------------------------
def _confusion_ciz(y, tahmin):
    cm = confusion_matrix(y, tahmin)
    fig, ax = plt.subplots(figsize=(4.4, 4))
    ax.imshow(cm, cmap="PuRd")
    ax.set_xticks([0, 1], ["Düşük", "Yüksek"])
    ax.set_yticks([0, 1], ["Düşük", "Yüksek"])
    ax.set_xlabel("Tahmin"); ax.set_ylabel("Gerçek")
    ax.set_title("Confusion Matrix (test seti)")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    fontsize=15, fontweight="bold",
                    color="white" if cm[i, j] > cm.max() / 2 else KOYU)
    fig.tight_layout(); fig.savefig(CIKTI_DIZINI / "confusion_matrix.png", dpi=130)
    plt.close(fig)


def _roc_ciz(y, olasilik, auc):
    fpr, tpr, _ = roc_curve(y, olasilik)
    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.plot(fpr, tpr, color=ANA, lw=2, label=f"ROC (AUC = {auc})")
    ax.plot([0, 1], [0, 1], "--", color="#bbb", lw=1)
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Eğrisi"); ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(CIKTI_DIZINI / "roc_egrisi.png", dpi=130)
    plt.close(fig)


def _oznitelik_onemi_ciz(model, vekt):
    """Sayısal özniteliklerin model içindeki önem sırası (yorumlanabilirlik)."""
    n_txt = len(vekt.get_feature_names_out())
    onem = model.feature_importances_
    sayisal_onem = onem[n_txt:]        # sayısal öznitelikler TF-IDF'ten sonra eklendi
    adlar = kalite.SAYISAL_OZNITELIKLER
    sira = np.argsort(sayisal_onem)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.barh([adlar[i] for i in sira], sayisal_onem[sira], color=ANA)
    ax.set_title("Sayısal öznitelik önemleri (Random Forest)")
    fig.tight_layout(); fig.savefig(CIKTI_DIZINI / "oznitelik_onemi.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Üretken Kadın kalite modeli eğitimi")
    ap.add_argument("--hizli", action="store_true", help="küçük ızgarayla hızlı eğit")
    egit(hizli=ap.parse_args().hizli)


if __name__ == "__main__":
    main()
