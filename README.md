# Price Sense AI

> **AI-powered promotion intelligence for mid-market retailers.**  
> Quantify price elasticity, forecast demand, surface cannibalization risk, and generate AI insights — all in a self-contained Python + Dash web app.

---

## Quick Start (local, no Docker)

### 1. Prerequisites
- Python 3.11+  
- Windows / macOS / Linux

### 2. Clone / open the project folder
```
cd "C:\Users\OneLIFE\Desktop\Trinamix"
```

### 3. Create a virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1     # Windows PowerShell
# or
source venv/bin/activate         # macOS / Linux
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

> **Prophet on Windows** — if `pip install prophet` fails, install the Visual C++ Build Tools first or use the Docker path instead.

### 5. Configure environment variables
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env     # Linux / macOS
copy .env.example .env   # Windows
```

Minimum required — generate a secret key and set admin credentials:
```powershell
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

Then edit `.env`:
```
SECRET_KEY=<paste-generated-key-here>
ADMIN_USERNAME=your_admin_name
ADMIN_PASSWORD=your_strong_password
OPEN_ROUTER_API_KEY=sk-or-...   # optional — enables AI insights
```

### 6. Generate synthetic data & seed the database
```bash
python data/seed_data.py
```
If `data/synthetic/` CSVs do not exist yet, `seed_data.py` runs `synthetic_generator.py` automatically before seeding.  
Safe to re-run — it detects an already-seeded database.

> **Note:** `data/synthetic/` is git-ignored. To regenerate CSVs independently: `python data/synthetic_generator.py`

### 7. Start the app
```bash
python app.py
```

Open **http://localhost:8050** in your browser.  
You will be redirected to **`/login`**. Log in with the `ADMIN_USERNAME` / `ADMIN_PASSWORD` you set in `.env`.

---

## Quick Start (Docker)

```bash
docker compose up --build
```

Open **http://localhost:8050**. The database is seeded automatically.  
Synthetic demo CSVs are generated during the Docker build step — no manual data download needed.

---

## Project Structure

```
Trinamix/
├── app.py                      # Dash entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                        # Secrets (not committed)
├── .env.example                # Template
│
├── config/
│   └── settings.py             # Central config — reads .env
│
├── data/
│   ├── database.py             # SQLAlchemy ORM (8 tables)
│   ├── synthetic_generator.py  # Generates realistic demo data
│   ├── seed_data.py            # Loads CSVs → SQLite
│   └── synthetic/              # Auto-generated CSV files (git-ignored; generated at build/startup)
│
├── models/
│   ├── elasticity.py           # Log-log OLS price elasticity
│   ├── cannibalization.py      # Cross-elasticity matrix
│   ├── demand_forecast.py      # Prophet + moving-average fallback
│   ├── profit_calculator.py    # Full P&L model
│   └── risk_scorer.py          # 6-factor composite risk score
│
├── services/
│   ├── promo_analyzer.py       # Orchestrates all 5 models
│   ├── insight_generator.py    # Template + OpenRouter AI insights
│   └── scenario_engine.py      # Multi-discount scenario comparison
│
├── components/                 # Reusable Plotly / Dash UI blocks
│   ├── promo_input_form.py
│   ├── recommendation_card.py
│   ├── elasticity_chart.py
│   ├── cannibalization_heatmap.py
│   ├── risk_gauge.py
│   ├── insight_panel.py
│   └── scenario_table.py
│
├── pages/                      # Dash multi-page layouts
│   ├── home.py                 # Dashboard overview
│   ├── analyze.py              # Promotion analyzer
│   ├── compare.py              # Scenario comparison
│   └── catalog.py              # Product catalog
│
├── auth/
│   ├── users.py                # User CRUD + Werkzeug PBKDF2-SHA256 hashing
│   ├── login_page.py           # /login and /register Dash pages
│   └── auth_callbacks.py       # Flask session login/register callbacks
│
├── callbacks/
│   ├── analyze_callbacks.py
│   ├── scenario_callbacks.py
│   └── catalog_callbacks.py
│
├── gunicorn.conf.py            # Production WSGI config
├── Procfile                    # Heroku / Render deployment
├── logging.yaml                # Structured logging config
├── .gitignore
│
└── tests/
    └── test_models.py          # pytest unit tests
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | KPI overview, trend charts |
| Analyze | `/analyze` | Full promotion analysis — select SKU → discount → get Go/No-Go |
| Compare | `/compare` | Side-by-side multi-discount scenario table |
| Catalog | `/catalog` | Browse all 15 SKUs + promotion history |

---

## Authentication

### First Login
Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`. On first startup, the app auto-creates that admin account.  
Navigate to **http://localhost:8050** — you will be redirected to `/login`.

