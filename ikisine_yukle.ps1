# Üretken Kadın — değişiklikleri iki depoya birden yükler
#
#   origin  : Tugce-hub/Uretken_Kadin      → Render buradan yayın yapar (site + API)
#   samsung : edasaruhan/SIC_AI_17_...     → capstone deposu (hoca ve ekip görür, herkese açık)
#
# Kullanım (proje klasöründe):  .\ikisine_yukle.ps1
# Önce main dalındaki commit'lerinizi yapın; bu betik yalnızca yükler.

$ErrorActionPreference = "Stop"

if ((git rev-parse --abbrev-ref HEAD) -ne "main") { throw "main dalında olmalısınız." }
if (git status --porcelain) { throw "Kaydedilmemiş değişiklik var; önce commit edin." }

Write-Host "1/3 · Uretken_Kadin deposuna yükleniyor (Render burayı izler)..." -ForegroundColor Cyan
git push origin main

Write-Host "2/3 · Capstone deposu güncelleniyor..." -ForegroundColor Cyan
git checkout samsung-main
try {
    git merge main --no-edit
    git push samsung samsung-main:main
} finally {
    git checkout main
}

Write-Host "3/3 · Bitti. Render birkaç dakika içinde siteyi güncelleyecek." -ForegroundColor Green
