"""
data/synthetic_generator.py
────────────────────────────
Generates realistic synthetic retail data for the Price Sense AI demo.

Produces:
  • 15 SKUs (9 nuts + 6 beverages) across 3 sizes
  • 25 stores across 4 regions
  • 104 weeks (2 years) of weekly sales with embedded seasonality
  • 60 historical promotions with varying discount depths
  • Cross-elasticity signals (cannibalization between substitutes)
  • Seasonal multipliers (Diwali ×3.0, Christmas ×2.5, summer dip ×0.7 etc.)
  • Customer segment profiles per store
  • Synthetic competitor events
  • Seasonality index table pre-computed per SKU × week

Run standalone: python data/synthetic_generator.py
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent
SYNTHETIC_DIR = BASE_DIR / "synthetic"
SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Reference date: data spans 2024-01-01 → 2025-12-28 (104 weeks) ───────────
START_DATE = date(2024, 1, 1)
END_DATE   = date(2025, 12, 28)

# ── SKU catalog ───────────────────────────────────────────────────────────────
PRODUCTS = [
    # Nuts (9 SKUs)
    {"sku_id": "NUT-PIST-08", "product_name": "Salted Pistachios 8oz",  "category": "Nuts", "subcategory": "Pistachios", "brand": "NutCo",     "size": 8,  "size_unit": "oz", "regular_price": 7.99,  "cost_price": 3.50, "is_seasonal": True,  "peak_seasons": ["diwali", "lunar_new_year", "christmas"]},
    {"sku_id": "NUT-PIST-16", "product_name": "Salted Pistachios 16oz", "category": "Nuts", "subcategory": "Pistachios", "brand": "NutCo",     "size": 16, "size_unit": "oz", "regular_price": 12.99, "cost_price": 6.50, "is_seasonal": True,  "peak_seasons": ["diwali", "lunar_new_year", "christmas"]},
    {"sku_id": "NUT-PIST-32", "product_name": "Salted Pistachios 32oz", "category": "Nuts", "subcategory": "Pistachios", "brand": "NutCo",     "size": 32, "size_unit": "oz", "regular_price": 22.99, "cost_price": 11.50,"is_seasonal": True,  "peak_seasons": ["diwali", "christmas"]},
    {"sku_id": "NUT-ALMD-08", "product_name": "Premium Almonds 8oz",    "category": "Nuts", "subcategory": "Almonds",    "brand": "NutCo",     "size": 8,  "size_unit": "oz", "regular_price": 6.49,  "cost_price": 2.80, "is_seasonal": True,  "peak_seasons": ["valentines", "mothers_day", "christmas"]},
    {"sku_id": "NUT-ALMD-16", "product_name": "Premium Almonds 16oz",   "category": "Nuts", "subcategory": "Almonds",    "brand": "NutCo",     "size": 16, "size_unit": "oz", "regular_price": 10.99, "cost_price": 5.20, "is_seasonal": True,  "peak_seasons": ["valentines", "mothers_day", "christmas"]},
    {"sku_id": "NUT-ALMD-32", "product_name": "Premium Almonds 32oz",   "category": "Nuts", "subcategory": "Almonds",    "brand": "NutCo",     "size": 32, "size_unit": "oz", "regular_price": 19.99, "cost_price": 9.50, "is_seasonal": False, "peak_seasons": []},
    {"sku_id": "NUT-MIXD-08", "product_name": "Mixed Nuts Gift 8oz",    "category": "Nuts", "subcategory": "Mixed Nuts", "brand": "NutCo",     "size": 8,  "size_unit": "oz", "regular_price": 8.49,  "cost_price": 3.80, "is_seasonal": True,  "peak_seasons": ["diwali", "christmas", "lunar_new_year"]},
    {"sku_id": "NUT-MIXD-16", "product_name": "Mixed Nuts Gift 16oz",   "category": "Nuts", "subcategory": "Mixed Nuts", "brand": "NutCo",     "size": 16, "size_unit": "oz", "regular_price": 14.99, "cost_price": 7.20, "is_seasonal": True,  "peak_seasons": ["diwali", "christmas", "lunar_new_year"]},
    {"sku_id": "NUT-MIXD-32", "product_name": "Mixed Nuts Gift 32oz",   "category": "Nuts", "subcategory": "Mixed Nuts", "brand": "NutCo",     "size": 32, "size_unit": "oz", "regular_price": 26.99, "cost_price": 13.00,"is_seasonal": True,  "peak_seasons": ["christmas"]},
    # Beverages (6 SKUs)
    {"sku_id": "BEV-COLA-12", "product_name": "Craft Cola 12-pack",     "category": "Beverages", "subcategory": "Craft Soda",   "brand": "BrewCo",   "size": 12, "size_unit": "pk",  "regular_price": 14.99, "cost_price": 6.80, "is_seasonal": True,  "peak_seasons": ["summer", "independence_day"]},
    {"sku_id": "BEV-COLA-24", "product_name": "Craft Cola 24-pack",     "category": "Beverages", "subcategory": "Craft Soda",   "brand": "BrewCo",   "size": 24, "size_unit": "pk",  "regular_price": 26.99, "cost_price": 12.00,"is_seasonal": True,  "peak_seasons": ["summer", "independence_day"]},
    {"sku_id": "BEV-WTER-06", "product_name": "Sparkling Water 6-pack", "category": "Beverages", "subcategory": "Sparkling",    "brand": "BubbleCo", "size": 6,  "size_unit": "pk",  "regular_price": 8.99,  "cost_price": 3.50, "is_seasonal": True,  "peak_seasons": ["summer"]},
    {"sku_id": "BEV-WTER-12", "product_name": "Sparkling Water 12-pack","category": "Beverages", "subcategory": "Sparkling",    "brand": "BubbleCo", "size": 12, "size_unit": "pk",  "regular_price": 15.99, "cost_price": 6.20, "is_seasonal": True,  "peak_seasons": ["summer"]},
    {"sku_id": "BEV-JUIC-32", "product_name": "Cold Press Juice 32oz",  "category": "Beverages", "subcategory": "Juice",        "brand": "FreshCo",  "size": 32, "size_unit": "oz",  "regular_price": 9.99,  "cost_price": 4.20, "is_seasonal": False, "peak_seasons": []},
    {"sku_id": "BEV-JUIC-64", "product_name": "Cold Press Juice 64oz",  "category": "Beverages", "subcategory": "Juice",        "brand": "FreshCo",  "size": 64, "size_unit": "oz",  "regular_price": 16.99, "cost_price": 7.50, "is_seasonal": False, "peak_seasons": []},
]

# Cross-elasticity substitution pairs (sku_a price cut → sku_b volume drop)
# Positive = substitutes (cannibalization)
CROSS_ELASTICITIES: dict[tuple[str, str], float] = {
    ("NUT-PIST-16", "NUT-ALMD-16"): 0.85,
    ("NUT-PIST-16", "NUT-MIXD-16"): 0.40,
    ("NUT-ALMD-16", "NUT-PIST-16"): 0.75,
    ("NUT-ALMD-16", "NUT-MIXD-16"): 0.35,
    ("NUT-MIXD-16", "NUT-PIST-16"): 0.30,
    ("NUT-MIXD-16", "NUT-ALMD-16"): 0.28,
    ("NUT-PIST-08", "NUT-ALMD-08"): 0.70,
    ("NUT-ALMD-08", "NUT-PIST-08"): 0.65,
    ("NUT-PIST-32", "NUT-MIXD-32"): 0.45,
    ("BEV-COLA-12", "BEV-COLA-24"): 0.60,
    ("BEV-COLA-24", "BEV-COLA-12"): 0.55,
    ("BEV-WTER-06", "BEV-WTER-12"): 0.50,
    ("BEV-WTER-12", "BEV-WTER-06"): 0.45,
    ("NUT-PIST-08", "NUT-PIST-16"): 0.40,   # size-down switch
    ("NUT-PIST-16", "NUT-PIST-32"): 0.25,   # cross-size minimal
}

# Own-price elasticities per SKU (β₁ in log-log regression)
OWN_ELASTICITIES: dict[str, float] = {
    "NUT-PIST-08": -2.20,
    "NUT-PIST-16": -2.10,
    "NUT-PIST-32": -1.80,
    "NUT-ALMD-08": -1.90,
    "NUT-ALMD-16": -1.70,
    "NUT-ALMD-32": -1.50,
    "NUT-MIXD-08": -1.95,
    "NUT-MIXD-16": -1.85,
    "NUT-MIXD-32": -1.60,
    "BEV-COLA-12": -2.40,
    "BEV-COLA-24": -2.20,
    "BEV-WTER-06": -2.50,
    "BEV-WTER-12": -2.30,
    "BEV-JUIC-32": -1.60,
    "BEV-JUIC-64": -1.40,
}

# Base weekly units sold (at regular price, average week)
BASE_UNITS: dict[str, float] = {
    "NUT-PIST-08": 600,
    "NUT-PIST-16": 3000,
    "NUT-PIST-32": 800,
    "NUT-ALMD-08": 700,
    "NUT-ALMD-16": 2800,
    "NUT-ALMD-32": 600,
    "NUT-MIXD-08": 500,
    "NUT-MIXD-16": 1800,
    "NUT-MIXD-32": 400,
    "BEV-COLA-12": 1600,
    "BEV-COLA-24": 1100,
    "BEV-WTER-06": 1800,
    "BEV-WTER-12": 1300,
    "BEV-JUIC-32": 900,
    "BEV-JUIC-64": 600,
}

# ── Seasonality multipliers per week-of-year ──────────────────────────────────

def _week_seasonality(sku_id: str, week: int, year: int) -> float:
    """Return seasonal demand multiplier for a given SKU and calendar week."""
    p = PRODUCTS_BY_ID[sku_id]
    peaks = p["peak_seasons"]
    base = 1.0

    # Nuts — Diwali (week 43–45 typically), Christmas (week 51–52), Lunar NY (week 4)
    if sku_id.startswith("NUT"):
        if week in range(43, 47):  # Diwali window
            if "diwali" in peaks: base *= 3.0
            else: base *= 1.2
        elif week in range(50, 53):  # Christmas
            if "christmas" in peaks: base *= 2.5
            else: base *= 1.3
        elif week in range(1, 6):   # Lunar New Year / New Year
            if "lunar_new_year" in peaks: base *= 1.8
            else: base *= 1.1
        elif week in range(7, 9):   # Valentine's
            if "valentines" in peaks: base *= 1.6
        elif week in range(19, 21): # Mother's Day
            if "mothers_day" in peaks: base *= 1.5
        elif week in range(2, 4):   # January dip
            base *= 0.75
        elif week in range(14, 19): # Spring mid
            base *= 0.90

    # Beverages — summer peak, holiday spike
    if sku_id.startswith("BEV"):
        if week in range(23, 36):  # Summer (Jun–Aug)
            if "summer" in peaks: base *= 1.8
            else: base *= 1.1
        elif week in range(27, 29):  # Independence Day
            if "independence_day" in peaks: base *= 2.0
        elif week in range(50, 53):  # Year-end parties
            base *= 1.3
        elif week in range(1, 8):   # Winter low for cold beverages
            if "summer" in peaks: base *= 0.65

    # Add some noise
    base *= (1 + np.random.normal(0, 0.05))
    return max(0.4, base)

PRODUCTS_BY_ID = {p["sku_id"]: p for p in PRODUCTS}


def _generate_stores() -> pd.DataFrame:
    regions = {"NE": ["New York", "Boston", "Philadelphia", "Providence"],
               "SE": ["Miami", "Atlanta", "Charlotte", "Orlando"],
               "MW": ["Chicago", "Detroit", "Minneapolis", "Cleveland"],
               "W":  ["Los Angeles", "Seattle", "Denver", "Phoenix"]}
    states  = {"New York": "NY", "Boston": "MA", "Philadelphia": "PA", "Providence": "RI",
               "Miami": "FL", "Atlanta": "GA", "Charlotte": "NC", "Orlando": "FL",
               "Chicago": "IL", "Detroit": "MI", "Minneapolis": "MN", "Cleveland": "OH",
               "Los Angeles": "CA", "Seattle": "WA", "Denver": "CO", "Phoenix": "AZ"}
    rows = []
    sid = 1
    for region, cities in regions.items():
        for city in cities:
            tiers = ["large", "medium", "small", "medium"]
            footfalls = [9500, 6000, 3500, 5200]
            for tier, ff in zip(tiers, footfalls):
                rows.append({
                    "store_id":            f"S{sid:03d}",
                    "store_name":          f"{city} {tier.title()} #{sid}",
                    "channel":             "physical",
                    "region":              region,
                    "state":               states[city],
                    "city":                city,
                    "size_tier":           tier,
                    "avg_weekly_footfall": ff + random.randint(-500, 500),
                })
                sid += 1
    # Add an online store
    rows.append({
        "store_id": "S099", "store_name": "Online Store",
        "channel": "online", "region": "ALL",
        "state": "", "city": "", "size_tier": "online",
        "avg_weekly_footfall": 0,
    })
    return pd.DataFrame(rows[:25] + [rows[-1]])  # 25 physical + 1 online


def _generate_sales(stores_df: pd.DataFrame) -> pd.DataFrame:
    """Generate 104 weeks of weekly sales per SKU per store."""
    rows = []
    all_weeks = pd.date_range(START_DATE.isoformat(), END_DATE.isoformat(), freq="W-MON")

    for _, store_row in stores_df.iterrows():
        store_id = store_row["store_id"]
        region_factor = {"NE": 1.1, "SE": 0.95, "MW": 1.0, "W": 1.05, "ALL": 2.0}.get(
            store_row["region"], 1.0
        )
        size_factor = {"large": 1.4, "medium": 1.0, "small": 0.65, "online": 1.8}.get(
            store_row["size_tier"], 1.0
        )

        for sku in PRODUCTS:
            sku_id = sku["sku_id"]
            base = BASE_UNITS[sku_id]

            for week_start in all_weeks:
                week_no = week_start.isocalendar().week
                year    = week_start.year
                seas    = _week_seasonality(sku_id, week_no, year)

                units = base * region_factor * size_factor * seas
                units = max(0, int(units + np.random.normal(0, units * 0.08)))

                rows.append({
                    "date":        week_start.date(),
                    "week_number": week_no,
                    "year":        year,
                    "sku_id":      sku_id,
                    "store_id":    store_id,
                    "units_sold":  units,
                    "revenue":     round(units * sku["regular_price"], 2),
                    "price_paid":  sku["regular_price"],
                    "discount_pct": 0.0,
                    "is_promo":    False,
                    "promo_id":    None,
                    "channel":     store_row["channel"],
                })

    return pd.DataFrame(rows)


def _generate_promotions(sales_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate 60 historical promotions and apply them to the sales data.
    Returns (promotions_df, updated_sales_df).
    """
    promo_rows = []
    all_weeks = sorted(sales_df["date"].unique())

    discount_levels = [0.10, 0.15, 0.20, 0.25, 0.30]
    promo_types     = ["TPR", "TPR", "TPR", "Bundle", "Clearance"]
    funding_types   = ["self_funded", "self_funded", "vendor_funded", "co_op"]

    promo_count = 0
    for sku in PRODUCTS:
        sku_id = sku["sku_id"]
        elasticity = OWN_ELASTICITIES[sku_id]
        n_promos = random.randint(3, 5)  # 3–5 promos per SKU over 2 years

        for _ in range(n_promos):
            if promo_count >= 60:
                break
            discount  = random.choice(discount_levels)
            start_idx = random.randint(2, len(all_weeks) - 3)
            start_dt  = pd.Timestamp(all_weeks[start_idx])
            end_dt    = start_dt + pd.Timedelta(weeks=random.randint(1, 2))

            promo_id  = f"P{promo_count+1:04d}"
            promo_rows.append({
                "promo_id":       promo_id,
                "sku_id":         sku_id,
                "start_date":     start_dt.date(),
                "end_date":       end_dt.date(),
                "discount_pct":   discount,
                "promo_type":     random.choice(promo_types),
                "promo_mechanism":"percent_off",
                "display_flag":   random.random() > 0.5,
                "feature_flag":   random.random() > 0.6,
                "digital_flag":   random.random() > 0.7,
                "funding_type":   random.choice(funding_types),
            })

            # Apply lift to matching sales rows
            promo_price = round(sku["regular_price"] * (1 - discount), 2)
            raw_lift    = abs(elasticity) * discount * 0.92   # diminishing returns factor
            lift        = min(raw_lift, 0.80)                 # cap at 80%

            mask = (
                (sales_df["sku_id"] == sku_id)
                & (pd.to_datetime(sales_df["date"]) >= start_dt)
                & (pd.to_datetime(sales_df["date"]) <= pd.Timestamp(end_dt.date()))
            )
            sales_df.loc[mask, "discount_pct"] = discount
            sales_df.loc[mask, "price_paid"]   = promo_price
            sales_df.loc[mask, "is_promo"]     = True
            sales_df.loc[mask, "promo_id"]     = promo_id
            sales_df.loc[mask, "units_sold"]   = (
                sales_df.loc[mask, "units_sold"] * (1 + lift)
            ).round(0)
            sales_df.loc[mask, "revenue"] = (
                sales_df.loc[mask, "units_sold"] * promo_price
            ).round(2)

            # Apply cannibalization to related SKUs in same period
            for (src, dst), cross_e in CROSS_ELASTICITIES.items():
                if src == sku_id:
                    cannibal_mask = (
                        (sales_df["sku_id"] == dst)
                        & (pd.to_datetime(sales_df["date"]) >= start_dt)
                        & (pd.to_datetime(sales_df["date"]) <= pd.Timestamp(end_dt.date()))
                    )
                    cannibal_drop = discount * cross_e * 0.85
                    sales_df.loc[cannibal_mask, "units_sold"] = (
                        sales_df.loc[cannibal_mask, "units_sold"] * (1 - cannibal_drop)
                    ).round(0)
                    dst_price = PRODUCTS_BY_ID[dst]["regular_price"]
                    sales_df.loc[cannibal_mask, "revenue"] = (
                        sales_df.loc[cannibal_mask, "units_sold"] * dst_price
                    ).round(2)

            promo_count += 1

    return pd.DataFrame(promo_rows), sales_df


