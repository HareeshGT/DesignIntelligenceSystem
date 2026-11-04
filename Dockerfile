FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DIS_DATABASE_PATH=/data/design_intelligence.db

WORKDIR /app

RUN addgroup --system dis && adduser --system --ingroup dis --home /app dis

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install --upgrade pip && pip install . && playwright install --with-deps chromium

RUN find /ms-playwright -type f -name chrome_sandbox -exec chown root:root {} \\; -exec chmod 4755 {} \\; && mkdir -p /data && chown -R dis:dis /app /data
USER dis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
