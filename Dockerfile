FROM python:3.11-slim

# ── Non-root user for security ────────────────────────────────────────────────
RUN groupadd --gid 1001 appgroup \
 && useradd  --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# build-essential + libgomp1 required by Prophet / Stan.
# curl kept for health-check and optional manual debugging.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (cached layer — rebuilt only on requirements change) ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Install CmdStan binary into Prophet's bundled path ───────────────────────
# Prophet 1.1.x expects CmdStan at  <prophet_pkg>/stan_model/cmdstan-X.Y.Z/
# and calls cmdstanpy.set_cmdstan_path() to that location internally, ignoring
# the system CMDSTAN env var.  We must install CmdStan to THAT directory.
RUN python3 -c "\
import pathlib, cmdstanpy, prophet; \
stan_dir = pathlib.Path(prophet.__file__).parent / 'stan_model'; \
stan_dir.mkdir(parents=True, exist_ok=True); \
print('Installing CmdStan into:', stan_dir); \
cmdstanpy.install_cmdstan(dir=str(stan_dir), version='2.33.1', overwrite=True); \
import glob; \
installed = glob.glob(str(stan_dir / 'cmdstan-*')); \
print('Installed:', installed); \
"

# ── Prophet: create makefile stub + fix permissions ──────────────────────────
# validate_cmdstan_path() only checks that 'makefile' exists (not contents).
# Prophet's Stan model is pre-compiled as prophet_model.bin; CmdStan source
# is NOT needed — only the binaries (stanc, stansummary, diagnose) are needed.
RUN touch /usr/local/lib/python3.11/site-packages/prophet/stan_model/cmdstan-2.33.1/makefile \
 && find /usr/local/lib/python3.11/site-packages/prophet/stan_model -type d -exec chmod 755 {} + \
 && find /usr/local/lib/python3.11/site-packages/prophet/stan_model -type f -exec chmod 644 {} + \
 && chmod 755 /usr/local/lib/python3.11/site-packages/prophet/stan_model/cmdstan-2.33.1/bin/* \
 && chmod 755 /usr/local/lib/python3.11/site-packages/prophet/stan_model/prophet_model.bin

# ── Application code (no .env — see .dockerignore) ───────────────────────────
COPY . .

# ── Generate synthetic demo data CSVs into the image ─────────────────────────
# data/synthetic/ is excluded from .dockerignore (not committed to git) so we
# generate the CSVs here.  They are baked into the image layer and used when
# the container runs WITHOUT a volume mount (e.g. docker run / CI).
# When docker-compose mounts ./data:/app/data the host path takes precedence;
# the CMD startup guard (see below) handles that case.
RUN python data/synthetic_generator.py

# ── Ensure data & log directories exist and are writable ─────────────────────
# data/zip/ is created here so the non-root user can write to it even when
# the host volume is mounted (Docker creates the host dir if missing).
RUN mkdir -p /app/data/zip /app/logs \
 && chown -R appuser:appgroup /app

# ── Drop to non-root ─────────────────────────────────────────────────────────
USER appuser

# ── Port ─────────────────────────────────────────────────────────────────────
EXPOSE 8050

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD curl -f http://localhost:8050 || exit 1

# ── Startup sequence ─────────────────────────────────────────────────────────
#
# The app starts immediately with synthetic data.
# Dataset download + ingestion run in the BACKGROUND so port 8050 is always
# available within seconds of container start.
#
# Background job sequence:
#   Step 1 — Download dunnhumby zips (if not already present in data/zip/).
#             data/zip/ is volume-mounted (./data:/app/data in docker-compose.yml),
#             so pre-placed zips are found immediately and the download is skipped.
#   Step 2 — Run ingestion once all zips are present (sentinel guards re-runs).
#
# Direct download URLs (no login required as of March 2026):
#   CJ  : https://www.dunnhumby.com/wp-content/uploads/source-files/dunnhumby_The-Complete-Journey.zip
#   LGSR: https://www.dunnhumby.com/wp-content/uploads/source-files/dunnhumby_Let's-Get-Sort-of-Real-(Full-Part-N-of-9).zip
#
# Env vars that control the background job:
#   SKIP_DOWNLOAD=1   — skip all downloads (use pre-placed zips only)
#   SKIP_CJ=1         — skip The Complete Journey download
#   SKIP_LGSR=1       — skip the 9-part LGSR download (~4.3 GB)
#
CMD ["sh", "-c", "\
echo '======================================================' && \
echo '  Price Sense AI — startup' && \
echo '======================================================' && \
\
echo '[bg] Launching dataset download + ingestion in background …' && \
sh -c '\
  if [ \"${SKIP_DOWNLOAD:-0}\" != \"1\" ]; then \
    python data/download_dunnhumby.py \
      || echo \"[bg] WARNING: download had failures — will ingest whatever zips exist\"; \
  else \
    echo \"[bg] SKIP_DOWNLOAD=1 — skipping download\"; \
  fi && \
  if [ -d /app/data/zip ] && ls /app/data/zip/*.zip 1>/dev/null 2>&1 && [ ! -f /app/data/.dunnhumby_loaded ]; then \
    echo \"[bg] Zips found — starting dunnhumby ingestion …\" && \
    python data/load_dunnhumby.py \
      || echo \"[bg] WARNING: ingestion had errors\"; \
  elif [ -f /app/data/.dunnhumby_loaded ]; then \
    echo \"[bg] Sentinel present — skipping ingestion (already done)\"; \
  else \
    echo \"[bg] No zips in data/zip/ — using synthetic data only\"; \
  fi \
' >> /app/logs/dataset_pipeline.log 2>&1 & \
\
echo '[startup] Checking synthetic demo data …' && \
if [ ! -f /app/data/synthetic/products.csv ]; then \
  echo '[startup] Synthetic CSVs not found (fresh volume mount) — generating now …' && \
  python data/synthetic_generator.py \
    && echo '[startup] Synthetic data generated.' \
    || echo '[startup] WARNING: synthetic data generation had errors'; \
else \
  echo '[startup] Synthetic CSVs present — skipping generation.'; \
fi && \
\
echo '[app] Starting application server …' && \
if command -v gunicorn > /dev/null 2>&1; then \
  gunicorn app:server -c gunicorn.conf.py; \
else \
  python app.py; \
fi \
"]
