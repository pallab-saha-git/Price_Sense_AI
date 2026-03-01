"""
config/settings.py
──────────────────
Central settings module. Reads from .env file.
SQLite for MVP — change DATABASE_URL to PostgreSQL for production.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ── Database ──────────────────────────────────────────────────────────────────
# Stage 1 MVP: SQLite (zero installation required — just a file on disk)
# Stage 2+:    postgresql://user:password@host:5432/pricesense
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'pricesense.db'}",
)

# ── App ───────────────────────────────────────────────────────────────────────
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8050"))

# ── Flask session secret ──────────────────────────────────────────────────────
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-please")

# ── Admin bootstrap (first-run seed account) ──────────────────────────────────
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

# ── Registration control ───────────────────────────────────────────────────────
REGISTRATION_DISABLED: bool = os.getenv("REGISTRATION_DISABLED", "false").lower() == "true"

# ── OpenRouter (AI-powered NL insights) ───────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPEN_ROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
# Default: Meta Llama 3.3 70B — a high-quality FREE model on OpenRouter.
# Other free options: google/gemma-3-27b-it:free  |  openai/gpt-oss-120b:free
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

# Use AI insights if API key is set, else fall back to templates
USE_AI_INSIGHTS: bool = bool(OPENROUTER_API_KEY)

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
PROCESSED_DIR = DATA_DIR / "processed"

# Create directories if they don't exist
for _d in [DATA_DIR, RAW_DIR, SYNTHETIC_DIR, PROCESSED_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── ML model parameters ───────────────────────────────────────────────────────
# Constrain elasticity to plausible retail range
ELASTICITY_MIN: float = -4.0
ELASTICITY_MAX: float = -0.3   # items less elastic than -0.3 are effectively inelastic

# Promotional response multiplier.
# Academic research (Blattberg, Briesch & Fox 1995) shows that promotional
# (temporary) price elasticity is 2–3× the regular (permanent) price
# elasticity due to urgency, display, and reference-price anchoring.
PROMO_RESPONSE_MULTIPLIER: float = 2.0

# Category-level default elasticities — used when item-level OLS estimation
# is unreliable (low R², high p-value, or clamped due to no price variation).
# Values based on typical US grocery benchmarks (Hoch et al. 1995).
CATEGORY_ELASTICITY_DEFAULTS: dict = {
    "Grocery":         -1.5,
    "Beverages":       -2.2,
    "Produce":         -1.8,
    "Meat":            -1.3,
    "Meat-Pckgd":      -1.3,
    "Drug Gm":         -1.0,
    "Deli":            -1.4,
    "Nuts":            -2.0,
    "Pastry":          -1.6,
    "Salad Bar":       -1.5,
    "Kiosk-Gas":       -0.8,
    "Misc Sales Tran": -0.8,
}
DEFAULT_CATEGORY_ELASTICITY: float = -1.5

# Risk thresholds
RISK_LOW_THRESHOLD: float = 0.3
RISK_HIGH_THRESHOLD: float = 0.6

# Scenario discount levels to compare
SCENARIO_DISCOUNTS: list = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

# ── Retail calendar events (hardcoded NRF events) ─────────────────────────────
RETAIL_EVENTS = {
    "2026-11-27": {"event": "Black Friday",     "intensity": 5, "categories": ["all"]},
    "2026-11-30": {"event": "Cyber Monday",     "intensity": 4, "categories": ["all"]},
    "2026-10-20": {"event": "Diwali",           "intensity": 5, "categories": ["nuts", "sweets", "gifts"]},
    "2026-12-25": {"event": "Christmas",        "intensity": 5, "categories": ["all"]},
    "2026-02-14": {"event": "Valentines Day",   "intensity": 3, "categories": ["premium", "gifts"]},
    "2026-05-10": {"event": "Mothers Day",      "intensity": 3, "categories": ["premium", "gifts"]},
    "2026-09-07": {"event": "Back to School",   "intensity": 3, "categories": ["snacks", "beverages"]},
    "2026-11-26": {"event": "Thanksgiving",     "intensity": 4, "categories": ["all"]},
    "2026-07-04": {"event": "Independence Day", "intensity": 3, "categories": ["beverages", "snacks"]},
    "2026-01-01": {"event": "New Year",         "intensity": 3, "categories": ["all"]},
    "2026-01-25": {"event": "Lunar New Year",   "intensity": 4, "categories": ["nuts", "gifts"]},
    "2026-03-23": {"event": "Eid al-Fitr",      "intensity": 4, "categories": ["nuts", "gifts"]},
    "2025-11-01": {"event": "Diwali",           "intensity": 5, "categories": ["nuts", "sweets", "gifts"]},
    "2025-11-28": {"event": "Black Friday",     "intensity": 5, "categories": ["all"]},
    "2025-12-25": {"event": "Christmas",        "intensity": 5, "categories": ["all"]},
    "2025-02-14": {"event": "Valentines Day",   "intensity": 3, "categories": ["premium", "gifts"]},
    "2025-12-01": {"event": "Cyber Monday",     "intensity": 4, "categories": ["all"]},
    "2024-11-01": {"event": "Diwali",           "intensity": 5, "categories": ["nuts", "sweets", "gifts"]},
    "2024-11-29": {"event": "Black Friday",     "intensity": 5, "categories": ["all"]},
    "2024-12-25": {"event": "Christmas",        "intensity": 5, "categories": ["all"]},
}
