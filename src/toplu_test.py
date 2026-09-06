# -*- coding: utf-8 -*-
"""
Üretken Kadın — Toplu test (A2.4)

data/ornekler.csv içindeki tüm ürün anlatımlarını sırayla çalıştırır,
çıktıları kaydeder ve özet metrikleri raporlar.

Kullanım:
    python src/toplu_test.py                      # 10 örnek, few_shot
    python src/toplu_test.py --teknik zero_shot   # baseline üretmek için
    python src/toplu_test.py --limit 3            # hızlı deneme (3 örnek)
    python src/toplu_test.py --hepsi              # üç tekniği de çalıştır (karşılaştırma)

Çıktılar `ciktilar/` klasörüne iki biçimde yazılır:
    *.csv  -> analiz için (pandas ile okunur)
    *.md   -> gözle okumak ve Barış'a göstermek için
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import prompts
import uret

# Proje kök klasörü (bu dosya src/ içinde olduğu için bir üst dizin)
KOK = Path(__file__).resolve().parent.parent
VERI = KOK / "data" / "ornekler.csv"
CIKTI_KLASORU = KOK / "ciktilar"

BEKLEME_SN = 2.0     # ücretsiz katman kotasını zorlamamak için istekler arası bekleme


# ---------------------------------------------------------------------------
def ornekleri_oku(limit: int | None = None) -> list[dict]:
    if not VERI.exists():
        raise FileNotFoundError(f"Örnek dosyası bulunamadı: {VERI}")
    with open(VERI, encoding="utf-8") as f:
        satirlar = list(csv.DictReader(f))
    return satirlar[:limit] if limit else satirlar


# ---------------------------------------------------------------------------
def _gecici_hata_mi(hata: Exception) -> bool:
    """503 (sunucu yogun) ve 429 (kota) gecicidir; beklenip tekrar denenebilir."""
    metin = str(hata)
    return any(k in metin for k in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                                    "high demand", "try again"))


def tek_ornek_calistir(client, satir: dict, teknik: str,
                       deneme_hakki: int = 3) -> dict:
    """Bir örneği çalıştırır; geçici hatalarda bekleyip tekrar dener."""
    kategori = satir["kategori"]
    kelimeler = prompts.KATEGORI_KELIMELERI.get(kategori, [])
    son_hata = None

    for deneme in range(1, deneme_hakki + 1):
        try:
            sonuc = uret.icerik_uret(
                anlatim=satir["anlatim"],
                kategori=kategori,
                teknik=teknik,
                trends_kullan=False,   # test metrikleri sabit kelime setiyle ölçülür
                client=client,
            )
            break                              # basarili, donguden cik
        except Exception as e:
            son_hata = e
            if _gecici_hata_mi(e) and deneme < deneme_hakki:
                bekleme = 5 * deneme           # 5 sn, sonra 10 sn
                print(f"(geçici hata, {bekleme} sn sonra tekrar) ", end="", flush=True)
                time.sleep(bekleme)
                continue
            sonuc = None
            break

    if sonuc is not None:
        tum_metin = f"{sonuc.instagram} {sonuc.shopier}"
        return {
            "id": satir["id"],
            "kategori": kategori,
            "teknik": teknik,
            "anlatim": satir["anlatim"],
            "instagram": sonuc.instagram,
            "shopier": sonuc.shopier,
            "ig_kelime": len(sonuc.instagram.split()),
            "sh_kelime": len(sonuc.shopier.split()),
            "seo_kapsam": uret.seo_kapsami(tum_metin, kelimeler),
            "seo_toplam": len(kelimeler),
            "klise": uret.klise_sayisi(tum_metin),
            "benzerlik": round(uret.kanal_benzerligi(sonuc.instagram, sonuc.shopier), 2),
            "hata": "",
        }

    # Tum denemeler basarisiz oldu
    return {
        "id": satir["id"], "kategori": kategori, "teknik": teknik,
        "anlatim": satir["anlatim"], "instagram": "", "shopier": "",
        "ig_kelime": 0, "sh_kelime": 0, "seo_kapsam": 0,
        "seo_toplam": len(kelimeler), "klise": 0, "benzerlik": 0.0,
        "hata": str(son_hata)[:200],
    }


# ---------------------------------------------------------------------------
def calistir(teknik: str, limit: int | None) -> list[dict]:
    ornekler = ornekleri_oku(limit)
    client = uret.istemci_olustur()
    sonuclar = []

    print(f"\n{'=' * 70}")
    print(f"TOPLU TEST  ·  teknik: {teknik}  ·  {len(ornekler)} örnek")
    print(f"{'=' * 70}")

    for i, satir in enumerate(ornekler, 1):
        onizleme = satir["anlatim"][:52].replace("\n", " ")
        print(f"  [{i}/{len(ornekler)}] {satir['kategori'][:22]:<22} {onizleme}…",
              end=" ", flush=True)

        sonuc = tek_ornek_calistir(client, satir, teknik)
        sonuclar.append(sonuc)

        if sonuc["hata"]:
            print("HATA")
        else:
            print(f"OK  (SEO {sonuc['seo_kapsam']}/{sonuc['seo_toplam']})")

        if i < len(ornekler):
            time.sleep(BEKLEME_SN)

    return sonuclar


# ---------------------------------------------------------------------------
def kaydet(sonuclar: list[dict], teknik: str) -> tuple[Path, Path]:
    CIKTI_KLASORU.mkdir(exist_ok=True)
    damga = datetime.now().strftime("%Y%m%d_%H%M")
    csv_yol = CIKTI_KLASORU / f"toplu_{teknik}_{damga}.csv"
    md_yol = CIKTI_KLASORU / f"toplu_{teknik}_{damga}.md"

    # CSV — analiz için
    alanlar = ["id", "kategori", "teknik", "anlatim", "instagram", "shopier",
               "ig_kelime", "sh_kelime", "seo_kapsam", "seo_toplam",
               "klise", "benzerlik", "hata"]
    with open(csv_yol, "w", encoding="utf-8-sig", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=alanlar)
        yazici.writeheader()
        yazici.writerows(sonuclar)

    # Markdown — gözle okumak için
    with open(md_yol, "w", encoding="utf-8") as f:
        f.write(f"# Toplu test — {teknik}\n\n")
        f.write(f"Tarih: {datetime.now():%d.%m.%Y %H:%M}  ·  "
                f"Model: `{uret.MODEL}`  ·  Örnek sayısı: {len(sonuclar)}\n\n---\n\n")
        for s in sonuclar:
            f.write(f"## {s['id']} · {s['kategori']}\n\n")
            f.write(f"**Üreticinin anlatımı:**\n> {s['anlatim']}\n\n")
            if s["hata"]:
                f.write(f"**HATA:** `{s['hata']}`\n\n---\n\n")
                continue
            f.write(f"**Instagram** ({s['ig_kelime']} kelime)\n\n{s['instagram']}\n\n")
            f.write(f"**Shopier** ({s['sh_kelime']} kelime)\n\n{s['shopier']}\n\n")
            f.write(f"*SEO kapsamı: {s['seo_kapsam']}/{s['seo_toplam']}  ·  "
                    f"klişe: {s['klise']}  ·  kanal benzerliği: {s['benzerlik']}*"
                    f"\n\n---\n\n")

    return csv_yol, md_yol


# ---------------------------------------------------------------------------
def ozet(sonuclar: list[dict]) -> None:
    basarili = [s for s in sonuclar if not s["hata"]]
    hatali = len(sonuclar) - len(basarili)

    print(f"\n{'-' * 70}")
    print("ÖZET")
    print(f"{'-' * 70}")
    print(f"  Başarılı            : {len(basarili)}/{len(sonuclar)}"
          + (f"   (hatalı: {hatali})" if hatali else ""))

    if not basarili:
        print("  Hiçbir örnek üretilemedi — hata mesajlarına bakın.")
        return

    ort = lambda k: sum(s[k] for s in basarili) / len(basarili)
    kapsam_orani = (sum(s["seo_kapsam"] for s in basarili) /
                    max(sum(s["seo_toplam"] for s in basarili), 1))

    print(f"  Ort. Instagram uzunluğu : {ort('ig_kelime'):.0f} kelime")
    print(f"  Ort. Shopier uzunluğu   : {ort('sh_kelime'):.0f} kelime")
    print(f"  Ort. SEO kapsamı        : {ort('seo_kapsam'):.1f}/"
          f"{ort('seo_toplam'):.0f}  (%{kapsam_orani * 100:.0f})")
    print()
    print(f"  KALİTE (düşük olması iyi):")
    klise_toplam = sum(s["klise"] for s in basarili)
    print(f"    Klişe kalıp sayısı    : {klise_toplam} toplam, "
          f"{ort('klise'):.1f} ortalama")
    print(f"    Kanal benzerliği      : {ort('benzerlik'):.2f}  "
          f"(0 = tamamen farklı, 1 = aynı)")

    # Kategori kırılımı — hangi kategoride daha iyi çalışıyor?
    print(f"\n  Kategoriye göre SEO kapsamı:")
    kategoriler = sorted({s["kategori"] for s in basarili})
    for kat in kategoriler:
        grup = [s for s in basarili if s["kategori"] == kat]
        k = sum(s["seo_kapsam"] for s in grup) / len(grup)
        t = grup[0]["seo_toplam"]
        print(f"    {kat:<24} {k:.1f}/{t}   ({len(grup)} örnek)")


# ---------------------------------------------------------------------------
def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Üretken Kadın toplu test")
    ayristirici.add_argument("--teknik", default="few_shot",
                             choices=["zero_shot", "few_shot", "chain_of_thought"])
    ayristirici.add_argument("--limit", type=int, default=None,
                             help="Kaç örnek çalıştırılsın (hızlı deneme için)")
    ayristirici.add_argument("--hepsi", action="store_true",
                             help="Üç tekniği de çalıştır (prompt karşılaştırması)")
    args = ayristirici.parse_args()

    teknikler = (["zero_shot", "few_shot", "chain_of_thought"]
                 if args.hepsi else [args.teknik])

    for teknik in teknikler:
        try:
            sonuclar = calistir(teknik, args.limit)
        except Exception as e:
            print(f"\nÇalıştırılamadı: {e}")
            raise SystemExit(1)

        ozet(sonuclar)
        csv_yol, md_yol = kaydet(sonuclar, teknik)
        print(f"\n  Kaydedildi:")
        print(f"    {csv_yol.relative_to(KOK)}   (analiz için)")
        print(f"    {md_yol.relative_to(KOK)}   (okumak için)")

    print()


if __name__ == "__main__":
    main()
