"""
data/seed_data.py
─────────────────
Load synthetic CSV files (or generate them first) into the SQLite database.
Safe to call on every app startup — skips if data already loaded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from config.settings import SYNTHETIC_DIR
from data.database import (
    CalendarEvent, CompetitorEvent, CustomerSegment, Product,
    Promotion, Sale, SeasonalityIndex, Store, WeatherIndex,
    create_tables, migrate_tables, get_session,
)

_SYNTH = Path(SYNTHETIC_DIR)


def _csv(name: str) -> Path:
    return _SYNTH / f"{name}.csv"


def _already_seeded(session: Session) -> bool:
    """Quick check — if products table has rows we've already seeded."""
    try:
        return session.query(Product).count() > 0
    except Exception:
        return False


def _load_products(session: Session, df: pd.DataFrame):
    records = df.to_dict("records")
    for r in records:
        p = Product(
            sku_id=r["sku_id"],
            product_name=r["product_name"],
            category=r["category"],
            subcategory=r["subcategory"],
            brand=r.get("brand"),
            size=r.get("size"),
            size_unit=r.get("size_unit"),
            regular_price=float(r["regular_price"]),
            cost_price=float(r["cost_price"]),
            margin_pct=float(r.get("margin_pct", 0)),
            is_seasonal=bool(r.get("is_seasonal", False)),
            peak_seasons=str(r.get("peak_seasons", "[]")),
        )
        session.merge(p)
    session.commit()
    logger.info(f"Loaded {len(records)} products")


def _load_stores(session: Session, df: pd.DataFrame):
    # Prepare records for bulk insert
    records = []
    for _, r in df.iterrows():
        records.append({
            "store_id": r["store_id"],
            "store_name": r["store_name"],
            "channel": r["channel"],
            "region": r["region"],
            "state": str(r.get("state", "")),
            "city": str(r.get("city", "")),
            "size_tier": r["size_tier"],
            "avg_weekly_footfall": int(r.get("avg_weekly_footfall", 0)),
        })
    # Use bulk_insert_mappings for ~10x speed improvement
    session.bulk_insert_mappings(Store, records, render_nulls=True)
    session.commit()
    logger.info(f"Loaded {len(df)} stores")


def _load_promotions(session: Session, df: pd.DataFrame):
    # Convert dates and prepare records for bulk insert
    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.date
    # Fill defaults
    df["promo_type"] = df.get("promo_type", "TPR").fillna("TPR")
    df["promo_mechanism"] = df.get("promo_mechanism", "percent_off").fillna("percent_off")
    df["display_flag"] = df.get("display_flag", False).fillna(False).astype(bool)
    df["feature_flag"] = df.get("feature_flag", False).fillna(False).astype(bool)
    df["digital_flag"] = df.get("digital_flag", False).fillna(False).astype(bool)
    df["funding_type"] = df.get("funding_type", "self_funded").fillna("self_funded")
    session.bulk_insert_mappings(Promotion, df.to_dict("records"), render_nulls=True)
    session.commit()
    logger.info(f"Loaded {len(df)} promotions")


def _load_sales(session: Session, df: pd.DataFrame, chunk_size: int = 5000):
    df = df.copy()
    df["date"]       = pd.to_datetime(df["date"]).dt.date
    df["is_promo"]   = df["is_promo"].astype(bool)
    df["promo_id"]   = df["promo_id"].where(df["promo_id"].notna(), None)

    total = len(df)
    for i in range(0, total, chunk_size):
        chunk = df.iloc[i : i + chunk_size]
        session.bulk_insert_mappings(Sale, chunk.to_dict("records"))
        session.commit()
        if (i + chunk_size) % 50000 == 0:
            logger.info(f"  Sales loaded: {i+chunk_size:,}/{total:,}")

    logger.info(f"Loaded {total:,} sales rows")


def _load_calendar(session: Session, df: pd.DataFrame):
    # Convert dates and prepare records for bulk insert
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["event_name"] = df.get("event_name", "").fillna("").astype(str)
    df["event_type"] = df.get("event_type", "holiday").fillna("holiday").astype(str)
    df["intensity"] = df.get("intensity", 3).fillna(3).astype(int)
    df["relevant_categories"] = df.get("relevant_categories", '["all"]').fillna('["all"]').astype(str)
    session.bulk_insert_mappings(CalendarEvent, df.to_dict("records"), render_nulls=True)
    session.commit()
    logger.info(f"Loaded {len(df)} calendar events")


def _load_seasonality(session: Session, df: pd.DataFrame):
    session.bulk_insert_mappings(SeasonalityIndex, df.to_dict("records"))
    session.commit()
    logger.info(f"Loaded {len(df)} seasonality index rows")


def _load_competitor_events(session: Session, df: pd.DataFrame):
    # Convert dates and prepare records for bulk insert
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["competitor_name"] = df.get("competitor_name", "").fillna("").astype(str)
    df["category"] = df.get("category", "").fillna("").astype(str)
    df["product_description"] = df.get("product_description", "").fillna("").astype(str)
    df["estimated_discount_pct"] = df.get("estimated_discount_pct", 0).fillna(0).astype(float)
    df["promo_type"] = df.get("promo_type", "TPR").fillna("TPR").astype(str)
    df["source"] = df.get("source", "synthetic").fillna("synthetic").astype(str)
    df["impact_on_own_sales"] = df.get("impact_on_own_sales", 0).fillna(0).astype(float)
    session.bulk_insert_mappings(CompetitorEvent, df.to_dict("records"), render_nulls=True)
    session.commit()
    logger.info(f"Loaded {len(df)} competitor events")


def _load_segments(session: Session, df: pd.DataFrame):
    records = df.to_dict("records")
    # Ensure gender_female_pct column is present (backward-compatible)
    for r in records:
        r.setdefault("gender_female_pct", None)
    session.bulk_insert_mappings(CustomerSegment, records)
    session.commit()
    logger.info(f"Loaded {len(df)} customer segment rows")


def _load_weather_index(session: Session, df: pd.DataFrame):
    session.bulk_insert_mappings(WeatherIndex, df.to_dict("records"))
    session.commit()
    logger.info(f"Loaded {len(df)} weather index rows")


def seed_database(force: bool = False):
    """
    Seed the database from synthetic CSVs.
    Generates synthetic data if CSVs do not exist yet.
    """
    migrate_tables()   # creates new tables + adds new columns to existing tables
    session = get_session()

    if not force and _already_seeded(session):
        logger.info("Database already seeded — skipping.")
        session.close()
        return

    # Generate data if CSVs are missing
    if not _csv("products").exists():
        logger.info("Synthetic CSVs not found — generating now...")
        from data.synthetic_generator import generate_all
        generate_all()

    logger.info("Seeding database from synthetic CSVs...")

    _load_products(session, pd.read_csv(_csv("products")))
    _load_stores(session, pd.read_csv(_csv("stores")))
    _load_promotions(session, pd.read_csv(_csv("promotions")))
    _load_sales(session, pd.read_csv(_csv("sales")))
    _load_calendar(session, pd.read_csv(_csv("calendar_events")))
    _load_seasonality(session, pd.read_csv(_csv("seasonality_index")))
    _load_competitor_events(session, pd.read_csv(_csv("competitor_events")))
    _load_segments(session, pd.read_csv(_csv("customer_segments")))
    if _csv("weather_index").exists():
        _load_weather_index(session, pd.read_csv(_csv("weather_index")))

    session.close()
    logger.info("Database seeding complete.")


if __name__ == "__main__":
    seed_database(force=True)
