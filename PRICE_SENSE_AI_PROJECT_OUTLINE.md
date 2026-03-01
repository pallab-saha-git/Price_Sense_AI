# Price Sense AI — Complete Project Outline & Build Plan

> **"Should I run this promotion?"** — The one question every mid-market retailer needs answered with data, not gut feel.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Market Context](#2-problem-statement--market-context)
3. [Product Vision & Scope](#3-product-vision--scope)
4. [Data Strategy — What You Need & Where to Get It](#4-data-strategy--what-you-need--where-to-get-it)
5. [Technology Decisions — APIs vs Packages, Cloud vs Local](#5-technology-decisions--apis-vs-packages-cloud-vs-local)
6. [System Architecture](#6-system-architecture)
7. [MVP vs Production — What Changes](#7-mvp-vs-production--what-changes)
8. [Component Breakdown & Package Registry](#8-component-breakdown--package-registry)
9. [ML/AI Model Pipeline — The Analytical Engine](#9-mlai-model-pipeline--the-analytical-engine)
10. [Enterprise Architecture Considerations](#10-enterprise-architecture-considerations)
11. [Work Plan & Sprint Schedule](#11-work-plan--sprint-schedule)
12. [Demo Script — Reference Customer Walkthrough](#12-demo-script--reference-customer-walkthrough)
13. [Risk Register & Mitigations](#13-risk-register--mitigations)
14. [Appendix](#14-appendix)

---

## 1. Executive Summary

Price Sense AI is an AI-powered promotion intelligence platform that transforms how mid-market retailers ($50M–$500M revenue) make promotion decisions. Instead of relying on gut feel, merchants get a data-driven answer to: *"Should I run 25% off on Salted Pistachios 16oz next week?"* — complete with projected lift, cannibalization impact, incremental profit estimate, and risk score.

**This document covers everything needed to go from an empty folder to a functioning demo-ready prototype, and then to a scalable production SaaS product.**

### Key Decisions (TL;DR)

| Question | Answer |
|----------|--------|
| Frontend framework? | **Dash (by Plotly)** — pure Python, no React/JS needed, production-ready, same code MVP→Prod |
| Do I need a Kaggle dataset? | **Yes, for the demo.** Use dunnhumby "The Complete Journey" — it is the only public dataset with real promo flags + cannibalization signals |
| Do I need Azure/OpenAI APIs? | **MVP: No.** Open-source packages cover everything. **Production v1: OpenAI API only** ($5–$15/mo at mid-market scale) |
| Do I need SQL installed locally? | **No.** SQLite is built into Python — zero installation, it's just a file on your disk |
| How many sprints for MVP? | **4–5 weeks** (solo developer) |
| How big is the MVP→Production gap? | **Small and gradual.** Same codebase throughout. For demo use: `python app.py` or `docker-compose up` — no live URL needed. If you ever want production later, only 2 things change: swap SQLite→PostgreSQL (one line) and add a login page |

---

## 2. Problem Statement & Market Context

### The Retailer's Promotion Problem

Mid-market retailers run **200–500+ promotions per year** across categories. Today's decision process:

```
Merchant thinks → "Pistachios sold well last time at 25% off" 
                → Runs same promo again
                → Sees sales spike during promo
                → Declares victory
                → Never measures:
                    ✗ How much was pulled forward from next week?
                    ✗ How much cannibalized Almonds sales?
                    ✗ Was the margin erosion worth it?
                    ✗ Would 20% off have worked just as well?
```

### Why This Matters (Business Case)

| Metric | Typical Mid-Market Retailer |
|--------|----------------------------|
| Annual Revenue | $50M–$500M |
| Promo Spend (% of revenue) | 15–25% |
| Promotions that are actually profitable | ~30–40% |
| Money left on the table annually | $2M–$15M |

**Price Sense AI target outcome:** Improve promotion ROI by 15–30%, which translates to $750K–$4.5M annual value for a $100M retailer.

### Target Personas

| Persona | Role | Pain Point |
|---------|------|------------|
| **Category Manager** | Decides which products to promote | "I don't know if 25% off is better than 20% off" |
| **Merchandising VP** | Approves promo calendar | "I can't see the portfolio-level impact of all planned promos" |
| **Finance/Pricing Analyst** | Measures promo ROI post-hoc | "Our post-promo analysis takes 2 weeks and is always retrospective" |

---

## 3. Product Vision & Scope

### Core User Flow (What the Demo Must Show)

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: INPUT                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Product:    [Salted Pistachios 16oz        ▼]        │   │
│  │ Discount:   [25% off                       ▼]        │   │
│  │ Duration:   [1 week   ] Start: [2026-03-08]          │   │
│  │ Channel:    [☑ In-store  ☑ Online]                   │   │
│  │                                                      │   │
│  │              [ Analyze Promotion → ]                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  STEP 2: RECOMMENDATION                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ✅ RECOMMENDED — with adjustments                    │   │
│  │                                                      │   │
│  │  Projected Volume Lift:    +42% (+1,260 units)       │   │
│  │  Cannibalization Impact:   -18% from Almonds 16oz    │   │
│  │  Net Incremental Revenue:  +$3,840                   │   │
│  │  Incremental Profit:       +$1,120                   │   │
│  │  Promo ROI:                2.3x                      │   │
│  │  Risk Score:               Medium (0.6/1.0)          │   │
│  │                                                      │   │
│  │  💡 Insight: "20% off would capture 85% of the       │   │
│  │   volume lift at 40% less margin cost. Consider      │   │
│  │   testing 20% off first."                            │   │
│  │                                                      │   │
│  │  📊 [View Detailed Analysis] [Compare Scenarios]     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  STEP 3: DEEP DIVE (expandable)                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Demand curve & elasticity chart                   │   │
│  │  • Cannibalization heatmap across product family     │   │
│  │  • Scenario comparison table (15% / 20% / 25% / 30%)│   │
│  │  • Historical promo performance for this SKU         │   │
│  │  • Confidence intervals & assumptions                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Horizontal Design Principle

The product MUST NOT be hardcoded for nuts. The data model and UI should support:

| Category | Example Catalog |
|----------|----------------|
| Specialty Nuts | Almonds, Pistachios, Mixed Nuts (multiple sizes) |
| Beverages | Craft sodas, sparkling water, juices (multiple sizes/packs) |
| Grocery/CPG | Cereals, snacks, dairy (multiple brands/sizes) |

This is achieved by abstracting the product hierarchy:
```
Category → Subcategory → Brand → Product → SKU (size/variant)
```

---

## 4. Data Strategy — What You Need & Where to Get It

### 4.1 What Data Does Price Sense AI Need?

**Short answer: Include everything from day one in the synthetic data.** It costs nothing extra to add it to a generated dataset, and it makes the model meaningfully more accurate — especially for seasonal categories like nuts (gifting spikes at Diwali, Christmas, New Year), beverages (summer peak), and specialty foods (holiday gift packs). A promo recommendation that ignores that Pistachios spike +180% in November will badly misestimate lift and risk.

| Data Type | Description | MVP? | Why All Should Be Included |
|-----------|-------------|:----:|---|
| **Transaction / POS Data** | Weekly sales by SKU: units, revenue, price paid | ✅ Synthetic | Core foundation — everything is built on this |
| **Promotion History** | Past promos: product, discount %, start/end, type (TPR, BOGO, display) | ✅ Synthetic | Required to estimate elasticity and historical lift |
| **Product Catalog** | SKU hierarchy, sizes, categories, cost/margin | ✅ Synthetic | Required for profit calculation and cannibalization grouping |
| **Price & Cost Data** | Regular price, cost price, supplier deal funding | ✅ Synthetic | Required for P&L and ROI calculation |
| **Seasonality & Calendar** | Holidays, retail events, weather signals, day-of-week patterns | ✅ **Include in MVP** | **Critical.** Without this, the demand baseline is wrong for seasonal SKUs. A pistachio promo in December is nothing like the same promo in July. Dry fruits, gift packs, specialty foods are among the most seasonal categories in retail. Free Python package (`holidays`) + free weather API (Open-Meteo). |
| **Store & Channel Data** | Store count, region, geography, online vs offline split | ✅ **Include in MVP** | Makes the model horizontal across multi-store retailers. Also needed to demonstrate "which 10 stores should run this promo?" — a question every Category Manager asks. Entirely synthetic for demo. |
| **Customer Segments** | Basket composition, loyalty tier, price sensitivity profile | ✅ **Include in MVP** | Enables "this promo attracts deal-seekers who don’t return" vs "this attracts loyal buyers who trade up." dunnhumby already provides household-level data. Synthetic buckets sufficient for demo. |
| **Competitor Signals** | Competitor promo activity, price index | ✅ **Include in MVP (synthetic)** | Explains why a promo performed better or worse than predicted. Synthetic competitor events (e.g., "Competitor ran BOGO that week") add realism to demos and explain variance in the model. |

> **Summary:** Including all 8 dimensions in the synthetic dataset costs zero extra money and zero extra infra. It only costs a few more lines in the synthetic generator script. The reward is a model that can explain seasonality, geography, channel, and competitive context — which is exactly what moves a demo from "interesting" to "I need this."

### 4.2 Datasets — Where to Get Them

#### Honest Coverage Map — What dunnhumby Actually Contains vs What You Build

This is important to be precise about. The document previously said dunnhumby "has" everything. Here is the exact truth:

| Dimension | What dunnhumby provides | What you build/derive on top |
|-----------|------------------------|-----------------------------|
| **Transactions** | ✅ `transaction_data.csv` — household, basket, product, day, quantity, price paid | Nothing extra needed |
| **Promotion flags** | ✅ `causal_data.csv` — weekly per-product per-store flags: `display` (endcap), `feature` (flyer), `temp_price_reduction` | Nothing extra needed |
| **Basket composition** | ✅ Multiple rows per `basket_id` — shows what else was bought in same trip as Pistachios | Nothing extra needed. This is where cannibalization signals come from. |
| **Customer segments** | ✅ `hh_demographic.csv` — age group, income band, family size, homeowner status | Map to your 3 segment buckets (price-sensitive / loyalist / occasional) |
| **Product hierarchy** | ✅ `product.csv` — department, commodity, sub-commodity, brand, curr_size_of_product | Does NOT have cost price — you add a synthetic margin % per category |
| **Campaign info** | ✅ `campaign_table.csv` + `campaign_desc.csv` — which campaign type (A/B/C) each household received | Maps to promo mechanism type |
| **Coupon redemptions** | ✅ `coupon_redempt.csv` — coupon usage per household per product | Maps to digital promo / loyalty offer signal |
| **SEASONALITY LABELS** | ❌ Not present. The data spans 2 years so seasonal patterns are embedded in the numbers, but there are no holiday or event labels. | You add: `holidays` Python package + hardcoded retail calendar. The seasonal patterns exist in dunnhumby data — you just label them. |
| **Weather** | ❌ Not present. | Open-Meteo API (free, no key). |
| **Store geography** | ⚠️ Partial. Store IDs exist in `transaction_data.csv` but no location names, regions, or coordinates. | You assign synthetic regions (NE/SE/MW/W) to store IDs. |
| **Competitor events** | ❌ Not present. | 30 lines of Python to generate synthetic competitor promo events. |
| **Cost / margin** | ❌ Not present. Only `sales_value` (what was paid). | You assign a synthetic `cost_price` using typical retail margin % per category. |

**Bottom line:**
- dunnhumby gives you the **statistical backbone**: real purchase patterns, real promo response distributions, real cross-product basket signals, real household heterogeneity.
- Everything else (labels, geography, competitors, cost) you **add on top** with free Python packages and synthetic generation.
- Together, this is higher quality than any fully-raw public dataset alone.

---

#### Why dunnhumby "The Complete Journey" and NOT Walmart Sales / Favorita?

This is an important choice — here is exactly why:

| Dataset | Has SKU-level promo flags? | Has cannibalization signals? | Has basket composition? | Has cost/margin? | Row count | Verdict |
|---------|:---:|:---:|:---:|:---:|:---:|---|
| **dunnhumby Complete Journey** | ✅ Yes, per-transaction | ✅ Yes — same basket shows substitute behavior | ✅ Yes | ✅ Yes (approximated) | ~7M rows | **USE THIS** |
| Walmart Sales (Kaggle) | ⚠️ Only markdown flags (not item-level) | ❌ No — aggregated store-week level, no SKU cross-effects visible | ❌ No | ❌ No | 400K rows | Too aggregated for elasticity or cannibalization |
| Corporación Favorita | ✅ Promo flag per item per day | ⚠️ Possible but 125M rows is overkill for MVP | ❌ No | ❌ No | 125M rows | Too large and complex for a solo MVP build |
| Instacart Market Basket | ❌ No pricing data at all | ⚠️ Association rules only | ✅ Yes | ❌ No | 3M orders | No price data = can't build elasticity models |

**The critical difference:** dunnhumby is the only dataset that gives you all three things at once — price paid per transaction, promo indicator, and basket-level cross-product visibility. This is what lets you demonstrate cannibalization with real data patterns rather than made-up numbers.

#### A. Free Public Datasets — Every Source Listed Here Is 100% Free

| Data Type | Dataset / Source | Access | What It Gives You | Free? |
|-----------|----------------|--------|-------------------|:-----:|
| **Transactions + Promos + Baskets + Segments** | dunnhumby "The Complete Journey" | Two paths — see download guide below | 2yr transactions, promo flags, household demographics, basket composition | ✅ Free |
| **Transactions + Promos (alternative)** | Corporación Favorita | Kaggle — see download guide below | 125M rows, daily SKU+store, promo flags | ✅ Free |
| **Beverage sales (vertical demo)** | Iowa Liquor Sales | data.iowa.gov — see download guide below | Retail alcohol sales with volume + pricing | ✅ Free |
| **National & regional holidays** | `holidays` Python package | `pip install holidays` | Public holidays for 100+ countries, any year range, built into Python | ✅ Free (package) |
| **Historical weather data** | Open-Meteo API | open-meteo.com — no sign-up, no key | Temperature, precipitation, any location, 80yr history | ✅ Free, no key |
| **Consumer interest / search trends** | Google Trends via `pytrends` | `pip install pytrends` | Search volume for product terms by week/month — proxy for demand seasonality | ✅ Free (unofficial) |
| **Retail calendar events** | NRF Key Dates (hardcode) | NRF.com (reference only) | Black Friday, Back-to-School, Super Bowl, Valentine’s, Diwali, Eid, Christmas | ✅ Free (hardcode) |
| **Product catalog reference** | Open Food Facts | world.openfoodfacts.org/data | 3M+ food products: name, category, brand, size | ✅ Free, open license |
| **Supplementary e-commerce** | UCI Online Retail | archive.ics.uci.edu/dataset/352 | UK e-commerce transactions with pricing | ✅ Free |

---

### 4.2A Step-by-Step Download Guide — Every Dataset

#### 1. dunnhumby "The Complete Journey" — PRIMARY DATASET

This is the most important download. Two paths — choose whichever is faster:

**Path A: Direct from dunnhumby.com (official)**
```
Step 1: Go to https://www.dunnhumby.com/source-files/
Step 2: Scroll to "The Complete Journey" section
Step 3: Click "Register to access"
Step 4: Fill in name + business email (any real email works, no payment)
Step 5: You receive a download link by email within minutes
Step 6: Download the ZIP file (~150MB)
Step 7: Extract to your project: data/raw/dunnhumby/
```

**Path B: Kaggle mirror (faster, no email required if you have Kaggle account)**
```
Step 1: Go to https://www.kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey
Step 2: Click "Download" (top right)
Step 3: Sign in to Kaggle (free account)
Step 4: Download ZIP (~150MB)
Step 5: Extract to: data/raw/dunnhumby/

OR using Kaggle CLI (fastest if you have it set up):
  pip install kaggle
  kaggle datasets download frtgnn/dunnhumby-the-complete-journey
  unzip dunnhumby-the-complete-journey.zip -d data/raw/dunnhumby/
```

**Files you will have after extraction:**
```
data/raw/dunnhumby/
├── transaction_data.csv       # 2,595 households × 2 years × all purchases
├── product.csv               # Product hierarchy: department → commodity → brand → size
├── causal_data.csv           # ★ PROMO FLAGS: display/feature/temp_price_reduction per product per week
├── hh_demographic.csv        # ★ SEGMENTS: age, income, family size per household
├── campaign_table.csv        # Which campaign type each household received
├── campaign_desc.csv         # Campaign type (A=major, B=focused, C=targeted) + date range
├── coupon.csv                # Which products are in each campaign coupon
└── coupon_redempt.csv        # When a coupon was actually redeemed by a household

Key columns to know:
  transaction_data.csv:
    household_key  → customer ID
    basket_id      → single shopping trip (multiple rows = same trip = cannibalization signal)
    day            → day number 1-711 (spanning ~2 years)
    product_id     → joins to product.csv
    quantity       → units purchased
    sales_value    → actual price paid (reflects any discount)
    store_id       → which store
    coupon_disc    → coupon discount amount applied
    retail_disc    → temporary price reduction amount

  causal_data.csv:
    product_id, store_id, week_no
    display        → 0/1/0.5: was product on in-store endcap display
    feature        → 0/1/0.5: was product in weekly flyer/feature
    mailer         → 0/1: was product in direct mail campaign
```

**What you do with it:**
```python
import pandas as pd

# Load the key files
txn = pd.read_csv('data/raw/dunnhumby/transaction_data.csv')
products = pd.read_csv('data/raw/dunnhumby/product.csv')
causal = pd.read_csv('data/raw/dunnhumby/causal_data.csv')     # promo flags
demographics = pd.read_csv('data/raw/dunnhumby/hh_demographic.csv')  # segments

# Day 1 → 2 years (711 days)
# Convert day number to actual date
import datetime
START_DATE = datetime.date(2017, 1, 1)  # approximate
txn['date'] = txn['day'].apply(lambda d: START_DATE + datetime.timedelta(days=d-1))
txn['week'] = txn['date'].dt.isocalendar().week
txn['year'] = txn['date'].dt.year

# Extract snack/nut-adjacent categories to calibrate your synthetic data
# dunnhumby uses grocery categories, not "nuts" specifically
# Look for: BAGS/SALTY SNACKS, TRAIL MIX, DRIED FRUIT/NUTS
snacks = products[products['commodity_desc'].str.contains(
    'SNACK|NUT|TRAIL|DRIED FRUIT', case=False, na=False
)]
print(snacks['commodity_desc'].value_counts().head(20))
```

---

#### 2. Corporación Favorita (Kaggle) — SUPPLEMENTARY / ALTERNATIVE

```
Step 1: Go to https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/data
Step 2: Sign in to Kaggle (free)
Step 3: Click "Join Competition" (required to access data, no submission needed)
Step 4: Download individual files (you do NOT need all 125M rows)
        Download only:
          • train.csv.gz (item+store+date+promo+units_sold)
          • items.csv (product catalog)
          • stores.csv (store city/state/type/cluster)
          • holidays_events.csv  ★ MOST USEFUL for you — Ecuador national holidays + events
Step 5: Extract to: data/raw/favorita/

OR Kaggle CLI:
  kaggle competitions download -c favorita-grocery-sales-forecasting \
    -f holidays_events.csv
  kaggle competitions download -c favorita-grocery-sales-forecasting \
    -f stores.csv
```

**What you use from Favorita:**
- `holidays_events.csv` — structured holiday + event flags with type (Holiday/Event/Additional/Bridge/Work Day). Use as a reference template for building your retail calendar.
- `stores.csv` — real store metadata (city, state, type, cluster). Use as a template for your synthetic store table.
- NOT the full 125M row `train.csv` — too large, dunnhumby is better structured for your use case.

---

#### 3. Iowa Liquor Sales — BEVERAGE VERTICAL DEMO DATA

```
Step 1: Go to https://data.iowa.gov/Sales-Distribution/Iowa-Liquor-Sales/m3tr-qhgy
Step 2: Click "Export" (top right)
Step 3: Choose "CSV" format

ORe use the Socrata API to download a manageable subset (free, no key needed):
  URL to get last 5 years, limited to 500K rows:
  https://data.iowa.gov/resource/m3tr-qhgy.csv?$limit=500000&$order=date%20DESC

This can be run directly in Python:
```
```python
import pandas as pd
beverage_df = pd.read_csv(
    "https://data.iowa.gov/resource/m3tr-qhgy.csv"
    "?$limit=200000&$order=date+DESC"
    "&$where=category_name+like+'%25VODKA%25'+OR+category_name+like+'%25RUM%25'"
)
# Then use bottle_volume_ml, state_bottle_cost, state_bottle_retail as price/cost/margin
```

**What you use from it:**
- Seasonal patterns for beverages (summer spikes, holiday spikes in spirits)
- Price-volume relationship across different SKU sizes
- Regional sales distribution across Iowa counties (maps to your store region concept)

---

#### 4. Python Packages — No Download, Just pip install

```bash
# Run this once after activating your virtual environment
pip install holidays pytrends requests

# holidays: provides UK, US, India, all major country holidays
#   import holidays
#   indian_holidays = holidays.India(years=range(2023, 2027))
#   # Automatically includes Diwali, Eid, Holi, Independence Day, etc.

# pytrends: Google Trends — shows search interest over time
#   from pytrends.request import TrendReq
#   pytrends = TrendReq()
#   pytrends.build_payload(["pistachios", "mixed nuts gift"], timeframe='2023-01-01 2025-12-31')
#   interest_df = pytrends.interest_over_time()
#   # Returns weekly relative search volume 0-100 — spike in Nov/Dec = gifting season signal

# requests: used to call Open-Meteo (weather, no API key)
#   Already shown in Section 4.2 code sample above
```

---

#### 5. What You Do NOT Need to Download

| Source | Why not needed |
|--------|---------------|
| US Census TIGER | Only needed if you build real geographic maps. For MVP, synthetic store regions (NE/SE/MW/W) are sufficient. |
| Open Food Facts | Only needed if you want to enrich product names/attributes from a real catalog. For MVP, your 15 synthetic SKUs are hand-crafted. |
| Walmart Sales (Kaggle) | Explicitly not useful — too aggregated, no SKU-level promo flags. |
| Instacart | No pricing data — can’t build elasticity models. |

#### Why Seasonality Data Is Non-Negotiable (Not Optional)

For the categories in your reference customer and horizontal targets, seasonality is the single biggest driver of demand variance — often more than the discount itself:

```
Category              Peak Period               Multiplier Effect
───────────────────────────────────────────────────────────────
 Salted Pistachios     Diwali, Eid, Lunar NY      ×2.5–3.5× baseline volume
 Mixed Nuts Gift Packs  Nov–Dec (Xmas/Hanukkah)   ×3–5× baseline volume
 Premium Almonds        Valentine’s, Mother’s Day  ×1.8–2.2× baseline volume
 Craft Beverages        Summer (Jun–Aug)           ×1.5–2.0× baseline volume
 Hot Beverages / Tea    Winter (Dec–Feb)           ×1.6–2.4× baseline volume

Without seasonality in the model:
  Baseline forecast for Pistachios in Nov = 3,000 units (avg weekly)
  Actual baseline in Nov (gifting season) = 7,500 units

  Model predicts: promo lifts volume from 3,000 → 4,200 (+40%)
  Reality: promo is lifting from an already-elevated 7,500 baseline
  Model massively underestimates risk of stocking out.
  Model also incorrectly credits the promo for natural seasonal demand.
```

**Implementation (all free, all in Python):**
```python
import holidays
import requests  # for Open-Meteo

# US holidays
us_holidays = holidays.US(years=[2024, 2025, 2026])
# Returns: {date: 'Christmas Day', date: 'Thanksgiving', ...}

# Weather for a location (Open-Meteo, no API key)
response = requests.get(
    "https://api.open-meteo.com/v1/forecast",
    params={
        "latitude": 40.71, "longitude": -74.01,  # NYC
        "weekly": "temperature_2m_max,precipitation_sum",
        "start_date": "2024-01-01", "end_date": "2025-12-31"
    }
)
weather_df = pd.DataFrame(response.json()["weekly"])

# Retail calendar (hardcoded NRF events — no API needed)
RETAIL_EVENTS = {
    "2025-11-28": {"event": "Black Friday",     "intensity": 5, "categories": ["all"]},
    "2025-12-01": {"event": "Cyber Monday",      "intensity": 4, "categories": ["all"]},
    "2025-11-01": {"event": "Diwali",            "intensity": 5, "categories": ["nuts", "sweets", "gifts"]},
    "2025-12-25": {"event": "Christmas",         "intensity": 5, "categories": ["all"]},
    "2025-02-14": {"event": "Valentine's Day",   "intensity": 3, "categories": ["premium", "gifts"]},
    "2025-05-11": {"event": "Mother's Day",      "intensity": 3, "categories": ["premium", "gifts"]},
    "2025-09-01": {"event": "Back to School",    "intensity": 3, "categories": ["snacks", "beverages"]},
}
```

#### B. Synthetic Data Generation (Recommended for Demo)

**Why synthetic?** Public datasets won't perfectly match the "specialty nuts retailer" reference customer. You should:

1. Use **dunnhumby** as the statistical backbone (real distributions, real seasonality)
2. Generate a **synthetic overlay** that maps to the nuts/snacks catalog
3. This gives you control over the narrative during the demo

**Synthetic data generator should produce:**
```
- 3 categories × 3 sizes = 9 core SKUs (Almonds, Pistachios, Mixed Nuts × 8oz/16oz/32oz)
- 104 weeks (2 years) of weekly sales data
- 50 historical promotions with varying discount depths (10%, 15%, 20%, 25%, 30%)
- Embedded cross-elasticity signals (pistachios ↔ almonds cannibalization)
- Seasonality (holiday spikes, summer dips)
- 10–25 simulated stores
```

### 4.4 Is This Too Much Data? — Direct Answer

**No.** Here is why each dimension earns its place:

| Dimension | Without It | With It | Cost to Add |
|-----------|-----------|---------|:-----------:|
| **Seasonality** | Model recommends "don’t run 25% off" in November — but actually Nov is the best month because baseline demand is 3× higher and margin dollars are huge even at a discount | Model correctly identifies that November promos for gift packs are more profitable despite same discount depth | 1 Python package (`holidays`) + free API |
| **Store / Channel** | Every store treated identically. Can’t answer "run this in NE stores only?" | Can recommend store-level targeting: "Run in NE + MW, skip SE (already overperforming organically)" | Synthetic data generation only |
| **Customer Segments** | Can’t explain why promo ROI differs across two identical stores | Can explain: "Store A has 60% price-sensitive customers — their promo response is 2× higher than Store B" | Included in dunnhumby; synthetic for others |
| **Competitor Events** | Model can’t explain anomalous weeks. Confuses "competitor ran BOGO" with "our promo was weak" | Model can flag: "Historical lift for this SKU was lower in weeks when Competitor A ran promos — account for this in forecast" | Fully synthetic; 30 lines of code |

> **All of it is free. All of it is synthetic for MVP. All of it improves the demo story.** + season flags

--- (Expanded — All Dimensions Included)

```sql
-- ============================================================
-- CORE TABLES
-- ============================================================

Products (
    sku_id, product_name, category, subcategory, brand,
    size, size_unit, regular_price, cost_price, margin_pct,
    is_seasonal, peak_seasons TEXT  -- e.g. '["diwali", "christmas"]'
)

Sales (
    date, week_number, year, sku_id, store_id,
    units_sold, revenue, price_paid, discount_pct,
    is_promo, promo_id, channel  -- 'physical' or 'online'
)

Promotions (
    promo_id, sku_id, start_date, end_date, discount_pct,
    promo_type,        -- 'TPR', 'BOGO', 'Bundle', 'Clearance'
    promo_mechanism,   -- 'percent_off', 'fixed_off', 'multibuy'
    display_flag,      -- 1 if in-store endcap display
    feature_flag,      -- 1 if in weekly flyer / email
    digital_flag,      -- 1 if online/app promotion
    funding_type       -- 'self_funded', 'vendor_funded', 'co_op'
)

Stores (
    store_id, store_name, channel,  -- 'physical', 'online'
    region,  -- 'NE', 'SE', 'MW', 'W'
    state, city, zip_code,
    size_tier,  -- 'large', 'medium', 'small'
    avg_weekly_footfall
)

-- ============================================================
-- SEASONALITY TABLES
-- ============================================================

CalendarEvents (
    date, event_name, event_type,  -- 'holiday', 'retail_event', 'cultural'
    intensity,  -- 1 (minor) to 5 (major like Christmas/Diwali)
    relevant_categories TEXT  -- '["nuts", "gifts", "all"]'
)

SeasonalityIndex (
    sku_id, week_of_year, seasonality_multiplier REAL,
    -- Pre-computed: how much higher/lower than annual avg this week is
    -- e.g., Pistachios week 46 (Diwali) = 3.2, week 3 (Jan dip) = 0.7
    confidence REAL
)

WeatherData (
    date, region, temperature_max_c REAL,
    precipitation_mm REAL, weather_bucket
    -- 'hot', 'warm', 'cold', 'wet' — for beverage/seasonal correlation
)

-- ============================================================
-- COMPETITOR TABLE
-- ============================================================

CompetitorEvents (
    date, competitor_name, category, product_description,
    estimated_discount_pct, promo_type, source,  -- 'synthetic', 'observed'
    impact_on_own_sales REAL  -- estimated % depression on own sales that week
)

-- ============================================================
-- CUSTOMER SEGMENTS TABLE
-- ============================================================

CustomerSegments (
    store_id, segment_name,  -- 'price_sensitive', 'loyalist', 'occasional'
    segment_share_pct REAL,  -- what % of that store's revenue this segment is
    price_elasticity REAL,   -- segment-specific elasticity (more sensitive = higher)
    promo_response_multiplier REAL,  -- how much more this segment responds to promos
    cannibalization_susceptibility REAL  -- how likely this segment switches SKUs
)
```

---

## 5. Technology Decisions — APIs vs Packages, Cloud vs Local

### 5.1 The Big Question: Do You Need Azure / OpenAI / LLM APIs?

| Capability | Packages Only (Free) | LLM/SLM API (Paid) | Recommendation |
|------------|:---:|:---:|---|
| **Demand forecasting** | ✅ Prophet, statsmodels, scikit-learn | Not needed | **Packages** |
| **Price elasticity modeling** | ✅ statsmodels (log-log regression) | Not needed | **Packages** |
| **Cannibalization detection** | ✅ Cross-elasticity matrix via regression | Not needed | **Packages** |
| **Promotion lift estimation** | ✅ Causal inference (DoWhy, EconML) | Not needed | **Packages** |
| **Natural language insights** | ⚠️ Template-based (limited) | ✅ GPT-4o / Claude for rich narrative | **Templates for MVP**, API for v2 |
| **Conversational interface** | ❌ | ✅ Chat-based promo advisor | **API for v2** |
| **Anomaly detection** | ✅ IsolationForest, PyOD | Not needed | **Packages** |

### **Verdict for MVP:**
> **You do NOT need Azure or any LLM API for the MVP demo.** All core analytical capabilities (elasticity, cannibalization, lift, profit) can be implemented with open-source Python packages. Use **template-based NL generation** for insights.

### **Verdict for Production v1:**
> Add **OpenAI GPT-4o-mini API** ($0.15/1M input tokens) or **Azure OpenAI** for:
> - Rich natural-language recommendation narratives
> - Merchant Q&A ("Why is cannibalization high for this product?")
> - Automated promo post-mortem summaries

### **Verdict for Production v2+:**
> Consider **Azure ML** or **AWS SageMaker** for:
> - Model training at scale (100K+ SKUs)
> - Model versioning and A/B testing
> - Real-time inference endpoints

### Why Dash and NOT Streamlit, Plotly standalone, or D3?

This is the most important frontend decision. Here is why each option was evaluated:

| Framework | Language | Interactivity | Production-ready? | Charts | Verdict |
|-----------|:---:|:---:|:---:|:---:|---|
| **Dash (by Plotly)** | Pure Python | ✅ Callbacks, dropdowns, sliders | ✅ Yes — same code runs dev→prod | ✅ Plotly built-in | **CHOOSE THIS** |
| Streamlit | Pure Python | ⚠️ Limited — re-runs entire script on every interaction | ❌ Hard to customize, state management is fragile, not multi-page-friendly | ✅ Plotly compatible | Good for quick notebook demos, not suitable once you add real-time analysis + multi-page routing |
| Plotly (standalone) | Python / JavaScript | ❌ Charts only — not a full app framework | ❌ Not a UI framework | ✅ Native | Plotly is a **charting library**, not an app. You use it INSIDE Dash |
| D3.js | JavaScript only | ✅ Maximum control | ✅ Yes | ✅ Maximum | Requires JavaScript expertise. You do not know React/JS — skip entirely |
| Panel (HoloViz) | Python | ✅ Good | ⚠️ Decent but smaller ecosystem | ✅ Multiple backends | Worth considering, but Dash has far more examples, community, and production deployments |
| Gradio | Python | ⚠️ Limited | ❌ ML demos only, not business apps | ⚠️ Basic | Designed for ML model demos, not multi-page business applications |

**Summary:** Dash is Plotly's app framework — you write Python components (dropdowns, sliders, tabs, tables), wire them up with Python callbacks, and it produces a full interactive web application. No HTML, no JavaScript, no React required. Run it on your laptop with one command — `python app.py` or `docker-compose up`.

### 5.2 Complete Technology Stack

#### What Does NOT Change From MVP to Production (Same Code Throughout)

```
Frontend:   Dash ──────────────────────────► Dash (same code, same files)
ML Engine:  pandas + statsmodels + Prophet ─► same packages (just more SKUs)
API layer:  Dash callbacks (no FastAPI needed for MVP, add later if needed)
```

#### What Changes Gradually (Not All at Once)

```
Stage 1 (MVP / Demo):     SQLite (Python built-in) + CSV files on disk, local laptop
Stage 2 (First Pilot):    Change ONE line: SQLite → managed PostgreSQL (if needed later)
Stage 3 (Paying Customers): Add login (Dash BasicAuth or Auth0), add CSV upload UI
Stage 4 (Scale 20+ clients): Add Redis cache ($10/mo), move to AWS ECS ($50–150/mo)
Stage 5 (Enterprise):     SOC 2, SSO, dedicated support — only when contracts require it
```

> **Kubernetes, Snowflake, Terraform, Celery, dbt, Airflow are NOT needed until you have 50+ concurrent users or 10M+ rows.** They were listed in the previous version as a complete picture but are overkill for anything before Series A.

#### MVP Stack (Week 1–5) — Everything in Python

```
┌─────────────────────────────────────────────────────┐
│              FRONTEND + BACKEND IN ONE               │
│  Dash 2.x (by Plotly) — full-stack Python app       │
│  plotly 5.x — charts (elasticity, heatmaps, bars)   │
│  dash-bootstrap-components — layout, cards, forms   │
│  dash-ag-grid — tables                              │
│                                                     │
├─────────────────────────────────────────────────────┤
│               ML / ANALYTICS ENGINE                  │
│  pandas + numpy — data manipulation                  │
│  statsmodels — elasticity (log-log OLS regression)   │
│  scikit-learn — cannibalization, clustering          │
│  prophet — baseline demand forecasting               │
│  scipy — optimization, confidence intervals          │
│                                                     │
├─────────────────────────────────────────────────────┤
│                   DATA LAYER                         │
│  SQLite — zero installation, built into Python       │
│  SQLAlchemy ORM — identical code for SQLite & PG     │
│  Synthetic data CSV files (dunnhumby-derived)        │
│                                                     │
├─────────────────────────────────────────────────────┤
│                 RUNNING IT                           │
│  python app.py → opens at localhost:8050             │
│  docker-compose up → same app, fully containerized   │
│  Share Docker image or run on any laptop for demo    │
└─────────────────────────────────────────────────────┘
```

#### Production Stack (First Pilot → Growth) — Gradual Additions Only

```
┌──────────────────────────────────────────────────────────────┐
│              FRONTEND + BACKEND                              │
│  Dash 2.x — same exact code as MVP                          │
│  dash-auth OR Auth0 — add login (single new file)           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                     DATA LAYER                               │
│  PostgreSQL managed (Supabase free tier or local Docker)     │
│  Change: engine = create_engine("postgresql://...")          │
│  That's the only code change for the database               │
│  Alembic — migrations (when schema changes)                 │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│               ML LAYER (add when needed)                     │
│  Same packages + LightGBM for ensemble forecasting           │
│  MLflow — track model versions (add at pilot stage)         │
│  openai API — NL insight generation (add at pilot, cheap)   │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE                              │
│  Docker Compose — run anywhere locally, no cloud needed      │
│  GitHub Actions — simple CI (run tests on push)             │
│  Sentry — error tracking (free tier sufficient early on)    │
│  Redis — ONLY add if response time exceeds 3 sec at scale   │
│                                                              │
│  Kubernetes / Snowflake / Airflow / Terraform:               │
│  ──────────────────────────────────────────────             │
│  Add these ONLY when you have 50+ concurrent users          │
│  (likely Series A or after 30+ paying mid-market clients)   │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. System Architecture

### 6.1 MVP Architecture Diagram (Everything Local, Everything Python)

```
                    ┌──────────────┐
                    │   Browser    │
                    │  (User/PM)   │
                    └──────┬───────┘
                           │ localhost:8050
                    ┌──────▼─────────────────┐
                    │   Dash App (app.py)     │
                    │   Python only           │
                    │                         │
                    │  Layout:                │
                    │  ┌─────────────────┐   │
                    │  │ PromoInputForm  │   │
                    │  │ (dcc.Dropdown,  │   │
                    │  │  dcc.Slider)    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  Callbacks:             │
                    │  ┌─────────────────┐   │
                    │  │ analyze_promo() │──►│─────► elasticity.py
                    │  │                 │   │─────► cannibalization.py
                    │  │                 │   │─────► demand_forecast.py
                    │  │                 │   │─────► profit_calculator.py
                    │  │                 │   │─────► risk_scorer.py
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │  SQLite DB       │   │  ← no installation needed
                    │  │  (single .db    │   │    just a file on disk
                    │  │   file)         │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
```

### 6.2 Production Architecture Diagram (Minimal Additions, Same Codebase)

```
                    ┌──────────────┐
                    │   Browser    │
                    │  (Customer)  │
                    └──────┬───────┘
                           │ HTTP   (localhost — demo runs locally)
                    ┌──────▼─────────────────┐
                    │   Same Dash App         │
                    │   + BasicAuth / Auth0   │  ← ONE new file added
                    │                         │
                    │   All callbacks same    │
                    │   All models same       │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │  PostgreSQL      │   │  ← Change 1 line in database.py
                    │  │  (local Docker) │   │    everything else identical
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ openai API      │   │  ← Optional: richer insights
                    │  │ (GPT-4o-mini)   │   │    ~$5–15/mo usage
                    │  └─────────────────┘   │
                    └─────────────────────────┘

  Customer POS Data  →  CSV upload UI  →  Same pipeline  →  Results
  (later: API connector when a customer requires it)
```

### 6.3 Core Module Decomposition (All Python — No JavaScript)

```
price-sense-ai/
│
├── app.py                       # Entry point: `python app.py` → localhost:8050
│                                # Dash app init + layout assembly
│
├── pages/                       # Dash multi-page app (Dash 2.x native routing)
│   ├── home.py                  # Dashboard overview (recent analyses, summary)
│   ├── analyze.py               # Main promo analysis page
│   ├── compare.py               # Scenario comparison page
│   └── catalog.py               # Product catalog & historical promo table
│
├── components/                  # Reusable Dash UI blocks (all Python)
│   ├── promo_input_form.py      # dcc.Dropdown, dcc.DatePicker, dcc.Slider
│   ├── recommendation_card.py   # dbc.Card with Go/No-Go + key metrics
│   ├── elasticity_chart.py      # plotly.express line chart (demand curve)
│   ├── cannibalization_heatmap.py  # px.imshow heatmap
│   ├── scenario_table.py        # dash_ag_grid table (4 discount scenarios)
│   ├── risk_gauge.py            # plotly go.Indicator gauge chart
│   └── insight_panel.py         # dbc.Alert blocks with narrative insights
│
├── callbacks/                   # Dash @callback functions (interactivity logic)
│   ├── analyze_callbacks.py     # Triggers ML engine on form submit
│   ├── scenario_callbacks.py    # Triggers scenario comparison
│   └── catalog_callbacks.py     # Product filter + history lookup
│
├── models/                      # Pure Python ML — no UI dependency
│   ├── elasticity.py            # Log-log OLS regression per SKU
│   ├── cannibalization.py       # Cross-elasticity matrix
│   ├── demand_forecast.py       # Prophet baseline forecast
│   ├── profit_calculator.py     # Full promo P&L model
│   └── risk_scorer.py           # Composite risk score (0.0–1.0)
│
├── services/
│   ├── promo_analyzer.py        # Orchestrates all 5 models into one result dict
│   ├── insight_generator.py     # Template strings → human-readable insights
│   └── scenario_engine.py       # Loops analyzer across N discount levels
│
├── data/
│   ├── database.py              # SQLAlchemy engine (SQLite MVP, PG prod)
│   ├── seed_data.py             # Load synthetic CSV → SQLite on startup
│   ├── synthetic_generator.py   # Generate 15 SKUs × 2yr weekly data
│   ├── raw/                     # dunnhumby CSV files (downloaded once)
│   ├── processed/               # Cleaned intermediate files
│   └── synthetic/               # generated_sales.csv, generated_promos.csv
│
├── config/
│   └── settings.py              # DATABASE_URL, OPENAI_KEY, debug flag
│                                # SQLite locally: sqlite:///./pricesense.db
│                                # PostgreSQL: postgresql://user:pass@host/db
│
├── notebooks/                   # Exploration only — not needed for app to run
│   ├── 01_data_exploration.ipynb
│   ├── 02_elasticity_modeling.ipynb
│   ├── 03_cannibalization_analysis.ipynb
│   └── 04_forecast_validation.ipynb
│
├── tests/
│   └── test_models.py           # Unit tests for ML calculations
│
├── requirements.txt             # All packages in one file
├── Dockerfile                   # For local Docker build + sharing
├── docker-compose.yml           # One command: docker-compose up → app at localhost:8050
├── .dockerignore                # Exclude venv, __pycache__, raw data from image
├── .env.example                 # Template: DATABASE_URL, OPENAI_KEY (optional)
└── README.md

NOTE: Docker is included from day one for easy sharing and local evaluation.
NOTE: No JavaScript files anywhere in this structure.
NOTE: To run the demo: `docker-compose up --build` → app available at localhost:8050 on any machine with Docker installed.
```

---

## 7. MVP vs Production — What Changes

### The Core Principle: Gradual, Not a Leap

The same Dash codebase runs from your laptop all the way to 50 paying customers. Each stage adds only what the current business situation demands. There is no frontend rewrite. There is no engine replacement. There is no "throw away the MVP" moment.

### Staged Evolution Matrix (Realistic for a PM-led build)

| Dimension | Stage 1: Local MVP | Stage 2: First Pilot | Stage 3: 5–15 Paying Customers | Stage 4: Scale (30+ clients) |
|-----------|:---:|:---:|:---:|:---:|
| **Frontend** | Dash (local) | Same Dash, deployed | Same Dash + auth | Same Dash + role tabs |
| **Database** | SQLite (zero install) | PostgreSQL (local Docker or Supabase) | Same PostgreSQL | Same + read replica if needed |
| **Deployment** | `python app.py` | `docker-compose up` (local demo) | Cloud if needed (Render/ECS) | AWS ECS (managed, no K8s) |
| **Auth** | None | BasicAuth (5 lines of code) | Auth0 free tier | Auth0 paid / SAML SSO |
| **Data** | Synthetic 15 SKUs | Customer CSV upload | CSV + scheduled refresh | API connector to POS/ERP |
| **NL Insights** | Template strings | Add openai API (~$5–15/mo) | GPT-4o-mini, same | Same |
| **ML Models** | OLS + Prophet | Same + LightGBM optional | Same | Add MLflow for versioning |
| **Monitoring** | Console logs | Sentry free tier | Sentry growth | Datadog |
| **Infra cost** | $0 | $5–15/mo | $50–150/mo | $300–800/mo |
| **Build effort from previous stage** | 5 weeks | 1–2 days | 2–3 weeks | 2–3 months |

> **Kubernetes, Snowflake, Terraform, Celery, dbt, Airflow:** add these ONLY once you have 50+ concurrent users. That is likely after Series A or 30+ paying mid-market clients. Do not build for that scale now.

### What "SQLite to PostgreSQL" Actually Looks Like (1 Line)

With SQLAlchemy ORM, the database swap is a single configuration change — no model rewrites, no query rewrites:

```python
# config/settings.py

# Stage 1 — MVP on your laptop (SQLite, zero installation required)
DATABASE_URL = "sqlite:///./pricesense.db"

# Stage 2 — Pilot (paste any PostgreSQL connection string here, nothing else changes)
DATABASE_URL = "postgresql://user:password@host:5432/pricesense"

# Every model, query, and service file stays IDENTICAL across both stages.
# SQLAlchemy handles the difference transparently.
```

### About SQLite — You Do NOT Need to Install Anything

SQLite is built into Python's standard library. It ships with Python itself.

```
You do NOT need to:              You DO just need to:
✗ Install a database server      ✓ import sqlite3  (already in Python)
✗ Run any background service     ✓ SQLAlchemy creates the .db file automatically
✗ Open any ports                 ✓ The entire database is one file: pricesense.db
✗ Set up credentials             ✓ Works offline, works on any laptop
```

The file `pricesense.db` sits in your project folder. It handles up to ~1M rows with no performance issues — more than enough for a 15-SKU demo with 2 years of weekly data.

### What Makes the MVP Demo Convincing

Even with synthetic data, the demo must show:
1. **Real analytical rigor** — The elasticity and cannibalization math must be sound
2. **Actionable output** — Not just charts, but a clear "do this" recommendation  
3. **Business language** — Speak in dollars, ROI, and risk — not p-values
4. **Horizontal proof** — Show it works for nuts AND beverages (switch category in demo)
5. **Speed** — Results in <3 seconds, not minutes

---

## 8. Component Breakdown & Package Registry

### 8.1 Complete Python Packages — requirements.txt

Dash is the full-stack framework. There is no separate backend server for MVP. Dash runs a Flask server internally — you write Python, it handles the HTTP layer.

```txt
# ============================================================
# SECTION 1: UI FRAMEWORK (Dash — replaces both frontend + API)
# ============================================================
dash==2.18.*                      # Core Dash framework (web server + UI)
dash-bootstrap-components==1.6.*  # Layout: Cards, Grid, Navbar, Tabs, Modals
dash-ag-grid==31.*                # Scenario comparison data table
plotly==5.24.*                    # All charts (built into Dash natively)

# Auth — add at Stage 2 only (one file, 5 lines)
# dash-auth==2.3.*               # BasicAuth (no external service needed)

# ============================================================
# SECTION 2: DATA & ML ENGINE (pure Python, no JS involvement)
# ============================================================
pandas==2.2.*               # Data manipulation
numpy==1.26.*               # Numerical computing
statsmodels==0.14.*         # Price elasticity (log-log OLS regression)
scikit-learn==1.5.*         # Cannibalization (cross-regression, clustering)
scipy==1.14.*               # Optimization, statistical tests, confidence intervals
prophet==1.1.*              # Demand baseline forecasting (Meta open-source)

# Seasonality & calendar (all free)
holidays==0.57.*            # Public holidays for 100+ countries — pip install holidays
pytrends==4.9.*             # Google Trends data — demand seasonality proxy (unofficial, free)
requests==2.32.*            # HTTP client — used to call Open-Meteo weather API (free, no key)

# Add at Stage 3 if forecast accuracy needs improvement:
# lightgbm==4.5.*           # Gradient boosting ensemble for better forecasts
# mlflow==2.16.*            # Model versioning and experiment tracking

# ============================================================
# SECTION 3: DATABASE (SQLite = zero install, PG = same code)
# ============================================================
sqlalchemy==2.0.*           # ORM — identical code for SQLite and PostgreSQL
alembic==1.13.*             # Schema migrations (needed when you add columns)
# psycopg2-binary==2.9.*    # Add only when switching to PostgreSQL

# ============================================================
# SECTION 4: NL INSIGHTS (add at Stage 2, optional)
# ============================================================
# openai==1.50.*            # GPT-4o-mini for rich natural-language insights
# python-dotenv==1.0.*      # Store API key in .env file (not in code)

# ============================================================
# SECTION 5: UTILITIES
# ============================================================
loguru==0.7.*               # Clean logging (replaces print statements)
faker==30.*                 # Synthetic data generation for demo

# ============================================================
# SECTION 6: TESTING
# ============================================================
pytest==8.3.*               # Unit tests for ML model calculations
```

### 8.2 Dash Component Reference (What Each Python Object Renders)\n\n**What this gives you (all in Python):**

| Dash Component | What it renders in the browser |
|---------------|--------------------------------|
| `dcc.Dropdown` | Product selector dropdown |
| `dcc.Slider` | Discount % slider (10%–40%) |
| `dcc.DatePickerRange` | Promo start/end date picker |
| `dbc.Card` | Recommendation card with metrics |
| `px.line` | Price-demand elasticity curve |
| `px.imshow` | Cannibalization heatmap |
| `go.Indicator` | Risk gauge (0–100) |
| `dag.AgGrid` | Scenario comparison table |
| `dbc.Navbar` | Top navigation bar |
| `dbc.Tabs` | Switch between Results / Charts / History |

**Why not Streamlit even for MVP?**
Streamlit re-runs the entire Python script top-to-bottom on every single user interaction. This makes it awkward for an app that has: a form → submit → show results → expand charts → change scenario. Dash uses event-driven callbacks — only the changed component updates. For a demo with 3–4 interactive steps, Dash feels like a real product. Streamlit feels like a notebook.

---

## 8.3 Docker Setup — Local Build, Run & Share

Docker lets you package the entire app — code, packages, database, data — into a single image. Anyone can run it with one command regardless of their OS or Python version. This is how you share it for evaluation.

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Prophet requires these)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages first (layer cache: only rebuilds if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Port that Dash runs on
EXPOSE 8050

# Generate synthetic data and start the app
# seed_data.py runs once and creates pricesense.db if it doesn't exist
CMD ["python", "app.py"]
```

### docker-compose.yml

```yaml
# docker-compose.yml
version: '3.9'

services:
  pricesense:
    build: .
    ports:
      - "8050:8050"            # Access at http://localhost:8050
    volumes:
      - ./data:/app/data       # Persist SQLite DB and downloaded datasets between restarts
    environment:
      - DATABASE_URL=sqlite:///./data/pricesense.db
      - DEBUG=false
      - HOST=0.0.0.0           # Required for Docker: listen on all interfaces, not just localhost
    restart: unless-stopped
```

### .dockerignore

```
venv/
.venv/
__pycache__/
*.pyc
*.pyo
.env
.git/
*.ipynb_checkpoints/
data/raw/              # Raw dunnhumby CSVs (too large for image, mount as volume)
```

### .env.example (commit this, not your real .env)

```bash
# Copy to .env and fill in values. Never commit .env to git.

DATABASE_URL=sqlite:///./data/pricesense.db
DEBUG=true
HOST=127.0.0.1

# Optional — only needed for Stage 2 NL insights:
# OPENAI_API_KEY=sk-...
```

### Commands for Local Use

```bash
# First time setup
git clone <your-repo>
cd price-sense-ai

# Option A: Run with Docker (recommended for sharing)
docker-compose up            # Builds image, starts app → http://localhost:8050
docker-compose up --build    # Force rebuild (after requirements.txt changes)
docker-compose down          # Stop

# Option B: Run without Docker (faster for development)
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt
python data/synthetic_generator.py   # Generate demo data once
python app.py                # → http://localhost:8050

# Run tests
pytest tests/
```

### What Docker Gives You for Sharing

```
You send someone:               They run:                    They get:
───────────────────────────    ────────────────────    ────────────────────
GitHub repo link           docker-compose up         Full app at localhost:8050
                                                     Pre-seeded with 15 SKUs
                                                     2 years of demo data
                                                     All charts working
                                                     No Python setup needed

No "it works on my machine" issues.
No Python version conflicts.
No missing package errors.
Works on Windows, Mac, Linux identically.
``` — The Analytical Engine

### 9.1 Price Elasticity Model

**Goal:** Estimate how a % change in price affects demand for each SKU.

```
Model: Log-Log OLS Regression
  ln(quantity) = β₀ + β₁·ln(price) + β₂·seasonality + β₃·trend + ε

  Own-price elasticity = β₁
  If β₁ = -1.8 → A 1% price drop increases volume by 1.8%

Example for Salted Pistachios 16oz:
  Elasticity = -2.1 (elastic — price-sensitive product)
  At 25% off: Expected volume lift = 25% × 2.1 = ~52.5% (base estimate)
  Adjusted for diminishing returns: ~42% (realistic)
```

**Implementation:**
```python
import statsmodels.api as sm
import numpy as np

def estimate_elasticity(sales_df, sku_id):
    sku_data = sales_df[sales_df['sku_id'] == sku_id].copy()
    sku_data['ln_qty'] = np.log(sku_data['units_sold'] + 1)
    sku_data['ln_price'] = np.log(sku_data['price_paid'])
    
    X = sm.add_constant(sku_data[['ln_price', 'week_of_year', 'trend']])
    y = sku_data['ln_qty']
    
    model = sm.OLS(y, X).fit()
    elasticity = model.params['ln_price']  # β₁
    
    return {
        'sku_id': sku_id,
        'elasticity': elasticity,
        'r_squared': model.rsquared,
        'p_value': model.pvalues['ln_price'],
        'confidence_interval': model.conf_int().loc['ln_price'].tolist()
    }
```

### 9.2 Cannibalization Model

**Goal:** When Pistachios go on promo, how much do Almonds and Mixed Nuts lose?

```
Model: Cross-Elasticity Matrix via Multivariate Regression
  ln(qty_almonds) = α + γ·ln(price_pistachios) + δ·ln(price_almonds) + ...

  Cross-elasticity γ > 0 → Substitutes (cannibalization risk)
  Cross-elasticity γ < 0 → Complements (halo effect)
  Cross-elasticity γ ≈ 0 → Independent products
```

**Output: Cannibalization Matrix**
```
                  Pistachios 16oz     Almonds 16oz     Mixed Nuts
                  price change        price change     price change
Pistachios 16oz      -2.1               +0.8             +0.3
Almonds 16oz         +0.9               -1.7             +0.4
Mixed Nuts           +0.2               +0.3             -1.4
                     ────               ────             ────
                   own-price          cross-price      cross-price
```

Reading: "When Pistachios 16oz price drops, Almonds 16oz volume drops (cross-elasticity +0.9 means a price cut in Pistachios diverts 0.9% of Almonds volume per 1% Pistachio price cut)"

### 9.3 Demand Forecasting

**Goal:** What would sales be WITHOUT the promotion? (Counterfactual baseline)

```
Model: Prophet (MVP) → Prophet + LightGBM Ensemble (Production)

Components:
  ŷ(t) = g(t) + s(t) + h(t) + p(t) + ε(t)
  
  g(t) = trend (linear or logistic growth)
  s(t) = seasonality (weekly, yearly)
  h(t) = holiday effects
  p(t) = promotion effect (what we're trying to measure)
```

**Key insight:** We forecast the BASELINE (no-promo scenario), then the promo lift is:
```
Incremental units = Actual promo sales - Baseline forecast
```

### 9.4 Profit Calculator

**The core P&L for a promotion decision:**

```
PROMOTION P&L MODEL
═══════════════════════════════════════════════════════
                                    Example: Pistachios 16oz @ 25% off

Regular Price:                      $12.99
Promo Price (25% off):              $9.74
Cost Price:                         $6.50
Regular Margin:                     $6.49 (50.0%)
Promo Margin:                       $3.24 (33.3%)

Baseline Weekly Volume:             3,000 units
Promo Volume (with +42% lift):      4,260 units
Incremental Units:                  1,260 units

REVENUE ANALYSIS
────────────────────────────────────────────────────
Baseline Revenue (no promo):        $38,970
Promo Revenue:                      $41,492
Incremental Revenue:                +$2,522

MARGIN ANALYSIS
────────────────────────────────────────────────────
Baseline Margin (no promo):         $19,470 (3,000 × $6.49)
Promo Margin (all units):           $13,802 (4,260 × $3.24)
Margin on Incremental Units:        +$4,082 (1,260 × $3.24)
Margin Loss on Base Units:          -$9,750 (3,000 × -$3.25)
─────────────────────────────────────────────────────
NET MARGIN IMPACT:                  -$5,668 ⚠️

CANNIBALIZATION ADJUSTMENT
────────────────────────────────────────────────────
Lost Almonds 16oz sales:            -180 units × $6.19 margin = -$1,114
Lost Mixed Nuts sales:              -60 units × $5.50 margin  = -$330
─────────────────────────────────────────────────────
TOTAL CANNIBALIZATION COST:         -$1,444

═══════════════════════════════════════════════════════
NET INCREMENTAL PROFIT:             -$7,112 ❌
PROMO ROI:                          Negative
RECOMMENDATION:                     DO NOT RUN at 25% off

💡 ALTERNATIVE: At 15% off:
   Estimated lift: +28%
   Net incremental profit: +$1,120 ✅
   Recommendation: RUN at 15% off
═══════════════════════════════════════════════════════
```

### 9.5 Risk Scorer

**Composite risk score (0.0–1.0) based on:**

| Factor | Weight | Low Risk (0) | High Risk (1) |
|--------|--------|:---:|:---:|
| Elasticity confidence | 25% | Tight CI, high R² | Wide CI, low R² |
| Data recency | 20% | <3 months old | >12 months old |
| Cannibalization breadth | 20% | Affects 0–1 SKUs | Affects 5+ SKUs |
| Discount depth vs. history | 15% | Within tested range | Beyond tested range |
| Seasonal anomaly risk | 10% | Normal period | Holiday/peak period |
| Category volatility | 10% | Stable demand | Highly variable demand |

```
Risk Score = Σ (factor_score × weight)

0.0–0.3 → LOW RISK    (Green)  — High confidence in estimates
0.3–0.6 → MEDIUM RISK (Yellow) — Reasonable confidence, some uncertainty
0.6–1.0 → HIGH RISK   (Red)    — Low confidence, proceed with caution
```

### 9.6 Insight Generator (Template-Based for MVP)

```python
INSIGHT_TEMPLATES = {
    "high_cannibalization": (
        "⚠️ Running {discount}% off on {product} is projected to cannibalize "
        "{cannibal_pct}% of {affected_product} sales, costing ${cannibal_cost:,.0f} "
        "in lost margin. Consider promoting {product} only when {affected_product} "
        "is not also being featured."
    ),
    "discount_depth_alternative": (
        "💡 A {alt_discount}% discount would capture {capture_pct}% of the volume "
        "lift at {margin_savings}% less margin erosion. This translates to "
        "${profit_diff:,.0f} more profit."
    ),
    "strong_recommendation": (
        "✅ This promotion is projected to generate ${inc_profit:,.0f} in incremental "
        "profit with a {roi}x ROI. Historical promotions for {product} have performed "
        "within {conf}% of projections."
    ),
    "negative_recommendation": (
        "❌ This promotion is projected to lose ${loss:,.0f} after accounting for "
        "margin erosion and cannibalization. The primary driver is {loss_driver}."
    ),
}
```

---

## 10. Enterprise Architecture Considerations

### 10.1 Capacity Planning (User Load Forecasting)

**Target: Mid-market retailers, $50M–$500M revenue**

| Phase | Timeline | Customers | Users/Customer | Total Users | Concurrent (Peak) |
|-------|----------|:---------:|:--------------:|:-----------:|:-----------------:|
| Demo/Pilot | Month 1–3 | 1–3 | 2–5 | 5–15 | 3–5 |
| Early Traction | Month 4–12 | 5–15 | 5–15 | 50–200 | 15–40 |
| Growth | Year 2 | 20–50 | 10–25 | 300–1,000 | 60–200 |
| Scale | Year 3+ | 50–200 | 15–50 | 2,000–10,000 | 400–2,000 |

**Usage Patterns:**
- Peak usage: Monday–Wednesday (promo planning for next week)
- Heaviest load: 9am–12pm local time
- Average analysis request: ~2–5 seconds compute
- Average session: 3–5 analyses per login
- Data volume per customer: 100MB–5GB (depending on SKU count and history depth)

### 10.2 Infrastructure Sizing

| Phase | Compute | Database | Cache | Storage | Est. Cost/mo |
|-------|---------|----------|-------|---------|:---:|
| **MVP** | 1 vCPU, 1GB RAM (local) | SQLite (file) | None | 100MB | $0 |
| **Pilot** | 2 vCPU, 4GB RAM | PostgreSQL (shared) | Redis 256MB | 10GB | $50–$100 |
| **Early** | 4 vCPU, 8GB RAM | PostgreSQL (dedicated) | Redis 1GB | 100GB | $300–$500 |
| **Growth** | 2× (4 vCPU, 8GB) + autoscale | PostgreSQL (HA) | Redis 4GB | 500GB | $1,500–$3,000 |
| **Scale** | K8s cluster (8–16 nodes) | PostgreSQL (cluster) | Redis cluster | 5TB | $5,000–$15,000 |

### 10.3 Security & Compliance Roadmap

| Requirement | MVP | Pilot | GA |
|-------------|:---:|:-----:|:--:|
| HTTPS/TLS | ✅ | ✅ | ✅ |
| Authentication | Basic | Auth0 | SAML SSO |
| Authorization (RBAC) | ❌ | Basic | Full |
| Data encryption at rest | ❌ | ✅ | ✅ |
| Data encryption in transit | ✅ | ✅ | ✅ |
| Tenant data isolation | N/A | Schema-level | Row-level + encryption |
| Audit logging | ❌ | Basic | Full |
| SOC 2 Type II | ❌ | ❌ | ✅ |
| GDPR compliance | ❌ | Partial | ✅ |
| Penetration testing | ❌ | ❌ | Annual |
| Backup & DR | ❌ | Daily backup | Multi-region, RPO <1hr |

### 10.4 API Design (Key Endpoints)

```yaml
# Core Promotion Analysis
POST /api/v1/promotions/analyze
  Input:  { sku_id, discount_pct, start_date, end_date, channels[] }
  Output: { recommendation, lift, cannibalization, profit, risk, insights[] }

POST /api/v1/promotions/compare
  Input:  { sku_id, scenarios: [{ discount_pct, start_date, end_date }] }
  Output: { scenarios: [{ ...analysis }], best_scenario, comparison_insights }

# Product Catalog
GET  /api/v1/products
GET  /api/v1/products/{sku_id}
GET  /api/v1/products/{sku_id}/history
GET  /api/v1/categories

# Promo History
GET  /api/v1/promotions/history?sku_id=&date_range=
GET  /api/v1/promotions/{promo_id}/postmortem

# Health & Meta
GET  /api/v1/health
GET  /api/v1/meta/categories
GET  /api/v1/meta/discount-types
```

---

## 11. Work Plan & Sprint Schedule

### 11.1 MVP Build Plan (5 Weeks — Solo Developer, Python Only)

#### Week 1: Foundation & Data (Days 1–5)

| Day | Task | Output |
|-----|------|--------|
| 1 | `pip install dash dash-bootstrap-components plotly pandas sqlalchemy`, scaffold folder structure, `app.py` with empty layout | App opens at localhost:8050 with navbar |
| 2 | Download dunnhumby dataset; run EDA notebook to understand distributions (price ranges, promo frequencies, cross-product patterns) | EDA notebook with key distributions |
| 3 | Build `synthetic_generator.py` (15 SKUs: 9 nuts + 6 beverages, 2yr weekly data, 50 promos, embedded cross-elasticity signals) | CSV files in `data/synthetic/` |
| 4 | `database.py` with SQLAlchemy + SQLite, `seed_data.py` loads CSVs into DB, basic product query working | SQLite file created on startup, 15 SKUs queryable |
| 5 | Build `pages/catalog.py` — product browser page in Dash showing SKU list, hierarchy, regular price | Catalog page visible in browser |

#### Week 2: Core ML Models (Days 6–10)

| Day | Task | Output |
|-----|------|--------|
| 6 | Price elasticity model (log-log regression per SKU) | `models/elasticity.py` with validated elasticities |
| 7 | Cross-elasticity / cannibalization matrix | `models/cannibalization.py` with 9×9 matrix |
| 8 | Demand baseline forecast (Prophet) | `models/demand_forecast.py` with backtested accuracy |
| 9 | Profit calculator + P&L model | `services/profit_calculator.py` with full P&L |
| 10 | Risk scorer + model integration testing | All models callable via unified `promo_analyzer.py` |

#### Week 3: API & Insight Engine (Days 11–15)

| Day | Task | Output |
|-----|------|--------|
| 11 | `POST /analyze` endpoint — full pipeline integration | End-to-end: input → analysis → JSON response |
| 12 | Scenario comparison engine + `POST /compare` endpoint | Compare 4 discount levels side-by-side |
| 13 | Template-based insight generator | Human-readable insights in API response |
| 14 | Historical promo lookup + `GET /history` endpoint | Browse past promo performance |
| 15 | API testing, edge cases, error handling | Robust API with proper error messages |

#### Week 4: UI & Visualization (Days 16–20)

| Day | Task | Output |
|-----|------|--------|
| 16 | `pages/analyze.py` — promo input form using dcc.Dropdown, dcc.Slider, dcc.DatePickerRange, and a Submit button | Form renders, inputs save to dcc.Store |
| 17 | `components/recommendation_card.py` — dbc.Card showing Go/No-Go badge, lift %, profit, ROI | Recommendation card appears after form submit |
| 18 | `components/elasticity_chart.py` (px.line), `components/cannibalization_heatmap.py` (px.imshow), `components/risk_gauge.py` (go.Indicator) | Three interactive Plotly charts embedded in results page |
| 19 | `pages/compare.py` — scenario comparison using dash_ag_grid table (10% / 15% / 20% / 25% / 30% side by side), category switcher (nuts → beverages) | Horizontal product proof, scenario table |
| 20 | dbc.Navbar with logo + page links, loading spinners, color-coded recommendation (green/yellow/red), layout responsiveness | Professional-looking demo ready |

#### Week 5: Demo Prep & Polish (Days 21–25)

| Day | Task | Output |
|-----|------|--------|
| 21 | Add beverage category demo data (6 more SKUs) | 15 total SKUs across 2 categories |
| 22 | Final Docker test: `docker-compose up --build` on a clean machine | Verify anyone with Docker can run the demo |
| 23 | Screen-share or laptop demo walkthrough rehearsal with the prospect | Polished 15-min in-person or Zoom demo |
| 24 | Demo script rehearsal, edge case fixes | Smooth 15-min demo flow |
| 25 | Documentation, README, backup plan | Ready for customer demo |

### 11.2 Milestone Checkpoints

```
Week 1 ──► "I can generate realistic retail data and serve it via API"
Week 2 ──► "I can compute elasticity, cannibalization, and forecast for any SKU"
Week 3 ──► "I can send a promo scenario and get back a full recommendation"
Week 4 ──► "I can show an interactive UI with charts and insights"
Week 5 ──► "I can run a convincing live demo for a prospective customer"
```

---

## 12. Demo Script — Reference Customer Walkthrough

### Setup (Before Demo)
- App loaded with specialty nuts + beverage data
- 2 years of pre-loaded synthetic history
- Pre-run a few analyses so historical data is visible

### Demo Flow (15 minutes)

**1. The Hook (2 min)**
> "Imagine you're the Category Manager at NutCo, a $120M specialty nuts retailer. You're planning next week's promo and considering 25% off on your best-seller, Salted Pistachios 16oz. Let's see what Price Sense AI tells us..."

**2. Input the Promotion (1 min)**
- Select: Salted Pistachios 16oz
- Discount: 25%
- Duration: 1 week, starting March 8
- Click "Analyze"

**3. The Recommendation (3 min)**
- Show the headline: **"⚠️ NOT RECOMMENDED at 25% — Consider 15% instead"**
- Walk through: volume lift (+42%), but heavy cannibalization (-18% from Almonds)
- Show the profit impact: **Net loss of $7,112** after cannibalization
- Highlight the alternative: 15% off yields **+$1,120 profit**

**4. Deep Dive — Charts (3 min)**
- Elasticity curve: "See how Pistachios are quite elastic — but there are diminishing returns past 20%"
- Cannibalization heatmap: "25% off Pistachios pulls heavily from Almonds 16oz and slightly from Mixed Nuts"
- Scenario comparison: Side-by-side of 10%/15%/20%/25%/30% — clearly 15% is the sweet spot

**5. Horizontal Proof — Beverages (2 min)**
- Switch to Beverage category
- Run: "What about 20% off Craft Cola 12-pack?"
- Show a completely different elasticity profile and recommendation
- Point: "Same engine, different category — works for any vertical"

**6. Business Value Recap (2 min)**
> "If NutCo runs 200 promotions a year and Price Sense AI prevents even 30% of money-losing promos and optimizes discount depth on the rest, that's $1.5M–$3M in annual value for a $120M retailer."

**7. Vision / Roadmap (2 min)**
- "Today: individual promo analysis"
- "Next: calendar-level optimization — 'What's the best promo plan for Q2?'"
- "Then: automated monitoring — 'Your running promo is underperforming, consider ending early'"
- "Data integration: direct POS/ERP connector — no CSV uploads"

---

## 13. Risk Register & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|:---:|:---:|---|
| 1 | **Synthetic data doesn't feel realistic** | Medium | High | Use dunnhumby distributions as foundation; validate with retail domain expert |
| 2 | **Elasticity model gives implausible results** | Medium | High | Constrain elasticity range [-0.5, -4.0]; add sanity checks; show confidence intervals |
| 3 | **Demo prospect asks "what about MY data?"** | High | Medium | Prepare CSV upload feature; have a "bring your own data" slide ready |
| 4 | **Dash UI looks too plain** | Low | Medium | dash-bootstrap-components gives professional layout out of the box; use a bootswatch theme (e.g., `dbc.themes.FLATLY`) for polished look in 1 line |
| 5 | **Prospect asks about integrations** | High | Low | Prepare integration roadmap slide (Shopify, Square, SAP connectors planned) |
| 6 | **Model takes too long (>5 sec)** | Low | High | Pre-compute elasticities; cache results; use approximations for real-time |
| 7 | **Cannibalization signals are weak in synthetic data** | Medium | High | Manually inject strong cross-elasticity; validate with economic intuition |
| 8 | **Prospect asks about forecast accuracy** | High | Medium | Show backtesting results with MAPE/WMAPE; be transparent about confidence intervals |

---

## 14. Appendix

### A. Glossary of Key Retail Promotion Terms

| Term | Definition |
|------|-----------|
| **TPR** | Temporary Price Reduction — a straightforward % off |
| **BOGO** | Buy One Get One (Free / Half Off) |
| **Feature** | Product is featured in weekly flyer / email |
| **Display** | Product has special in-store display/endcap |
| **Lift** | % increase in sales during promo vs baseline |
| **Cannibalization** | Sales lost by related products due to promo |
| **Halo Effect** | Positive sales impact on related products |
| **Forward Buy** | Customers stock up during promo, reducing future sales |
| **Pantry Loading** | Consumer version of forward buy |
| **Incremental Volume** | Additional units sold that wouldn't have sold without promo |
| **Own-Price Elasticity** | % change in qty demanded per 1% change in own price |
| **Cross-Price Elasticity** | % change in qty of Product A per 1% change in Product B's price |
| **Baseline** | Expected sales without any promotion |
| **MAPE** | Mean Absolute Percentage Error — forecast accuracy metric |

### B. Key Formulas Quick Reference

```
Own-Price Elasticity:
  ε = (∂Q/Q) / (∂P/P) = ∂ln(Q) / ∂ln(P)

Expected Lift:
  Lift% ≈ |ε| × Discount% × diminishing_return_factor

Incremental Volume:
  ΔQ = Baseline_Q × Lift%

Cannibalization Volume Loss (per affected SKU):
  ΔQ_affected = Baseline_Q_affected × Cross_Elasticity × Discount%

Promotion Profit:
  π_promo = (Promo_Price - Cost) × Promo_Volume
  π_baseline = (Regular_Price - Cost) × Baseline_Volume
  π_incremental = π_promo - π_baseline - Σ(cannibalization_costs)

Promo ROI:
  ROI = π_incremental / (Regular_Margin - Promo_Margin) × Baseline_Volume
```

### C. Recommended Reading / Resources

1. **"Pricing and Revenue Optimization"** by Robert Phillips — Elasticity modeling theory
2. **"Causal Inference for The Brave and True"** (free online) — Measuring true promo lift
3. **dunnhumby Source Files Documentation** — Understanding the reference dataset
4. **Meta Prophet Documentation** — Time series forecasting setup
5. **Dash Documentation** (dash.plotly.com) — Full-stack Python web app framework
6. **Dash Bootstrap Components Gallery** (dash-bootstrap-components.opensource.faculty.ai) — UI component reference

### D. Competitive Landscape

| Competitor | Positioning | Price Point | Our Differentiation |
|-----------|-------------|-------------|---------------------|
| Revionics (Aptos) | Enterprise promo optimization | $200K+/yr | Too expensive and complex for mid-market |
| DemandTec (Acoustic) | CPG-focused promo planning | $150K+/yr | CPG-centric, not retailer-friendly |
| Kognitwin | Digital twin for pricing | $100K+/yr | More industrial, less retail |
| **Price Sense AI** | **Mid-market promo intelligence** | **$25K–$75K/yr** | **Right-sized for mid-market, AI-first, fast time-to-value** |

### E. Pricing Strategy (For Your Reference)

| Tier | Target | Features | Price Range |
|------|--------|----------|:-----------:|
| **Starter** | $50M–$100M retailers | 1 category, basic analysis, 3 users | $2K–$3K/mo |
| **Growth** | $100M–$250M retailers | Multi-category, scenario comparison, 10 users | $4K–$6K/mo |
| **Enterprise** | $250M–$500M retailers | Full suite, SSO, API access, dedicated support, 25+ users | Custom |

---

## Summary: Your Next Steps

### This Week (Immediate Actions)
- [ ] Create a Python virtual environment: `python -m venv venv` then `venv\Scripts\activate`
- [ ] Install all packages: `pip install dash dash-bootstrap-components dash-ag-grid plotly pandas sqlalchemy alembic statsmodels prophet scikit-learn scipy numpy loguru faker holidays pytrends requests pytest`
- [ ] Download the dunnhumby "Complete Journey" dataset from dunnhumby.com/source-files (free, requires email registration)
- [ ] Create the folder structure from Section 6.3 (including `Dockerfile` and `docker-compose.yml` from Section 8.3)
- [ ] Create a minimal `app.py` and confirm it opens at localhost:8050 with `python app.py`
- [ ] Test Docker works: `docker-compose up` → same app at localhost:8050 (proves it’s shareable)
- [ ] Run the initial EDA notebook on dunnhumby data to understand price distributions, promo flags, and household seasonality patterns
- [ ] Finalize the synthetic data design: 15 SKUs, 25 stores, 2yr weekly data, seasonal multipliers per Section 4.2B

### Next 2 Weeks
- [ ] Build `synthetic_generator.py`: embed seasonality (holiday multipliers), store regions, customer segments, competitor events — all detailed in Section 4.2B
- [ ] Build `data/database.py` with SQLAlchemy + all 8 schema tables from Section 4.3
- [ ] Implement all 5 ML models with seasonality as a feature: elasticity, cannibalization, demand forecast (Prophet with holiday regressors), profit calculator, risk scorer
- [ ] Wire up Dash callbacks so form submit triggers the full analysis pipeline

### Week 3–4
- [ ] Build all Dash pages: analyze, compare scenarios, catalog with history, store heatmap
- [ ] Integrate all Plotly charts: elasticity curve, cannibalization heatmap, risk gauge, scenario table, seasonality overlay chart
- [ ] Add category switcher (nuts → beverages) and store/region filter to prove horizontal + multi-location product fit

### Week 5
- [ ] Final Docker test: `docker-compose up --build`, share with someone who has never set up Python and confirm they can run it
- [ ] Final Docker test: `docker-compose up --build` → confirm app loads clean at localhost:8050 with no setup steps
- [ ] Rehearse the 15-minute demo script (Section 12)
- [ ] Prepare answers: "What about my data?", "How does it integrate with my POS?", "What does the roadmap look like?"

---

> **Remember:** The demo’s job is not to be a finished product. It’s to make the prospect say: *"I want this for my data."* Every design decision should optimize for that moment.

> **Data philosophy:** Include all 8 dimensions in synthetic data from day one. It’s all free. It makes the model smarter. It makes the demo story richer. You can always turn off a dimension — you can’t add one at demo time if you didn’t build it in.

> **Sharing philosophy:** If you can’t give someone a GitHub link and have them run `docker-compose up` to see a live version in 5 minutes, the demo is not ready.

---

*Document Version: 2.0 | Created: March 1, 2026 | Updated: March 1, 2026 | Author: Price Sense AI Product Team*