### Creating Additional Users
Navigate to **`/register`** to create a new account (username, email, password).  
To disable public registration (private deployment), set:
```
REGISTRATION_DISABLED=true
```

### Session Security
- Passwords are hashed with **PBKDF2-SHA256** (Werkzeug — built into Flask/Dash).
- Sessions are signed with `SECRET_KEY` — **never use the default in production**.
- Sessions expire after 8 hours of inactivity.
- Logout at `/logout`.

### Generating a SECRET_KEY
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## AI Insights

When `OPEN_ROUTER_API_KEY` is set in `.env`, the app calls **OpenRouter** to generate narrative recommendations.  
Without the key, it falls back to deterministic templates.

Default free model: `meta-llama/llama-3.3-70b-instruct:free` (131K context, $0/M tokens)  
Endpoint: `https://openrouter.ai/api/v1`

Other free OpenRouter models you may use:
| Model | Context | Notes |
|---|---|---|
| `meta-llama/llama-3.3-70b-instruct:free` | 131K | **Default — recommended** |
| `google/gemma-3-27b-it:free` | 131K | Multimodal |
| `openai/gpt-oss-120b:free` | 128K | OpenAI open-weight |
| `qwen/qwen3-coder:free` | 1M | Code-focused |

Change the model by setting `OPENROUTER_MODEL=<model-id>` in `.env`.

---

## Data Model

### Synthetic Demo Data (default)

The `data/synthetic/` CSVs are **not committed to git** — they are generated automatically.

| Where | How |
|---|---|
| **Docker** | `RUN python data/synthetic_generator.py` bakes the CSVs into the image at build time. On first start with a volume mount (`./data:/app/data`), the CMD startup guard regenerates them into the mounted directory if they are absent. |
| **Local (non-Docker)** | `python data/seed_data.py` auto-generates the CSVs before seeding, or run the generator directly: `python data/synthetic_generator.py` |

**Contents:**
- 15 SKUs — 9 Nut varieties + 6 Beverage varieties  
- 25 stores across 5 regions  
- 104 weeks of synthetic weekly sales (2024 – 2026)  
- 60 historical promotions with realistic seasonality (Diwali, Christmas, summer)

To regenerate with a different random seed, edit `SEED` in [data/synthetic_generator.py](data/synthetic_generator.py) and re-run it.

---

## Real Dataset — dunnhumby

The app can run on real retail transaction data from **dunnhumby**.

> **Why isn't there an automated Docker download step?**  
> dunnhumby Source Files require a free account registration on their website.  
> Automated download scripts cannot bypass that registration wall.  
> Place the downloaded zip(s) in `data/zip/` **before** starting Docker —  
> the `docker-compose.yml` already mounts `./data` into the container, so  
> no extra volume configuration is needed.

### Option A: Download from dunnhumby Source Files (recommended)

1. Visit **https://www.dunnhumby.com/source-files/**
2. Register (free) and download either:
   - **"The Complete Journey"** — 128 MB zip, ~2,500 households, best for local dev
   - **"Let's Get Sort of Real"** (Full) — 9 × 480 MB zips (~4.3 GB total), full retail chain transaction history 2006–2011

3. Place the downloaded zip(s) in your local `data/zip/` folder:
   ```
   Trinamix/
   └── data/
       └── zip/
           ├── dunnhumby_The-Complete-Journey.zip          ← Complete Journey
           ├── dunnhumby_Let's-Get-Sort-of-Real-(Full-Part-1-of-9).zip
           └── ...
           └── dunnhumby_Let's-Get-Sort-of-Real-(Full-Part-9-of-9).zip
   ```

