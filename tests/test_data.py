"""
tests/test_data.py
──────────────────
Unit tests for data layer (database, seed_data, synthetic_generator).
Run with:  pytest tests/test_data.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

import pytest
import pandas as pd


class TestDatabase:
    """Test database schema and operations."""
    
    def test_tables_exist(self):
        """Ensure all required tables are created."""
        from data.database import engine, create_tables
        from sqlalchemy import inspect
        
        create_tables()
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        required_tables = [
            "products", "stores", "sales", "promotions",
            "calendar_events", "seasonality_index",
            "customer_segments", "weather_index", "users"
        ]
        
        for table in required_tables:
            assert table in table_names, f"Missing table: {table}"
    
    def test_get_session_returns_session(self):
        """Test session factory works."""
        from data.database import get_session
        from sqlalchemy.orm import Session
        
        session = get_session()
        assert isinstance(session, Session)
        session.close()
    
    def test_migrate_tables_runs_without_error(self):
        """Test migration function runs successfully."""
        from data.database import migrate_tables
        # Should not raise
        migrate_tables()


class TestSeedData:
    """Test data seeding operations."""
    
    def test_seed_database_idempotent(self):
        """Test that seed_database can be called multiple times safely."""
        from data.seed_data import seed_database
        # Should not raise, even if data already exists
        seed_database(force=False)
    
    def test_products_loaded(self):
        """Ensure products table has data after seeding."""
        from data.database import get_session, Product
        from data.seed_data import seed_database
        
        seed_database(force=False)
        session = get_session()
        count = session.query(Product).count()
        session.close()
        
        assert count > 0, "Products table is empty after seeding"


class TestSyntheticGenerator:
    """Test synthetic data generation."""
    
    def test_synthetic_csvs_exist(self):
        """Check that synthetic CSVs are generated."""
        from config.settings import SYNTHETIC_DIR
        
        expected_files = [
            "products.csv",
            "stores.csv",
            "sales.csv",
            "promotions.csv",
            "calendar_events.csv",
            "seasonality_index.csv",
            "customer_segments.csv",
        ]
        
        for fname in expected_files:
            fpath = SYNTHETIC_DIR / fname
            # Create if doesn't exist (for fresh test env)
            if not fpath.exists():
                from data.synthetic_generator import generate_all
                generate_all()
            
            assert fpath.exists(), f"Missing synthetic file: {fname}"
    
    def test_synthetic_products_readable(self):
        """Ensure products CSV can be loaded."""
        from config.settings import SYNTHETIC_DIR
        
        products_csv = SYNTHETIC_DIR / "products.csv"
        if not products_csv.exists():
            from data.synthetic_generator import generate_all
            generate_all()
        
        df = pd.read_csv(products_csv)
        assert len(df) > 0
        assert "sku_id" in df.columns
        assert "product_name" in df.columns
        assert "category" in df.columns


class TestDataValidation:
    """Test data integrity and validation."""
    
    def test_sales_have_valid_dates(self):
        """Ensure sales records have valid date values."""
        from data.database import get_session, Sale
        
        session = get_session()
        # Sample 100 sales records
        sales = session.query(Sale).limit(100).all()
        session.close()
        
        if sales:
            for sale in sales:
                assert sale.date is not None
                assert sale.units_sold >= 0
                assert sale.sku_id is not None
    
    def test_products_have_positive_prices(self):
        """Ensure products have sensible price values."""
        from data.database import get_session, Product
        
        session = get_session()
        products = session.query(Product).limit(50).all()
        session.close()
        
        if products:
            for prod in products:
                assert prod.regular_price > 0, f"Invalid regular_price for {prod.sku_id}"
                assert prod.cost_price >= 0, f"Invalid cost_price for {prod.sku_id}"
                assert prod.cost_price <= prod.regular_price, f"Cost > price for {prod.sku_id}"
