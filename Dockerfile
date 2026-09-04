FROM python:3.12-slim

# WeasyPrint native deps + fonts (PDF fallback inside the container).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    libcairo2 libglib2.0-0 libfontconfig1 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY hermes ./hermes
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[scrape,rag,pdf,web]"

# Playwright chromium for auto-fill + PDF (headless only inside docker).
RUN python -m playwright install chromium --with-deps || \
    python -m playwright install chromium

# Non-root user for safety.
RUN useradd -m hermes && mkdir -p /app/data && chown -R hermes:hermes /app
USER hermes

ENV HERMES_DATA=/app/data
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["hermes", "run", "--offline"]