4. Start Docker — the loader runs automatically on first start:
   ```bash
   # The ./data/ directory is mounted into the container,
   # so zips in data/zip/ are immediately visible to Docker.
   docker compose up --build
   ```
   The container detects the zips at startup and runs `python data/load_dunnhumby.py`
   automatically (one-time, ~2–5 min for Complete Journey). Subsequent restarts skip it.

   Or run the loader manually (outside Docker):
   ```bash
   python data/load_dunnhumby.py
   ```
   To force a reload (clears existing dunnhumby data and re-ingests):
   ```bash
   python data/load_dunnhumby.py --force
   ```

### Option B: Kaggle Hub (programmatic download)

```bash
pip install kagglehub
```

```python
import kagglehub
from kagglehub import KaggleDatasetAdapter

hf_dataset = kagglehub.load_dataset(
    KaggleDatasetAdapter.HUGGING_FACE,
    "frtgnn/dunnhumby-the-complete-journey",
    "",   # file_path — leave empty to load all files
)
print("Hugging Face Dataset:", hf_dataset)
```

### Dataset Priority

When `data/zip/` contains zips, the Docker entrypoint follows this priority:

| Priority | Dataset | Size | Rows (approx) |
|----------|---------|------|---------------|
| 1 | The Complete Journey | 128 MB zip | ~500K weekly aggregates |
| 2 | Let's Get Sort of Real | 9 × 480 MB | Sampled ~270K weekly aggregates |
| fallback | Synthetic data | ~3 MB | ~40K rows (auto-generated) |

### What changes with real data

- **Elasticity** computed from real observed price variation across 2+ years
- **Stores** reflect actual retail footprint (50+ stores with real regional patterns)
- **Cannibalization** signals from actual basket co-purchase data
- **Seasonality** reflects real promotional calendar and holiday lifts
- **Calendar events** populated from [`holidays`](https://pypi.org/project/holidays/) package (US/UK public holidays) + hardcoded NRF retail calendar (Black Friday, Diwali, Cyber Monday, etc.)
- **Competitor events** generated synthetically per product category (~5 events/category/year) to calibrate competitive price pressure
- **Gender distribution** (`gender_female_pct`) derived from `hh_demographic.csv` household composition data (Complete Journey) or UK grocery research benchmarks (LGSR); stored per customer segment
- **Cost & margin** assigned synthetically: `cost_price = regular_price × 0.58` (CJ) or `× 0.60` (LGSR). The `products` table always has `cost_price` and `margin_pct` for full P&L analysis
- **Weather index** populated from [Open-Meteo API](https://open-meteo.com/) (free, no key needed) for representative coordinates per region. Falls back to hardcoded seasonal averages if the API is unavailable
- Recommendation card shows real product names, departments, and brand tiers

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|--------|
| `SECRET_KEY` | **Yes** (prod) | insecure default | Flask session signing key |
| `ADMIN_USERNAME` | Recommended | empty | Bootstrap admin account username |
| `ADMIN_PASSWORD` | Recommended | empty | Bootstrap admin account password |
| `REGISTRATION_DISABLED` | No | `false` | Set to `true` to disable `/register` |
| `OPEN_ROUTER_API_KEY` | No | empty | OpenRouter API key for AI insights |
| `OPENROUTER_MODEL` | No | `meta-llama/llama-3.3-70b-instruct:free` | AI model to use |
| `DATABASE_URL` | No | SQLite | SQLAlchemy connection URL |
| `HOST` | No | `0.0.0.0` | Server bind host |
| `PORT` | No | `8050` | Server port |
| `DEBUG` | No | `false` | Enable Dash debug mode |

---

## Production Deployment

### Gunicorn (Linux / Docker)
```bash
pip install gunicorn
gunicorn app:server -c gunicorn.conf.py
```

### Heroku / Render
The included `Procfile` is ready:
```
web: gunicorn app:server -c gunicorn.conf.py
```
Set all environment variables in your platform dashboard.

### Docker
```bash
docker-compose up --build
```
The `docker-compose.yml` uses the `Procfile` command and maps port 8050.
