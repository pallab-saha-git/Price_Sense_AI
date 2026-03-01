"""
gunicorn.conf.py — Production WSGI server configuration
=========================================================
Usage:
    gunicorn app:server -c gunicorn.conf.py

Install:
    pip install gunicorn
"""
import multiprocessing
import os

# ── Worker config ──────────────────────────────────────────────────────────────
workers     = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"           # use "gthread" if you need threaded workers
threads     = 1
worker_connections = 1000

# ── Network ────────────────────────────────────────────────────────────────────
bind        = f"0.0.0.0:{os.getenv('PORT', '8050')}"
backlog     = 2048

# ── Timeouts ───────────────────────────────────────────────────────────────────
timeout     = 120               # seconds; increase if ML inference is slow
keepalive   = 5
graceful_timeout = 30

# ── Logging ────────────────────────────────────────────────────────────────────
accesslog   = "-"               # stdout
errorlog    = "-"               # stderr
loglevel    = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# ── Security & process ─────────────────────────────────────────────────────────
limit_request_line   = 4094
limit_request_fields = 100
max_requests         = 1000     # recycle workers after N requests (memory leak guard)
max_requests_jitter  = 100      # randomise to avoid thundering herd
preload_app          = True     # load app before forking (memory sharing on Linux)

# ── Hooks ──────────────────────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("🚀 Gunicorn starting — Price Sense AI")

def worker_exit(server, worker):
    server.log.info(f"Worker {worker.pid} exiting.")
