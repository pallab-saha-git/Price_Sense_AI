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
This creates `data/synthetic/` CSVs and populates `data/pricesense.db` (SQLite).  
Safe to re-run — it detects an already-seeded database.

### 7. Start the app
```bash
python app.py
```

Open **http://localhost:8050** in your browser.  
You will be redirected to **`/login`**. Log in with the `ADMIN_USERNAME` / `ADMIN_PASSWORD` you set in `.env`.

---

## Quick Start (Docker)

```bash
docker-compose up --build
```

Open **http://localhost:8050**. The database is seeded automatically.

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
│   └── synthetic/              # Auto-generated CSV files
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

15 SKUs — 9 Nut varieties + 6 Beverage varieties  
25 stores across 5 regions  
104 weeks of synthetic weekly sales (2024 – 2026)  
60 historical promotions with realistic seasonality (Diwali, Christmas, summer)

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