def _generate_competitor_events() -> pd.DataFrame:
    """Synthetic competitor promo events."""
    competitors = ["RetailCo", "NutsPlus", "HealthMart", "BulkBarn"]
    categories  = ["Nuts", "Beverages"]
    rows = []
    for _ in range(40):
        dt = START_DATE + timedelta(days=random.randint(0, 710))
        rows.append({
            "date":                    dt,
            "competitor_name":         random.choice(competitors),
            "category":                random.choice(categories),
            "product_description":     "Mixed Nuts 16oz BOGO" if random.random() > 0.5 else "Craft Soda 24pk 25% off",
            "estimated_discount_pct":  round(random.uniform(0.15, 0.35), 2),
            "promo_type":              random.choice(["BOGO", "TPR", "Bundle"]),
            "source":                  "synthetic",
            "impact_on_own_sales":     round(-random.uniform(0.03, 0.12), 3),
        })
    return pd.DataFrame(rows)


def _generate_seasonality_index(stores_df: pd.DataFrame) -> pd.DataFrame:
    """Pre-compute seasonality index per SKU × week_of_year."""
    rows = []
    for sku in PRODUCTS:
        sku_id = sku["sku_id"]
        for week in range(1, 54):
            # Average over multiple samples + years to get stable index
            mults = [_week_seasonality(sku_id, week, year) for year in [2024, 2025, 2026] for _ in range(3)]
            avg   = float(np.mean(mults))
            conf  = max(0.5, 1.0 - float(np.std(mults)) / max(avg, 0.01))
            rows.append({"sku_id": sku_id, "week_of_year": week, "seasonality_multiplier": round(avg, 4), "confidence": round(conf, 3)})
    return pd.DataFrame(rows)


