# Üretken Kadın REST API — Render, Google Cloud Run ve benzeri platformlar için
#   docker build -t uretken-kadin-api .
#   docker run -p 8000:8000 --env-file .env uretken-kadin-api
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/ src/
COPY data/kalite_etiketli.csv data/kalite_etiketli.csv

# root olmayan kullanıcı; data/ yazılabilir (Google Trends önbelleği)
RUN useradd --create-home uygulama && chown -R uygulama /app
USER uygulama

EXPOSE 8000
# Tek işçi: kota sayaçları bellekte (bkz. API.md → Ölçekleme). Platform PORT değişkenini verir.
# --no-access-log: uvicorn'un istemci IP'si içeren erişim günlüğü kapalı; api.py yalnızca yol,
# durum, iş ortağı adı ve süreyi yazar (KVKK veri minimizasyonu, API.md ile tutarlı).
CMD ["sh", "-c", "uvicorn api:app --app-dir src --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --no-access-log"]
