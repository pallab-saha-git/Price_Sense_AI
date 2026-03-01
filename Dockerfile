FROM python:3.11-slim

# ── Non-root user for security ────────────────────────────────────────────────
RUN groupadd --gid 1001 appgroup \
 && useradd  --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# ── System dependencies (Prophet / Stan require build tools + libgomp) ────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (cached layer — rebuilt only on requirements change) ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Application code (no .env — see .dockerignore) ───────────────────────────
COPY . .

# ── Ensure data & log directories exist and are writable ─────────────────────
RUN mkdir -p /app/data /app/logs \
 && chown -R appuser:appgroup /app

# ── Drop to non-root ─────────────────────────────────────────────────────────
USER appuser

# ── Port ─────────────────────────────────────────────────────────────────────
EXPOSE 8050

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8050 || exit 1

# ── Start with gunicorn in production; fall back to dev server if missing ────
CMD ["sh", "-c", \
    "if command -v gunicorn > /dev/null 2>&1; then \
       gunicorn app:server -c gunicorn.conf.py; \
     else \
       python app.py; \
     fi"]
