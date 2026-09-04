# ApplyJin — production image for Render / any Docker host.
# Runs the FastAPI app (landing API + Console API + PDF/LaTeX generation).
# The browser auto-fill agent is NOT included by design: it belongs on
# your own machine where it opens your own browser.

# ---- Stage 1: build the frontend (landing page + Console) ----------
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --silent
COPY frontend ./
RUN npx vite build

# ---- Stage 2: the backend runtime -----------------------------------
FROM python:3.12-slim

# WeasyPrint native deps + fonts + TeX Live (pdflatex for the LaTeX-first
# resume/cover-letter PDF pipeline).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    libcairo2 libglib2.0-0 libfontconfig1 fonts-liberation \
    texlive-latex-base texlive-latex-recommended texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend install. chromadb is installed directly (not via the `rag`
# extra, which pulls sentence-transformers -> torch ~2GB). The runtime
# uses ChromaDB's bundled ONNX MiniLM embedder — real semantic
# embeddings with zero torch dependency.
COPY pyproject.toml README.md LICENSE ./
COPY hermes ./hermes
COPY config ./config
COPY scripts ./scripts
RUN pip install --no-cache-dir -e ".[scrape,pdf,web]" chromadb

# Frontend dist from stage 1 — served by FastAPI at / and /dashboard
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Non-root runtime user
RUN useradd -m applyjin && mkdir -p /app/data && chown -R applyjin:applyjin /app
USER applyjin

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 0.0.0.0 is required by Render's port forwarding
CMD ["hermes", "serve", "--host", "0.0.0.0", "--port", "8000"]
