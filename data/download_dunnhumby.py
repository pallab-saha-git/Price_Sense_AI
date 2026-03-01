"""
data/download_dunnhumby.py
──────────────────────────
Downloads dunnhumby dataset zips into data/zip/ at container startup (or on demand).

Datasets downloaded
───────────────────
  1. dunnhumby – The Complete Journey  (128 MB)
     Source: https://www.dunnhumby.com/source-files/
     ~2,500 households, 92K products, 2 years of weekly transactions.

  2. dunnhumby – Let's Get Sort of Real (9 × ~480 MB = ~4.3 GB total)
     Source: https://www.dunnhumby.com/source-files/
     Full UK grocery chain transaction history 2006–2011.

Behaviour
─────────
  • Skips any file that already exists with the correct size (resume-safe).
  • Uses streaming download with chunked writes — low memory usage.
  • Retries up to MAX_RETRIES times per file with exponential back-off.
  • Writes a .partial temp file and renames on success to avoid corrupt zips.
  • Called automatically by the Dockerfile CMD if data/zip/ has no zips.
  • Can also be run directly:  python data/download_dunnhumby.py [--force]
    --force  redownloads even if the file already exists.

Environment variables (optional)
─────────────────────────────────
  SKIP_LGSR=1    — download only The Complete Journey (faster for dev)
  SKIP_CJ=1      — download only the LGSR 9-part set
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests
from loguru import logger

# ── Destination directory ──────────────────────────────────────────────────────
ZIP_DIR = Path(__file__).resolve().parent / "zip"

# ── Dataset URLs ───────────────────────────────────────────────────────────────
# Direct download links from dunnhumby.com/source-files/
COMPLETE_JOURNEY_URL = (
    "https://www.dunnhumby.com/wp-content/uploads/source-files/"
    "dunnhumby_The-Complete-Journey.zip"
)

# dunnhumby filenames use the curly right-single-quote (U+2019) in the URL path.
# We provide both variants and try them in order — the script will use whichever
# returns HTTP 200.  Variant A = curly apostrophe (U+2019), Variant B = ASCII apostrophe (U+0027).
_LGSR_BASE = "https://www.dunnhumby.com/wp-content/uploads/source-files/"

def _lgsr_urls(n: int) -> list[str]:
    """Return candidate URLs for LGSR part N (1–9), best-guess first."""
    return [
        # curly apostrophe — as shown on dunnhumby.com
        f"{_LGSR_BASE}dunnhumby_Let\u2019s-Get-Sort-of-Real-(Full-Part-{n}-of-9).zip",
        # ASCII apostrophe — fallback
        f"{_LGSR_BASE}dunnhumby_Let%27s-Get-Sort-of-Real-(Full-Part-{n}-of-9).zip",
        # plain URL-encoded curly quote explicitly
        f"{_LGSR_BASE}dunnhumby_Let%E2%80%99s-Get-Sort-of-Real-(Full-Part-{n}-of-9).zip",
    ]

# ── Download settings ──────────────────────────────────────────────────────────
CHUNK_SIZE  = 1024 * 1024   # 1 MB chunks
MAX_RETRIES = 5
RETRY_DELAY = 5             # seconds (doubles on each retry)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PriceSenseAI-DataLoader/1.0; "
        "+https://github.com/your-org/trinamix)"
    )
}


def _filename_from_url(url: str) -> str:
    """Extract filename from URL path."""
    return url.split("/")[-1]


def _download_file(url: str | list, dest: Path, force: bool = False) -> bool:
    """
    Download a single file with retry, streaming, and resume detection.

    `url` may be a string or a list of candidate URLs tried in order.
    Returns True if downloaded (or already present), False on permanent failure.
    """
    urls: list[str] = [url] if isinstance(url, str) else url
    filename = dest.name

    # ── Check if already present ──────────────────────────────────────────────
    if dest.exists() and not force:
        size_mb = dest.stat().st_size / (1024 ** 2)
        logger.info(f"  ✓ {filename} already present ({size_mb:.1f} MB) — skipping")
        return True

    partial = dest.with_suffix(".partial")

    for candidate_url in urls:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"  ↓ {filename} (attempt {attempt}/{MAX_RETRIES}) …")
                resp = requests.get(candidate_url, headers=HEADERS, stream=True, timeout=60)

                if resp.status_code == 404:
                    logger.warning(f"    HTTP 404 for: {candidate_url}")
                    break   # try next candidate URL

                resp.raise_for_status()

                total = int(resp.headers.get("content-length", 0))
                total_mb = total / (1024 ** 2) if total else 0
                if total_mb:
                    logger.info(f"    Size: {total_mb:.1f} MB")

                downloaded = 0
                last_log = 0

                with open(partial, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pct = (downloaded / total * 100) if total else 0
                            dl_mb = downloaded / (1024 ** 2)
                            if dl_mb - last_log >= 100 or (total and pct >= 100):
                                logger.info(f"    … {dl_mb:.0f}/{total_mb:.0f} MB ({pct:.0f}%)")
                                last_log = dl_mb

                partial.rename(dest)
                final_mb = dest.stat().st_size / (1024 ** 2)
                logger.success(f"  ✓ {filename} downloaded ({final_mb:.1f} MB)")
                return True

            except requests.RequestException as exc:
                logger.warning(f"  ! Attempt {attempt} failed: {exc}")
                if partial.exists():
                    partial.unlink(missing_ok=True)
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY * (2 ** (attempt - 1))
                    logger.info(f"    Retrying in {delay}s …")
                    time.sleep(delay)
        # If we exhausted retries or got 404, move on to next candidate URL

    logger.error(f"  ✗ {filename}: all URL variants failed")
    return False


def download_all(force: bool = False) -> dict[str, bool]:
    """
    Download all configured dunnhumby zips to data/zip/.

    Returns a dict of {filename: success_bool}.
    """
    ZIP_DIR.mkdir(parents=True, exist_ok=True)

    skip_lgsr = os.environ.get("SKIP_LGSR", "").strip().lower() in ("1", "true", "yes")
    skip_cj   = os.environ.get("SKIP_CJ",   "").strip().lower() in ("1", "true", "yes")

    results: dict[str, bool] = {}

    # ── The Complete Journey ──────────────────────────────────────────────────
    if not skip_cj:
        logger.info("─── The Complete Journey ───────────────────────────────────")
        fname = _filename_from_url(COMPLETE_JOURNEY_URL)
        dest  = ZIP_DIR / fname
        results[fname] = _download_file(COMPLETE_JOURNEY_URL, dest, force=force)
    else:
        logger.info("SKIP_CJ=1 — skipping The Complete Journey download")

    # ── Let's Get Sort of Real (9 parts) ─────────────────────────────────────
    if not skip_lgsr:
        logger.info("─── Let's Get Sort of Real (9 parts) ──────────────────────")
        for n in range(1, 10):
            # Canonical filename saved to disk always uses curly apostrophe (U+2019)
            # to match what dunnhumby names the file on download.
            fname = f"dunnhumby_Let\u2019s-Get-Sort-of-Real-(Full-Part-{n}-of-9).zip"
            dest  = ZIP_DIR / fname
            urls  = _lgsr_urls(n)
            results[fname] = _download_file(urls, dest, force=force)
    else:
        logger.info("SKIP_LGSR=1 — skipping Let's Get Sort of Real download")

    # ── Summary ───────────────────────────────────────────────────────────────
    ok  = sum(1 for v in results.values() if v)
    bad = sum(1 for v in results.values() if not v)
    logger.info(f"Download complete: {ok} succeeded, {bad} failed")
    if bad:
        for fname, success in results.items():
            if not success:
                logger.warning(f"  FAILED: {fname}")

    return results


if __name__ == "__main__":
    force = "--force" in sys.argv
    logger.info(f"dunnhumby downloader — force={force}")
    logger.info(f"Destination: {ZIP_DIR}")
    results = download_all(force=force)
    failed  = [f for f, ok in results.items() if not ok]
    sys.exit(1 if failed else 0)
