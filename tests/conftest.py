"""
tests/conftest.py
─────────────────
Shared pytest fixtures for all test modules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta


@pytest.fixture
def sample_sales_df():
    """Generate a sample sales DataFrame for testing."""
    n_rows = 200
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n_rows, freq="W")
    prices = rng.uniform(8.0, 14.0, n_rows)
    units = 100 * (prices / 10.0) ** (-2.0) * rng.lognormal(0, 0.05, n_rows)
    is_promo = rng.random(n_rows) < 0.2
    week_numbers = [d.isocalendar().week for d in dates]
    years = [d.year for d in dates]
    
    return pd.DataFrame({
        "date":       dates,
        "sku_id":     "TEST-SKU-001",
        "price_paid": prices,
        "units_sold": units,
        "is_promo":   is_promo,
        "store_id":   "STORE-001",
        "week_number": week_numbers,
        "year":       years,
    })


@pytest.fixture
def sample_products_df():
    """Generate a sample products DataFrame for testing."""
    return pd.DataFrame([
        {
            "sku_id": "TEST-SKU-001",
            "product_name": "Test Product 1",
            "category": "TestCategory",
            "subcategory": "TestSub",
            "regular_price": 10.0,
            "cost_price": 6.0,
            "margin_pct": 40.0,
        },
        {
            "sku_id": "TEST-SKU-002",
            "product_name": "Test Product 2",
            "category": "TestCategory",
            "subcategory": "TestSub",
            "regular_price": 12.0,
            "cost_price": 7.5,
            "margin_pct": 37.5,
        },
    ])


@pytest.fixture
def sample_stores_df():
    """Generate a sample stores DataFrame for testing."""
    return pd.DataFrame([
        {
            "store_id": "STORE-001",
            "store_name": "Test Store 1",
            "channel": "physical",
            "region": "NE",
            "state": "NY",
            "city": "New York",
            "size_tier": "large",
            "avg_weekly_footfall": 5000,
        },
        {
            "store_id": "STORE-002",
            "store_name": "Test Store 2",
            "channel": "online",
            "region": "W",
            "state": "CA",
            "city": "San Francisco",
            "size_tier": "medium",
            "avg_weekly_footfall": 0,
        },
    ])


@pytest.fixture
def sample_promotions_df():
    """Generate a sample promotions DataFrame for testing."""
    return pd.DataFrame([
        {
            "promo_id": "PROMO-001",
            "sku_id": "TEST-SKU-001",
            "start_date": date(2024, 3, 1),
            "end_date": date(2024, 3, 7),
            "discount_pct": 0.20,
            "promo_type": "TPR",
        },
        {
            "promo_id": "PROMO-002",
            "sku_id": "TEST-SKU-002",
            "start_date": date(2024, 4, 1),
            "end_date": date(2024, 4, 7),
            "discount_pct": 0.25,
            "promo_type": "TPR",
        },
    ])


@pytest.fixture
def test_db_session():
    """Create a test database session (in-memory SQLite)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from data.database import Base
    
    # Create in-memory SQLite database for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    
    yield session
    
    session.close()
