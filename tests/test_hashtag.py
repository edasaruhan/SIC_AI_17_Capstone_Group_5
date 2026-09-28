# -*- coding: utf-8 -*-
"""
uret.hashtag_denetle testleri — API anahtarı ve internet gerektirmez.

    python tests/test_hashtag.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from uret import hashtag_denetle  # noqa: E402

BATTANIYE = ("El örgüsü bebek battaniyesi yapıyorum. Organik pamuk ipliği kullanıyorum, "
             "tamamen elde örüyorum.")


def test_anlatimda_olmayan_malzeme_cikarilir_olan_kalir():
    # Canlı testte gerçekten üretilen çıktı: ürün kumaş değil ama #doğalkumaş yazıldı.
    metin = "**🔎 Arayanların yazdığı**\n#elyapımı #elemeği #doğalkumaş #organikpamuk"
    temiz, cikan = hashtag_denetle(metin, BATTANIYE)
    assert cikan == ["#doğalkumaş"]
    assert temiz == "**🔎 Arayanların yazdığı**\n#elyapımı #elemeği #organikpamuk"


def test_klise_ve_iddia_her_zaman_cikarilir():
    anlatim = BATTANIYE + " Göz nuru, mucize gibi bir iş."   # anlatımda geçse bile
    _, cikan = hashtag_denetle("#elemekgöznuru #mucizebattaniye #şifalıbitki #eniyi #bebek",
                               anlatim)
    assert cikan == ["#elemekgöznuru", "#mucizebattaniye", "#şifalıbitki", "#eniyi"]


def test_ekli_ve_buyuk_harfli_anlatimda_kok_bulunur():
    # "katkı maddesi yok" → #katkısız uygun; "İpek" büyük harfle yazılmış → #ipekeşarp uygun
    temiz, cikan = hashtag_denetle("#katkısız #ipekeşarp #yüneşarp",
                                   "İpek eşarp ve salça yapıyorum. Hiçbir katkı maddesi yok.")
    assert cikan == ["#yüneşarp"] and temiz == "#katkısız #ipekeşarp"


def test_tekrarlanan_etiket_bir_kez_raporlanir_satirlar_korunur():
    metin = "#doğalkumaş #elyapımı\n\n**📋 En iyi 5**\n#elyapımı #doğalkumaş"
    temiz, cikan = hashtag_denetle(metin, BATTANIYE)
    assert cikan == ["#doğalkumaş"]
    assert temiz == "#elyapımı\n\n**📋 En iyi 5**\n#elyapımı"


if __name__ == "__main__":
    testler = [(ad, f) for ad, f in sorted(globals().items()) if ad.startswith("test_")]
    hatali = 0
    for ad, f in testler:
        try:
            f()
            print(f"  OK    {ad}")
        except Exception as hata:
            hatali += 1
            print(f"  HATA  {ad}: {hata!r}")
    print(f"\n{len(testler) - hatali}/{len(testler)} test geçti")
    sys.exit(1 if hatali else 0)
