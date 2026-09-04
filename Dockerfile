# ApplyJin backend — production image for Render / any Docker host.
# Runs the FastAPI app (landing API + Console API + PDF/LaTeX generation).
# The browser auto-fill agent is NOT included by design: it belongs on
# your own machine where it opens your own browser.

FROM python:3.12-slim

# WeasyPrint native deps + fonts + TeX Live (pdflatex for the LaTeX-first
# resume/cover-letter PDF pipeline).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    libcairo2 libglib2.0-0 libfontconfig1 fonts-liberation \
    texlive-latex-base texlive-latex-recommended texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend install (scrape/rag/pdf/web extras — no playwright/browser)
COPY pyproject.toml README.md LICENSE ./
COPY hermes ./hermes
COPY config ./config
COPY scripts ./scripts
RUN pip install --no-cache-dir -e ".[scrape,rag,pdf,web]"

# Frontend build (landing + Console) — built on the host or in CI and
# committed is NOT required; Render builds it here so / serves the SPA.
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm install --silent 2>/dev/null || true
COPY frontend ./frontend
RUN cd frontend && npm install --silent && npx vite build

# Non-root runtime user
RUN useradd -m applyjin && mkdir -p /app/data && chown -R applyjin:applyjin /app
USER applyjin

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 0.0.0.0 is required by Render's port forwarding
CMD ["hermes", "serve", "--host", "0.0.0.0", "--port", "8000"]
