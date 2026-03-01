"""
data/load_dunnhumby.py
──────────────────────
Ingests the dunnhumby retail dataset into the Price Sense AI database.

Supports two dataset flavours — whichever is present in data/zip/:

  1. dunnhumby – The Complete Journey (128 MB zip, ~2500 households, 92K products)
     Source: https://www.dunnhumby.com/source-files/
     File  : data/zip/dunnhumby_The-Complete-Journey.zip
     Strategy: full load, aggregate daily → weekly per product+store.
               Use top TOP_N_PRODUCTS by transaction volume.

  2. dunnhumby – Let's Get Sort of Real (9 × ~480 MB zips, 2006–2011)
     Source: https://www.dunnhumby.com/source-files/
     Files : data/zip/dunnhumby_Let's-Get-Sort-of-Real-(Full-Part-N-of-9).zip
     Strategy: streaming sample from each monthly file without extracting to disk.
               Uses first SAMPLE_ROWS_PER_FILE rows per monthly transaction file.

Run standalone:
    python data/load_dunnhumby.py [--force]

    --force  : drop and reload even if .dunnhumby_loaded sentinel exists

Called automatically by Docker entrypoint when data/zip/ contains zips.

Output:
  • Populates/extends the SQLite database (data/pricesense.db)
  • Writes data/.dunnhumby_loaded sentinel file when done
  • Does NOT overwrite existing synthetic data — starts fresh if called with --force
"""

from __future__ import annotations

import json
import random as _rnd
import sys
import uuid
import zipfile
from datetime import date, timedelta
from pathlib import Path

# ── Ensure repo root is on sys.path when script is run directly ───────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
import requests
from loguru import logger

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

ZIP_DIR      = Path(__file__).resolve().parent / "zip"
SENTINEL     = Path(__file__).resolve().parent / ".dunnhumby_loaded"

# Complete Journey settings
CJ_ZIP       = ZIP_DIR / "dunnhumby_The-Complete-Journey.zip"
CJ_PREFIX    = "dunnhumby_The-Complete-Journey/dunnhumby_The-Complete-Journey CSV/"
TOP_N_PRODUCTS   = 200     # limit to N most-purchased products
TOP_N_STORES     = 50      # limit to N busiest stores

# Let's Get Sort of Real settings
LGSR_SAMPLE_ROWS = 30_000  # rows to sample from each monthly file
LGSR_TOP_PRODUCTS = 150
LGSR_TOP_STORES   = 40