def _generate_customer_segments(stores_df: pd.DataFrame) -> pd.DataFrame:
    """3 segments per store."""
    segments = [
        ("price_sensitive", 0.45, -2.8, 1.8, 0.75),
        ("loyalist",        0.35, -1.5, 1.2, 0.25),
        ("occasional",      0.20, -2.0, 1.4, 0.50),
    ]
    rows = []
    for _, store in stores_df.iterrows():
        for seg_name, share, elas, promo_resp, cannibal in segments:
            rows.append({
                "store_id":                       store["store_id"],
                "segment_name":                   seg_name,
                "segment_share_pct":              share + round(random.uniform(-0.05, 0.05), 3),
                "price_elasticity":               elas + round(random.uniform(-0.2, 0.2), 3),
                "promo_response_multiplier":      promo_resp + round(random.uniform(-0.1, 0.1), 3),
                "cannibalization_susceptibility": cannibal + round(random.uniform(-0.05, 0.05), 3),
            })
    return pd.DataFrame(rows)


def _generate_calendar_events() -> pd.DataFrame:
    """Build CalendarEvents from hardcoded NRF events + holidays package."""
    try:
        import holidays as hols
        us_hols_2024 = hols.US(years=2024)
        us_hols_2025 = hols.US(years=2025)
        us_hols_2026 = hols.US(years=2026)
        all_us = {**us_hols_2024, **us_hols_2025, **us_hols_2026}
    except ImportError:
        all_us = {}

    retail_events = [
        (date(2024, 11, 29), "Black Friday",      "retail_event", 5, json.dumps(["all"])),
        (date(2024, 12, 2),  "Cyber Monday",      "retail_event", 4, json.dumps(["all"])),
        (date(2024, 11, 1),  "Diwali",            "cultural",     5, json.dumps(["nuts","gifts"])),
        (date(2024, 12, 25), "Christmas",         "holiday",      5, json.dumps(["all"])),
        (date(2024, 2, 14),  "Valentines Day",    "retail_event", 3, json.dumps(["premium","gifts"])),
        (date(2024, 5, 12),  "Mothers Day",       "retail_event", 3, json.dumps(["premium","gifts"])),
        (date(2024, 9, 2),   "Back to School",    "retail_event", 3, json.dumps(["snacks","beverages"])),
        (date(2025, 11, 28), "Black Friday",      "retail_event", 5, json.dumps(["all"])),
        (date(2025, 12, 1),  "Cyber Monday",      "retail_event", 4, json.dumps(["all"])),
        (date(2025, 11, 1),  "Diwali",            "cultural",     5, json.dumps(["nuts","gifts"])),
        (date(2025, 12, 25), "Christmas",         "holiday",      5, json.dumps(["all"])),
        (date(2025, 2, 14),  "Valentines Day",    "retail_event", 3, json.dumps(["premium","gifts"])),
        (date(2025, 5, 11),  "Mothers Day",       "retail_event", 3, json.dumps(["premium","gifts"])),
        (date(2025, 1, 29),  "Lunar New Year",    "cultural",     4, json.dumps(["nuts","gifts"])),
        (date(2024, 2, 10),  "Lunar New Year",    "cultural",     4, json.dumps(["nuts","gifts"])),
        (date(2024, 7, 4),   "Independence Day",  "holiday",      3, json.dumps(["beverages","snacks"])),
        (date(2025, 7, 4),   "Independence Day",  "holiday",      3, json.dumps(["beverages","snacks"])),
    ]

    rows = [{"date": dt, "event_name": en, "event_type": et, "intensity": i, "relevant_categories": rc}
            for dt, en, et, i, rc in retail_events]

    for dt, name in all_us.items():
        if START_DATE <= dt <= END_DATE:
            rows.append({"date": dt, "event_name": name, "event_type": "holiday",
                         "intensity": 3, "relevant_categories": json.dumps(["all"])})

    return pd.DataFrame(rows).drop_duplicates(subset=["date", "event_name"])


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_all() -> dict[str, pd.DataFrame]:
    """Generate all synthetic datasets and save to CSV files."""
    print("Generating synthetic data...")

    # 1. Products
    products_df = pd.DataFrame(PRODUCTS)
    products_df["margin_pct"] = ((products_df["regular_price"] - products_df["cost_price"])
                                  / products_df["regular_price"] * 100).round(1)
    products_df["peak_seasons"] = products_df["peak_seasons"].apply(json.dumps)
    print(f"  Products: {len(products_df)} SKUs")

    # 2. Stores
    stores_df = _generate_stores()
    print(f"  Stores: {len(stores_df)}")

    # 3. Sales (before promos)
    print("  Generating sales (this takes ~30s)...")
    sales_df = _generate_sales(stores_df)

    # 4. Promotions (apply to sales in-place)
    promos_df, sales_df = _generate_promotions(sales_df)
    print(f"  Promotions: {len(promos_df)}")
    print(f"  Sales rows: {len(sales_df):,}")

    # 5. Competitor events
    competitor_df = _generate_competitor_events()
    print(f"  Competitor events: {len(competitor_df)}")

    # 6. Seasonality index
    seas_df = _generate_seasonality_index(stores_df)
    print(f"  Seasonality index: {len(seas_df)}")

    # 7. Customer segments
    segments_df = _generate_customer_segments(stores_df)
    print(f"  Customer segments: {len(segments_df)}")

    # 8. Calendar events
    calendar_df = _generate_calendar_events()
    print(f"  Calendar events: {len(calendar_df)}")

    # Save CSVs
    datasets = {
        "products":          products_df,
        "stores":            stores_df,
        "sales":             sales_df,
        "promotions":        promos_df,
        "competitor_events": competitor_df,
        "seasonality_index": seas_df,
        "customer_segments": segments_df,
        "calendar_events":   calendar_df,
    }
    for name, df in datasets.items():
        path = SYNTHETIC_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  Saved → {path}")

    print("Synthetic data generation complete.")
    return datasets


if __name__ == "__main__":
    generate_all()
