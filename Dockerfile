FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DIS_DATABASE_PATH=/data/design_intelligence.db

WORKDIR /app

# Playwright's bundled Node runtime links libatomic.so.1. Install it before
# invoking the Playwright CLI (including "playwright install --with-deps").
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system dis && adduser --system --ingroup dis --home /app dis

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install --upgrade pip && pip install . && playwright install --with-deps chromium

RUN find /ms-playwright -type f -name chrome_sandbox -exec chown root:root {} + && find /ms-playwright -type f -name chrome_sandbox -exec chmod 4755 {} + && mkdir -p /data && chown -R dis:dis /app /data
USER dis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=3)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