# Reference dates — week 1 of each dataset maps to 2024-01-01 for consistency
WEEK1_DATE   = date(2024, 1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _week_to_date(week_no: int, base: date = WEEK1_DATE) -> date:
    """Convert 1-based week number to a Monday date."""
    return base + timedelta(weeks=int(week_no) - 1)


def _week_to_shopdate(shop_date_int: int) -> date:
    """Convert LGSR YYYYMMDD integer to date."""
    s = str(int(shop_date_int))
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _remap_date_to_2024(d: date) -> date:
    """Shift any date into the 2024-01-01 → 2025-12-28 window."""
    # Use year and week-of-year, reassign to 2024/2025
    iso = d.isocalendar()
    target_year = 2024 + (iso.week // 53)
    try:
        return date.fromisocalendar(target_year, iso.week, iso.weekday)
    except ValueError:
        return date(target_year, 1, 1)


def _clean_str(s) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip().title()


# ─────────────────────────────────────────────────────────────────────────────
# Shared enrichment helpers (calendar, weather, competitor events, gender)
# ─────────────────────────────────────────────────────────────────────────────

def _populate_calendar_events(session, start_year: int = 2024, end_year: int = 2025):
    """
    Populate CalendarEvent table using the `holidays` Python package +
    a hardcoded NRF retail event calendar.

    The `holidays` package is already in requirements.txt (holidays==0.57.*).
    This gives us proper holiday labels to annotate the seasonal patterns
    that are embedded in the dunnhumby sales data.
    """
    from data.database import CalendarEvent

    try:
        import holidays as hols
        us = {}
        uk = {}
        for yr in range(start_year, end_year + 1):
            us.update(hols.US(years=yr))
            uk.update(hols.country_holidays("GB", years=yr))
    except ImportError:
        logger.warning("holidays package not found — skipping US/UK public holiday labels")
        us, uk = {}, {}

    # ── NRF / retail calendar (hardcoded, applies 2024–2025) ─────────────────
    retail_calendar = [
        # (date, name, type, intensity 1-5, relevant_categories JSON)
        (date(2024, 11, 29), "Black Friday",     "retail_event", 5, '["all"]'),
        (date(2024, 12,  2), "Cyber Monday",     "retail_event", 4, '["all"]'),
        (date(2024, 11,  1), "Diwali",           "cultural",     5, '["nuts","gifts","sweets"]'),
        (date(2024, 12, 25), "Christmas Day",    "holiday",      5, '["all"]'),
        (date(2024,  2, 14), "Valentines Day",   "retail_event", 3, '["premium","gifts","chocolate"]'),
        (date(2024,  5, 12), "Mothers Day",      "retail_event", 3, '["premium","gifts","flowers"]'),
        (date(2024,  9,  2), "Back to School",   "retail_event", 3, '["snacks","beverages"]'),
        (date(2024,  7,  4), "Independence Day", "holiday",      3, '["beverages","bbq","snacks"]'),
        (date(2024,  2, 10), "Lunar New Year",   "cultural",     4, '["nuts","gifts"]'),
        (date(2024, 11, 28), "Thanksgiving",     "holiday",      4, '["grocery","beverages"]'),
        (date(2024,  4, 10), "Easter",           "holiday",      3, '["grocery","sweets"]'),
        (date(2025, 11, 28), "Black Friday",     "retail_event", 5, '["all"]'),
        (date(2025, 12,  1), "Cyber Monday",     "retail_event", 4, '["all"]'),
        (date(2025, 11,  1), "Diwali",           "cultural",     5, '["nuts","gifts","sweets"]'),
        (date(2025, 12, 25), "Christmas Day",    "holiday",      5, '["all"]'),
        (date(2025,  2, 14), "Valentines Day",   "retail_event", 3, '["premium","gifts","chocolate"]'),
        (date(2025,  5, 11), "Mothers Day",      "retail_event", 3, '["premium","gifts","flowers"]'),
        (date(2025,  1, 29), "Lunar New Year",   "cultural",     4, '["nuts","gifts"]'),
        (date(2025,  7,  4), "Independence Day", "holiday",      3, '["beverages","bbq","snacks"]'),
        (date(2025, 11, 27), "Thanksgiving",     "holiday",      4, '["grocery","beverages"]'),
        (date(2025,  4, 20), "Easter",           "holiday",      3, '["grocery","sweets"]'),
    ]

    inserted = 0
    seen: set = set()

    # retail calendar first (takes priority)
    for dt, name, etype, intensity, cats in retail_calendar:
        key = (dt, name)
        if key not in seen:
            session.merge(CalendarEvent(
                date=dt, event_name=name, event_type=etype,
                intensity=intensity, relevant_categories=cats,
            ))
            seen.add(key)
            inserted += 1

    # US public holidays
    for dt, name in us.items():
        key = (dt, name)
        if key not in seen:
            session.merge(CalendarEvent(
                date=dt, event_name=name, event_type="holiday",
                intensity=3, relevant_categories='["all"]',
            ))
            seen.add(key)
            inserted += 1

    # UK public holidays (for LGSR which is UK data)
    for dt, name in uk.items():
        key = (dt, name + " (UK)")
        if key not in seen:
            session.merge(CalendarEvent(
                date=dt, event_name=name + " (UK)", event_type="holiday",
                intensity=3, relevant_categories='["all"]',
            ))
            seen.add(key)
            inserted += 1

    session.commit()
    logger.success(f"  {inserted} calendar events inserted (US holidays + UK public holidays + NRF retail calendar)")


def _populate_competitor_events(session, categories: list[str], start_year: int = 2024, end_year: int = 2025):
    """
    Generate synthetic competitor promotional events.
    ~4–6 events per category per year — enough to calibrate competitive price pressure.
    Uses the same approach as synthetic_generator.py but keyed to the real category list.
    """
    from data.database import CompetitorEvent

    competitors = {
        "Grocery":    ["FreshMart", "ValueKing", "MegaGrocer"],
        "Nuts":       ["NutHouse", "Whole & Natural", "SnackDepot"],
        "Beverages":  ["DrinkCo", "BeverageWorld", "SodaKing"],
        "Dairy":      ["DairyFarm", "FreshDairy"],
        "Bakery":     ["BakeFresh", "CrustMart"],
        "Produce":    ["GreenGrocer", "FreshFarm"],
        "Frozen":     ["FrostBite", "IcedGoods"],
        "Snacks":     ["SnackWorld", "MunchCo"],
        "Meat":       ["MeatMart", "ButcherBox"],
        "default":    ["CompetitorA", "CompetitorB", "RetailCo"],
    }
    promo_types = ["TPR", "BOGO", "Bundle", "Clearance", "Feature Ad"]

    all_dates: list[date] = []
    for yr in range(start_year, end_year + 1):
        d = date(yr, 1, 1)
        while d.year == yr:
            all_dates.append(d)
            d += timedelta(days=7)

    inserted = 0
    for cat in (categories or ["Grocery"]):
        comp_pool = competitors.get(cat, competitors["default"])
        # ~5 events per category per year
        n_events = (end_year - start_year + 1) * 5
        sampled_dates = _rnd.sample(all_dates, min(n_events, len(all_dates)))
        for dt in sampled_dates:
            disc = round(_rnd.uniform(0.10, 0.35), 2)
            session.merge(CompetitorEvent(
                date=dt,
                competitor_name=_rnd.choice(comp_pool),
                category=cat,
                product_description=f"{cat} promotional event",
                estimated_discount_pct=disc,
                promo_type=_rnd.choice(promo_types),
                source="synthetic",
                impact_on_own_sales=round(-disc * _rnd.uniform(0.3, 0.6), 3),
            ))
            inserted += 1

    session.commit()
    logger.success(f"  {inserted} competitor events generated across {len(categories)} categories")


def _populate_weather_index(session, regions: list[str], use_api: bool = True):
    """
    Populate WeatherIndex table with monthly avg temperature and a demand multiplier.

    Strategy:
      1. Try Open-Meteo free API (no key required) using representative
         lat/lon for each region — one call per region (12 months).
      2. Fall back to hardcoded synthetic values if API unavailable.

    Demand index logic: hot months ↑ beverages, cold months ↑ nuts/soups.
    """
    from data.database import WeatherIndex

    # Representative coordinates per region (used for Open-Meteo API)
    REGION_COORDS = {
        "NE":  (40.71, -74.01),   # New York
        "SE":  (33.75, -84.39),   # Atlanta
        "MW":  (41.88, -87.63),   # Chicago
        "W":   (34.05, -118.24),  # Los Angeles
        "SW":  (33.45, -112.07),  # Phoenix
        "ALL": (39.95, -75.17),   # Philadelphia (online store placeholder)
        "UK":  (51.51, -0.13),    # London (for LGSR)
        "Unknown": (39.95, -75.17),
    }

    # Synthetic fallback: avg monthly temps °F per region
    SYNTHETIC_TEMPS = {
        "NE":  [32, 35, 44, 55, 65, 75, 80, 78, 70, 58, 47, 36],
        "SE":  [52, 56, 63, 72, 79, 85, 88, 87, 82, 72, 62, 53],
        "MW":  [26, 30, 42, 55, 65, 75, 79, 77, 69, 57, 43, 30],
        "W":   [58, 60, 62, 65, 68, 73, 78, 79, 76, 70, 63, 57],
        "SW":  [54, 58, 64, 72, 81, 91, 95, 93, 87, 75, 62, 54],
        "ALL": [38, 41, 50, 61, 70, 78, 82, 80, 73, 62, 51, 40],
        "UK":  [40, 41, 45, 50, 56, 62, 65, 65, 59, 52, 45, 41],
        "Unknown": [50, 52, 58, 65, 72, 78, 82, 80, 74, 64, 55, 48],
    }

    def _demand_index(temp_f: float) -> float:
        """Simple heuristic: cold → +demand (comfort food), hot → neutral."""
        if temp_f < 35:    return 1.20   # very cold — soups, nuts, hot beverages
        elif temp_f < 50:  return 1.10
        elif temp_f < 65:  return 1.00   # baseline
        elif temp_f < 78:  return 0.97
        else:               return 0.93  # very hot — impulse ice / cold beverages spike handled in seasonality

    def _precip(region: str, month: int) -> float:
        """Synthetic monthly precipitation (inches)."""
        base = {"NE": 3.8, "SE": 4.5, "MW": 3.2, "W": 1.5, "SW": 0.7, "UK": 2.2}.get(region, 3.0)
        seasonal = [1.1, 1.0, 1.1, 1.2, 1.3, 1.1, 1.2, 1.1, 1.0, 0.9, 0.9, 1.1][month - 1]
        return round(base * seasonal, 2)

    inserted = 0
    for region in set(regions):
        lat, lon = REGION_COORDS.get(region, REGION_COORDS["ALL"])
        monthly_temps: list[float] = []

        if use_api:
            try:
                url = (
                    "https://archive-api.open-meteo.com/v1/archive"
                    f"?latitude={lat}&longitude={lon}"
                    "&start_date=2024-01-01&end_date=2024-12-31"
                    "&monthly=temperature_2m_mean"
                    "&temperature_unit=fahrenheit&timezone=auto"
                )
                resp = requests.get(url, timeout=8)
                if resp.ok:
                    monthly_temps = resp.json().get("monthly", {}).get("temperature_2m_mean", [])
                    logger.info(f"  Open-Meteo: {region} → {len(monthly_temps)} monthly temps fetched")
            except Exception as exc:
                logger.warning(f"  Open-Meteo API failed for {region}: {exc} — using synthetic fallback")

        if len(monthly_temps) < 12:
            monthly_temps = SYNTHETIC_TEMPS.get(region, SYNTHETIC_TEMPS["ALL"])

        for month_idx, temp in enumerate(monthly_temps[:12], start=1):
            session.merge(WeatherIndex(
                region=region,
                month=month_idx,
                avg_temp_f=round(float(temp), 1),
                precipitation_in=_precip(region, month_idx),
                weather_demand_index=round(_demand_index(float(temp)), 3),
            ))
            inserted += 1

    session.commit()
    logger.success(f"  {inserted} weather index rows inserted ({len(set(regions))} regions)")


def _extract_gender_female_pct(hh_demo_df: pd.DataFrame) -> float:
    """
    Estimate female household shopper % from dunnhumby hh_demographic.csv.

    The Complete Journey demographic file has:
      HH_COMP_DESC — "1 Adult", "1 Adult Kids", "2 Adults", "2 Adults Kids", "Unknown"
      MARITAL_STATUS_CODE — "A" (single), "B" (married/partnered), "U" (unknown)
      There is no direct GENDER column.

    Heuristic: single-adult households in Complete Journey skew ~55% female
    (consistent with US grocery shopper research). Two-adult households are
    treated as 50/50. We compute a weighted average.
    """
    if hh_demo_df.empty:
        return 52.0  # national US grocery shopper average

    hh_col = "HH_COMP_DESC" if "HH_COMP_DESC" in hh_demo_df.columns else None
    if not hh_col:
        return 52.0

    female_weights = {
        "1 adult":       0.58,   # single-adult hh skew female
        "1 adult kids":  0.62,   # single parent skew female
        "2 adults":      0.50,
        "2 adults kids": 0.50,
        "unknown":       0.52,
    }

    total, weighted = 0, 0.0
    for _, r in hh_demo_df.iterrows():
        desc = str(r[hh_col]).lower().strip()
        w = next((v for k, v in female_weights.items() if k in desc), 0.52)
        weighted += w
        total += 1

    return round((weighted / max(total, 1)) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Complete Journey loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_complete_journey(session) -> bool:
    """Load from The Complete Journey zip. Returns True on success."""
    if not CJ_ZIP.exists():
        logger.info("Complete Journey zip not found — skipping.")
        return False

    logger.info(f"Loading The Complete Journey from {CJ_ZIP} …")

    from data.database import (
        CalendarEvent, CompetitorEvent, CustomerSegment, Product, Promotion,
        Sale, SeasonalityIndex, Store, WeatherIndex,
    )

    with zipfile.ZipFile(str(CJ_ZIP)) as zf:
        names = {n.split("/")[-1]: n for n in zf.namelist() if n.endswith(".csv")}

        # ── Products ──────────────────────────────────────────────────────────
        logger.info("  Reading product.csv …")
        with zf.open(names.get("product.csv", "")) as f:
            prod_df = pd.read_csv(f)

        # ── Transactions ──────────────────────────────────────────────────────
        logger.info("  Reading transaction_data.csv …")
        with zf.open(names.get("transaction_data.csv", "")) as f:
            tx_df = pd.read_csv(f)
        logger.info(f"  {len(tx_df):,} transaction rows loaded")

        # ── Causal (promo flags) ───────────────────────────────────────────────
        causal_df = pd.DataFrame()
        if "causal_data.csv" in names:
            logger.info("  Reading causal_data.csv …")
            with zf.open(names["causal_data.csv"]) as f:
                causal_df = pd.read_csv(f)

        # ── Campaigns (promotions) ─────────────────────────────────────────────
        camp_desc_df = pd.DataFrame()
        if "campaign_desc.csv" in names:
            with zf.open(names["campaign_desc.csv"]) as f:
                camp_desc_df = pd.read_csv(f)

        hh_demo_df = pd.DataFrame()
        if "hh_demographic.csv" in names:
            with zf.open(names["hh_demographic.csv"]) as f:
                hh_demo_df = pd.read_csv(f)

    # ── Identify top products by transaction count ─────────────────────────
    col_product  = "PRODUCT_ID" if "PRODUCT_ID" in tx_df.columns else "PRODUCT_NUM"
    col_store    = "STORE_ID"
    col_week     = "WEEK_NO"
    col_qty      = "QUANTITY"
    col_sales    = "SALES_VALUE"
    col_disc     = "RETAIL_DISC"

    top_products = (
        tx_df.groupby(col_product)[col_qty].sum()
        .nlargest(TOP_N_PRODUCTS).index.tolist()
    )
    top_stores = (
        tx_df.groupby(col_store)[col_sales].sum()
        .nlargest(TOP_N_STORES).index.tolist()
    )

    tx_filt = tx_df[
        tx_df[col_product].isin(top_products) &
        tx_df[col_store].isin(top_stores)
    ].copy()
    logger.info(f"  Filtered to {len(tx_filt):,} rows ({len(top_products)} products × {len(top_stores)} stores)")

    # ── Compute regular price per product (median non-discounted price) ──────
    non_promo = tx_filt[tx_filt[col_disc] == 0].copy()
    non_promo["unit_price"] = non_promo[col_sales] / non_promo[col_qty].clip(lower=1)
    reg_price_map = (
        non_promo.groupby(col_product)["unit_price"].median()
        .to_dict()
    )
    # fallback: use global median per product
    all_unit = tx_filt.copy()
    all_unit["unit_price"] = all_unit[col_sales] / all_unit[col_qty].clip(lower=1)
    fallback_price = all_unit.groupby(col_product)["unit_price"].median().to_dict()
    for pid in top_products:
        if pid not in reg_price_map or reg_price_map[pid] <= 0:
            reg_price_map[pid] = fallback_price.get(pid, 3.99)

    # Merge product metadata
    prod_map: dict = {}
    if col_product in prod_df.columns:
        prod_col_name = "PRODUCT_ID" if "PRODUCT_ID" in prod_df.columns else "PRODUCT_NUM"
        for _, r in prod_df.iterrows():
            pid = r[prod_col_name]
            if pid in top_products:
                prod_map[pid] = r

    # ── Insert products ────────────────────────────────────────────────────────
    logger.info("  Inserting products …")
    for pid in top_products:
        pinfo     = prod_map.get(pid, {})
        dept      = _clean_str(pinfo.get("DEPARTMENT", "Grocery"))
        brand_raw = pinfo.get("BRAND", "National")
        brand     = "National" if pd.isna(brand_raw) else str(brand_raw).title()
        commodity = _clean_str(pinfo.get("COMMODITY_DESC", "Product"))
        sub_comm  = _clean_str(pinfo.get("SUB_COMMODITY_DESC", ""))
        size_raw  = str(pinfo.get("CURR_SIZE_OF_PRODUCT", ""))
        reg_p     = round(float(reg_price_map.get(pid, 3.99)), 2)

        pname = f"{commodity} {size_raw}".strip() if size_raw else commodity
        sku   = f"DH-{pid}"
        p = Product(
            sku_id=sku,
            product_name=pname[:120],
            category=dept[:60],
            subcategory=sub_comm[:60] or commodity[:60],
            brand=brand[:60],
            size=None,
            size_unit=None,
            regular_price=reg_p,
            cost_price=round(reg_p * 0.58, 2),
            margin_pct=round((1 - 0.58) * 100, 1),
            is_seasonal=False,
            peak_seasons="[]",
        )
        session.merge(p)
    session.commit()
    logger.success(f"  {len(top_products)} products inserted")

    # ── Insert stores ──────────────────────────────────────────────────────────
    logger.info("  Inserting stores …")
    _REGIONS = ["NE", "SE", "MW", "W", "SW"]
    _SIZES   = ["large", "medium", "small"]
    _FOOTFALL = {"large": 8500, "medium": 4200, "small": 1800}
    for i, sid in enumerate(top_stores):
        region   = _REGIONS[i % len(_REGIONS)]
        size_t   = _SIZES[i % len(_SIZES)]
        s = Store(
            store_id=f"STR-{sid}",
            store_name=f"Store {sid} {size_t.title()}",
            channel="physical",
            region=region,
            state="",
            city=f"City {sid}",
            size_tier=size_t,
            avg_weekly_footfall=_FOOTFALL[size_t],
        )
        session.merge(s)
    # Add online store
    session.merge(Store(
        store_id="STR-ONLINE",
        store_name="Online Store",
        channel="online",
        region="ALL",
        state="",
        city="",
        size_tier="large",
        avg_weekly_footfall=0,
    ))
    session.commit()
    logger.success(f"  {len(top_stores) + 1} stores inserted")

    # ── Build causal promo flags per (product, store, week) ───────────────────
    promo_flag_set: set = set()
    if not causal_df.empty:
        causal_col_prod = "PRODUCT_NUM" if "PRODUCT_NUM" in causal_df.columns else "PRODUCT_ID"
        # display/mailer can be '0', '1', 'A', 'B' etc. — treat any non-zero as promotional
        def _is_promo_col(series: pd.Series) -> pd.Series:
            s = series.astype(str).str.strip()
            return s.isin(["1", "A", "B", "Y", "X"]) | (pd.to_numeric(s, errors="coerce").fillna(0) > 0)

        disp_col = "display" if "display" in causal_df.columns else None
        mail_col = "mailer"  if "mailer"  in causal_df.columns else None

        promo_mask = pd.Series(False, index=causal_df.index)
        if disp_col:
            promo_mask |= _is_promo_col(causal_df[disp_col])
        if mail_col:
            promo_mask |= _is_promo_col(causal_df[mail_col])

        causal_filtered = causal_df[
            causal_df[causal_col_prod].isin(top_products) & promo_mask
        ]
        for _, r in causal_filtered.iterrows():
            promo_flag_set.add((r[causal_col_prod], r.get("STORE_ID", r.get("store_id", 0)), r.get("WEEK_NO", 0)))

    # ── Aggregate transactions → weekly sales ──────────────────────────────────
    logger.info("  Aggregating to weekly sales …")
    tx_filt["sku_id"]    = "DH-" + tx_filt[col_product].astype(str)
    tx_filt["store_id"]  = "STR-" + tx_filt[col_store].astype(str)
    tx_filt["week_no"]   = tx_filt[col_week]
    tx_filt["is_promo_disc"] = tx_filt[col_disc].abs() > 0.01
    tx_filt["is_promo_caus"] = tx_filt.apply(
        lambda r: (r[col_product], r[col_store], r[col_week]) in promo_flag_set, axis=1
    )
    tx_filt["is_promo_any"] = tx_filt["is_promo_disc"] | tx_filt["is_promo_caus"]

    weekly = (
        tx_filt
        .groupby(["sku_id", "store_id", "week_no"])
        .agg(
            units_sold=("QUANTITY",    "sum"),
            revenue   =(col_sales,     "sum"),
            disc_sum  =(col_disc,      "sum"),
            is_promo  =("is_promo_any","max"),
        )
        .reset_index()
    )
    weekly["price_paid"]   = (weekly["revenue"] / weekly["units_sold"].clip(lower=1)).round(4)
    weekly["discount_pct"] = ((-weekly["disc_sum"]) / (weekly["revenue"] - weekly["disc_sum"]).clip(lower=0.01)).clip(0, 0.6).round(4)
    weekly["date"]         = weekly["week_no"].apply(lambda w: _week_to_date(int(w)))
    weekly["year"]         = weekly["date"].apply(lambda d: d.year)
    weekly["week_number"]  = weekly["date"].apply(lambda d: d.isocalendar().week)
    weekly["channel"]      = "physical"
    weekly["promo_id"]     = None
    logger.info(f"  {len(weekly):,} weekly sale rows to insert")

    # ── Insert sales in chunks ─────────────────────────────────────────────────
    logger.info("  Inserting sales …")
    chunk_size = 5000
    from data.database import Sale as SaleModel
    for i in range(0, len(weekly), chunk_size):
        chunk = weekly.iloc[i : i + chunk_size]
        session.bulk_insert_mappings(SaleModel, [
            dict(
                date=r["date"],
                week_number=int(r["week_number"]),
                year=int(r["year"]),
                sku_id=r["sku_id"],
                store_id=r["store_id"],
                units_sold=float(r["units_sold"]),
                revenue=float(r["revenue"]),
                price_paid=float(r["price_paid"]),
                discount_pct=float(r["discount_pct"]),
                is_promo=bool(r["is_promo"]),
                promo_id=None,
                channel=r["channel"],
            )
            for _, r in chunk.iterrows()
        ])
        session.commit()
        if (i // chunk_size) % 10 == 0:
            logger.info(f"    … {i:,}/{len(weekly):,} rows")
    logger.success(f"  {len(weekly):,} sale rows inserted")

    # ── Insert promotions from campaign data ───────────────────────────────────
    if not camp_desc_df.empty:
        logger.info("  Inserting campaign promotions …")
        promo_types = {"A": "TPR", "B": "Bundle", "C": "Clearance", "T": "TPR"}
        week_min   = tx_filt["week_no"].min()
        for _, c in camp_desc_df.iterrows():
            start_wk = int(c.get("START_DAY", c.get("start_wk", 1)))
            end_wk   = int(c.get("END_DAY", c.get("end_wk", start_wk)))
            ctype    = str(c.get("CAMPAIGN_TYPE", c.get("campaign_type", "A"))).strip().upper()[:1]
            # Each campaign applies to multiple products — create one promo per product per campaign
            for pid in top_products[:20]:   # cap to avoid thousands of promos
                session.merge(Promotion(
                    promo_id=f"DH-CAMP-{c.get('CAMPAIGN','X')}-{pid}",
                    sku_id=f"DH-{pid}",
                    start_date=_week_to_date(max(1, start_wk - week_min + 1)),
                    end_date=_week_to_date(max(1, end_wk - week_min + 2)),
                    discount_pct=0.15,
                    promo_type=promo_types.get(ctype, "TPR"),
                    promo_mechanism="percent_off",
                    display_flag=(ctype in ("A", "B")),
                    feature_flag=(ctype == "A"),
                    digital_flag=False,
                    funding_type="vendor_funded",
                ))
        session.commit()
        logger.success(f"  Campaign promotions inserted")

    # ── Customer segments from household demographics ──────────────────────────
    if not hh_demo_df.empty and not weekly.empty:
        logger.info("  Generating customer segments from hh_demographic …")
        income_col = "INCOME_DESC" if "INCOME_DESC" in hh_demo_df.columns else None
        if income_col:
            low_income_frac = (hh_demo_df[income_col].str.contains("Under|Low", case=False, na=False)).mean()
        else:
            low_income_frac = 0.35

        # ── Gender from hh_demographic.csv ────────────────────────────────────
        # dunnhumby Complete Journey has HH_COMP_DESC (household composition)
        # and MARITAL_STATUS_CODE but NO direct GENDER column.
        # We derive a female-shopper % using household composition heuristics
        # (single-parent HH skew female per US grocery shopper research).
        global_female_pct = _extract_gender_female_pct(hh_demo_df)
        logger.info(f"  Estimated female shopper % from hh_demographic: {global_female_pct:.1f}%")

        for store_id in [f"STR-{s}" for s in top_stores[:20]]:
            # Vary segment mix slightly per store using store id hash
            h = hash(store_id) % 100
            price_sensitive_pct = round(30 + low_income_frac * 25 + (h % 20) - 10, 1)
            loyalist_pct        = round(40 + (h % 20) - 10, 1)
            occasional_pct      = max(5.0, round(100 - price_sensitive_pct - loyalist_pct, 1))
            # Gender split varies slightly per segment:
            # price_sensitive shoppers skew slightly more female (US research)
            segs = [
                ("price_sensitive", price_sensitive_pct, -2.8, 1.35, 0.55, min(100, global_female_pct + 3)),
                ("loyalist",        loyalist_pct,        -1.2, 0.85, 0.2,  global_female_pct),
                ("occasional",      occasional_pct,      -1.9, 1.15, 0.35, max(0, global_female_pct - 2)),
            ]
            for seg_name, share, elast, resp, cann, fem_pct in segs:
                session.merge(CustomerSegment(
                    store_id=store_id,
                    segment_name=seg_name,
                    segment_share_pct=share,
                    price_elasticity=elast,
                    promo_response_multiplier=resp,
                    cannibalization_susceptibility=cann,
                    gender_female_pct=round(fem_pct, 1),
                ))
        session.commit()
        logger.success("  Customer segments inserted (with gender_female_pct from hh_demographic)")

    # ── Seasonality index ─────────────────────────────────────────────────────
    logger.info("  Computing seasonality index …")
    weekly_agg = (
        weekly.groupby(["sku_id", "week_number"])["units_sold"].mean().reset_index()
    )
    for sku_id in weekly_agg["sku_id"].unique()[:TOP_N_PRODUCTS]:
        sku_data = weekly_agg[weekly_agg["sku_id"] == sku_id]
        mean_vol = sku_data["units_sold"].mean()
        if mean_vol <= 0:
            continue
        for _, r in sku_data.iterrows():
            session.merge(SeasonalityIndex(
                sku_id=sku_id,
                week_of_year=int(r["week_number"]),
                seasonality_multiplier=round(float(r["units_sold"]) / mean_vol, 4),
                confidence=0.8,
            ))
    session.commit()
    logger.success("  Seasonality index inserted")

    # ── Calendar events (holidays package + NRF retail calendar) ──────────────
    logger.info("  Populating calendar events …")
    _populate_calendar_events(session, start_year=2024, end_year=2025)

    # ── Competitor events (synthetic for each product category) ───────────────
    logger.info("  Populating competitor events …")
    categories = list({
        prod_map.get(pid, {}).get("DEPARTMENT", "Grocery") or "Grocery"
        for pid in top_products
    })
    _populate_competitor_events(session, categories=[str(c) for c in categories if c])

    # ── Weather index (Open-Meteo API or synthetic fallback) ──────────────────
    logger.info("  Populating weather index …")
    regions = list({_REGIONS[i % len(_REGIONS)] for i in range(len(top_stores))}) + ["ALL"]
    _populate_weather_index(session, regions=regions)

    logger.success("Complete Journey load finished.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Let's Get Sort of Real loader (streaming sample from 9 zip parts)
# ─────────────────────────────────────────────────────────────────────────────

def _load_lgsr(session) -> bool:
    """Load a sampled subset from the 9-part Let's Get Sort of Real dataset."""
    parts = sorted(ZIP_DIR.glob("*Get-Sort-of-Real*.zip"))
    if not parts:
        logger.info("Let's Get Sort of Real parts not found — skipping.")
        return False

    logger.info(f"Found {len(parts)} Let's Get Sort of Real zip parts. Streaming sample …")

    from data.database import (
        CalendarEvent, CompetitorEvent, CustomerSegment, Product,
        Sale as SaleModel, SeasonalityIndex, Store, WeatherIndex,
    )

    all_tx_chunks: list[pd.DataFrame] = []

    for part in parts:
        logger.info(f"  Sampling {part.name} …")
        try:
            with zipfile.ZipFile(str(part)) as zf:
                csv_files = [n for n in zf.namelist() if n.endswith(".csv") and "transactions" in n]
                # Sample first 2 monthly files per part
                for csv_name in csv_files[:2]:
                    with zf.open(csv_name) as f:
                        try:
                            chunk = pd.read_csv(f, nrows=LGSR_SAMPLE_ROWS, on_bad_lines="skip")
                            all_tx_chunks.append(chunk)
                            logger.info(f"    {csv_name.split('/')[-1]}: {len(chunk):,} rows")
                        except Exception as e:
                            logger.warning(f"    Could not read {csv_name}: {e}")
        except Exception as e:
            logger.warning(f"  Could not open {part.name}: {e}")
            continue

    if not all_tx_chunks:
        logger.warning("No LGSR transaction data could be read.")
        return False

    # Concatenate all sampled rows
    tx_df = pd.concat(all_tx_chunks, ignore_index=True)
    logger.info(f"Total LGSR sampled rows: {len(tx_df):,}")

    # ── Identify columns ───────────────────────────────────────────────────────
    # Expected: SHOP_WEEK, SHOP_DATE, QUANTITY, SPEND, PROD_CODE, PROD_CODE_30, PROD_CODE_40,
    #           STORE_CODE, STORE_FORMAT, STORE_REGION, CUST_CODE, CUST_PRICE_SENSITIVITY, etc.
    col_prod   = "PROD_CODE"    if "PROD_CODE"   in tx_df.columns else None
    col_store  = "STORE_CODE"   if "STORE_CODE"  in tx_df.columns else None
    col_date   = "SHOP_DATE"    if "SHOP_DATE"   in tx_df.columns else None
    col_week   = "SHOP_WEEK"    if "SHOP_WEEK"   in tx_df.columns else None
    col_qty    = "QUANTITY"     if "QUANTITY"    in tx_df.columns else None
    col_spend  = "SPEND"        if "SPEND"       in tx_df.columns else None
    col_dept   = "PROD_CODE_40" if "PROD_CODE_40" in tx_df.columns else None
    col_subcat = "PROD_CODE_30" if "PROD_CODE_30" in tx_df.columns else None
    col_region = "STORE_REGION" if "STORE_REGION" in tx_df.columns else None
    col_format = "STORE_FORMAT" if "STORE_FORMAT" in tx_df.columns else None
    col_pricesens = "CUST_PRICE_SENSITIVITY" if "CUST_PRICE_SENSITIVITY" in tx_df.columns else None

    if not all([col_prod, col_store, col_date, col_qty, col_spend]):
        logger.error(f"LGSR columns missing. Found: {list(tx_df.columns)}")
        return False

    # ── Top products & stores ──────────────────────────────────────────────────
    top_products = tx_df.groupby(col_prod)[col_qty].sum().nlargest(LGSR_TOP_PRODUCTS).index.tolist()
    top_stores   = tx_df.groupby(col_store)[col_spend].sum().nlargest(LGSR_TOP_STORES).index.tolist()

    tx_df = tx_df[
        tx_df[col_prod].isin(top_products) &
        tx_df[col_store].isin(top_stores)
    ].copy()

    # ── Convert SHOP_DATE (YYYYMMDD) to actual date, remap to 2024 range ──────
    tx_df["real_date"]    = tx_df[col_date].apply(lambda d: _week_to_shopdate(int(d)))
    tx_df["mapped_date"]  = tx_df["real_date"].apply(_remap_date_to_2024)
    tx_df["week_number"]  = tx_df["mapped_date"].apply(lambda d: d.isocalendar().week)
    tx_df["year"]         = tx_df["mapped_date"].apply(lambda d: d.year)

    # ── Compute approx regular price per product ───────────────────────────────
    all_unit             = tx_df.copy()
    all_unit["unit_price"] = all_unit[col_spend] / all_unit[col_qty].clip(lower=1)
    reg_price_map        = all_unit.groupby(col_prod)["unit_price"].median().to_dict()

    # ── Insert products ────────────────────────────────────────────────────────
    logger.info("  Inserting LGSR products …")
    for pid in top_products:
        rows   = tx_df[tx_df[col_prod] == pid]
        dept   = _clean_str(rows[col_dept].iloc[0])  if col_dept  and not rows.empty else "Grocery"
        subcat = _clean_str(rows[col_subcat].iloc[0]) if col_subcat and not rows.empty else dept
        reg_p  = round(float(reg_price_map.get(pid, 2.99)), 2)

        session.merge(Product(
            sku_id=f"LGSR-{pid}",
            product_name=f"{dept} {subcat}".strip()[:120] or str(pid),
            category=dept[:60] or "Grocery",
            subcategory=subcat[:60] or dept[:60],
            brand="Various",
            size=None,
            size_unit=None,
            regular_price=reg_p,
            cost_price=round(reg_p * 0.60, 2),
            margin_pct=40.0,
            is_seasonal=False,
            peak_seasons="[]",
        ))
    session.commit()
    logger.success(f"  {len(top_products)} LGSR products inserted")

    # ── Insert stores ──────────────────────────────────────────────────────────
    logger.info("  Inserting LGSR stores …")
    for sid in top_stores:
        rows    = tx_df[tx_df[col_store] == sid]
        region  = _clean_str(rows[col_region].iloc[0]) if col_region and not rows.empty else "Unknown"
        fmt     = _clean_str(rows[col_format].iloc[0]) if col_format and not rows.empty else "Standard"
        size_t  = "large" if "large" in fmt.lower() else ("small" if "express" in fmt.lower() else "medium")
        session.merge(Store(
            store_id=f"LGSR-{sid}",
            store_name=f"{fmt} Store {sid}",
            channel="physical",
            region=region[:10] or "UK",
            state="",
            city="",
            size_tier=size_t,
            avg_weekly_footfall={"large": 9000, "medium": 4000, "small": 1500}[size_t],
        ))
    session.commit()
    logger.success(f"  {len(top_stores)} LGSR stores inserted")

    # ── Aggregate to weekly per product+store ─────────────────────────────────
    logger.info("  Aggregating sampled LGSR data to weekly …")
    tx_df["sku_id"]   = "LGSR-" + tx_df[col_prod].astype(str)
    tx_df["store_id"] = "LGSR-" + tx_df[col_store].astype(str)

    weekly = (
        tx_df.groupby(["sku_id", "store_id", "mapped_date", "week_number", "year"])
        .agg(units_sold=(col_qty, "sum"), revenue=(col_spend, "sum"))
        .reset_index()
    )
    weekly["price_paid"]   = (weekly["revenue"] / weekly["units_sold"].clip(lower=1)).round(4)
    weekly["discount_pct"] = 0.0
    weekly["is_promo"]     = False
    weekly["channel"]      = "physical"

    logger.info(f"  {len(weekly):,} LGSR weekly rows to insert")

    for i in range(0, len(weekly), 5000):
        chunk = weekly.iloc[i : i + 5000]
        session.bulk_insert_mappings(SaleModel, [
            dict(
                date=r["mapped_date"],
                week_number=int(r["week_number"]),
                year=int(r["year"]),
                sku_id=r["sku_id"],
                store_id=r["store_id"],
                units_sold=float(r["units_sold"]),
                revenue=float(r["revenue"]),
                price_paid=float(r["price_paid"]),
                discount_pct=0.0,
                is_promo=False,
                promo_id=None,
                channel="physical",
            )
            for _, r in chunk.iterrows()
        ])
        session.commit()

    logger.success(f"  {len(weekly):,} LGSR sale rows inserted")

    # ── LGSR Seasonality index (from actual weekly sales ratios) ──────────────
    logger.info("  Computing LGSR seasonality index …")
    lgsr_weekly_agg = (
        weekly.groupby(["sku_id", "week_number"])["units_sold"].mean().reset_index()
    )
    for sku_id in lgsr_weekly_agg["sku_id"].unique()[:LGSR_TOP_PRODUCTS]:
        sku_data = lgsr_weekly_agg[lgsr_weekly_agg["sku_id"] == sku_id]
        mean_vol = sku_data["units_sold"].mean()
        if mean_vol <= 0:
            continue
        for _, r in sku_data.iterrows():
            session.merge(SeasonalityIndex(
                sku_id=sku_id,
                week_of_year=int(r["week_number"]),
                seasonality_multiplier=round(float(r["units_sold"]) / mean_vol, 4),
                confidence=0.7,  # slightly lower confidence — sampled data
            ))
    session.commit()
    logger.success("  LGSR seasonality index inserted")

    # ── Segments ───────────────────────────────────────────────────────────────
    if col_pricesens and not tx_df.empty:
        logger.info("  Generating LGSR customer segments …")
        # LGSR has CUST_PRICE_SENSITIVITY but no gender column.
        # UK grocery research: ~54% female shoppers (Kantar 2023).
        UK_FEMALE_PCT = 54.0
        for sid in top_stores[:20]:
            store_rows = tx_df[tx_df[col_store] == sid]
            ps_frac = (store_rows[col_pricesens].str.contains("Low|UM", case=False, na=False)).mean() if not store_rows.empty else 0.35
            session.merge(CustomerSegment(store_id=f"LGSR-{sid}", segment_name="price_sensitive",
                segment_share_pct=round(ps_frac * 100, 1), price_elasticity=-2.8,
                promo_response_multiplier=1.35, cannibalization_susceptibility=0.55,
                gender_female_pct=round(UK_FEMALE_PCT + 3, 1)))
            session.merge(CustomerSegment(store_id=f"LGSR-{sid}", segment_name="loyalist",
                segment_share_pct=round(40.0, 1), price_elasticity=-1.2,
                promo_response_multiplier=0.85, cannibalization_susceptibility=0.2,
                gender_female_pct=UK_FEMALE_PCT))
            session.merge(CustomerSegment(store_id=f"LGSR-{sid}", segment_name="occasional",
                segment_share_pct=round(max(5, 100 - ps_frac * 100 - 40), 1), price_elasticity=-1.9,
                promo_response_multiplier=1.15, cannibalization_susceptibility=0.35,
                gender_female_pct=round(UK_FEMALE_PCT - 2, 1)))
        session.commit()
        logger.success("  LGSR customer segments inserted (with UK gender_female_pct)")

    # ── LGSR product categories for competitor events ─────────────────────────
    lgsr_cats: list[str] = []
    if col_dept and not tx_df.empty:
        lgsr_cats = [str(c).title() for c in tx_df[col_dept].dropna().unique().tolist()[:15]]
    if not lgsr_cats:
        lgsr_cats = ["Grocery", "Beverages", "Snacks", "Dairy", "Bakery"]

    # ── Calendar events ───────────────────────────────────────────────────────
    logger.info("  Populating calendar events (UK + US holidays + retail calendar) …")
    _populate_calendar_events(session, start_year=2024, end_year=2025)

    # ── Competitor events ─────────────────────────────────────────────────────
    logger.info("  Populating competitor events …")
    _populate_competitor_events(session, categories=lgsr_cats)

    # ── Weather index (UK region from Open-Meteo or synthetic) ────────────────
    logger.info("  Populating weather index …")
    lgsr_regions = ["UK"] + list({
        str(tx_df[col_region].iloc[i]).strip().upper()[:10]
        for i in range(min(len(tx_df), 1000))
        if col_region and not pd.isna(tx_df[col_region].iloc[i])
    })
    _populate_weather_index(session, regions=[r for r in lgsr_regions if r])

    logger.success("Let's Get Sort of Real load finished.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def load_dunnhumby(force: bool = False):
    """
    Main entry point. Checks for zip files and loads whichever is available.

    Priority: Complete Journey > Let's Get Sort of Real
    """
    if SENTINEL.exists() and not force:
        logger.info("Dunnhumby data already loaded (.dunnhumby_loaded sentinel found). Pass --force to reload.")
        return

    # Check if any zip is available at all
    cj_available   = CJ_ZIP.exists()
    lgsr_available = bool(list(ZIP_DIR.glob("*Get-Sort-of-Real*.zip")))

    if not cj_available and not lgsr_available:
        logger.info("No dunnhumby zip files found in data/zip/ — using synthetic data only.")
        return

    from data.database import create_tables, migrate_tables, get_session
    migrate_tables()   # creates new tables + adds new columns to existing tables
    session = get_session()

    try:
        loaded = False

        if cj_available:
            logger.info("Using The Complete Journey dataset (priority 1)")
            loaded = _load_complete_journey(session)

        if not loaded and lgsr_available:
            logger.info("Using Let's Get Sort of Real dataset (priority 2)")
            loaded = _load_lgsr(session)

        if loaded:
            SENTINEL.write_text("loaded\n")
            logger.success("Dunnhumby ingestion complete. Sentinel written.")
        else:
            logger.warning("No dunnhumby data was successfully loaded.")

    except Exception as exc:
        logger.exception(f"Dunnhumby load failed: {exc}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        SENTINEL.unlink(missing_ok=True)
        logger.info("Force mode — removing sentinel and reloading …")

    load_dunnhumby(force=force)
