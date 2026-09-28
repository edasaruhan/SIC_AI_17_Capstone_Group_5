# Üretken Kadın — değişiklikleri iki depoya birden yükler
#
#   origin  : Tugce-hub/Uretken_Kadin      → Render buradan yayın yapar (site + API)
#   samsung : edasaruhan/SIC_AI_17_...     → capstone deposu (hoca ve ekip görür, herkese açık)
#
# Kullanım (proje klasöründe):  .\ikisine_yukle.ps1
# Önce main dalındaki commit'lerinizi yapın; bu betik yalnızca yükler.

# Not: git ilerleme iletilerini stderr'e yazar; bu yüzden "Stop" kullanmayıp çıkış kodlarına bakıyoruz.
function Calistir([string[]]$arg) {
    git @arg
    if ($LASTEXITCODE -ne 0) { throw "Komut başarısız: git $($arg -join ' ')" }
}

if ((git rev-parse --abbrev-ref HEAD) -ne "main") { throw "main dalında olmalısınız." }
if (git status --porcelain) { throw "Kaydedilmemiş değişiklik var; önce commit edin." }

Write-Host "1/3 - Uretken_Kadin deposuna yukleniyor (Render burayi izler)..." -ForegroundColor Cyan
Calistir @("push", "origin", "main")

Write-Host "2/3 - Capstone deposu guncelleniyor..." -ForegroundColor Cyan
Calistir @("checkout", "samsung-main")
try {
    Calistir @("merge", "main", "--no-edit")
    Calistir @("push", "samsung", "samsung-main:main")
} finally {
    Calistir @("checkout", "main")
}

Write-Host "3/3 - Bitti. Render birkac dakika icinde siteyi guncelleyecek." -ForegroundColor Green
