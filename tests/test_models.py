"""
tests/test_models.py
─────────────────────
Unit tests for all five ML models.
Run with:  pytest tests/test_models.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest
from datetime import date


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_sales_df(n_rows: int = 200, sku_id: str = "NUT-ALMD-16", seed: int = 42):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_rows, freq="W")
    prices = rng.uniform(8.0, 14.0, n_rows)
    # True elasticity ≈ -2.0
    units = 100 * (prices / 10.0) ** (-2.0) * rng.lognormal(0, 0.05, n_rows)
    is_promo = rng.random(n_rows) < 0.2
    return pd.DataFrame({
        "sale_date":  dates,
        "sku_id":     sku_id,
        "actual_price": prices,
        "regular_price": np.full(n_rows, 10.0),
        "units_sold": units,
        "is_promo":   is_promo,
        "store_id":   "STORE-001",
    })


def _make_products_df():
    rows = [
        {"sku_id": "NUT-ALMD-16", "product_name": "Almonds 16oz", "category": "Nuts",
         "regular_price": 10.0, "cost_price": 6.0, "margin_pct": 40.0},
        {"sku_id": "NUT-PIST-16", "product_name": "Pistachios 16oz", "category": "Nuts",
         "regular_price": 12.0, "cost_price": 7.5, "margin_pct": 37.5},
    ]
    return pd.DataFrame(rows)


# ── Elasticity tests ───────────────────────────────────────────────────────────

class TestElasticity:
    def test_result_in_valid_range(self):
        from models.elasticity import estimate_elasticity, ELASTICITY_MIN, ELASTICITY_MAX
        sales = _make_sales_df()
        res = estimate_elasticity(sales, "NUT-ALMD-16")
        assert ELASTICITY_MIN <= res.elasticity <= ELASTICITY_MAX, (
            f"Elasticity {res.elasticity} outside [{ELASTICITY_MIN}, {ELASTICITY_MAX}]"
        )

    def test_r_squared_non_negative(self):
        from models.elasticity import estimate_elasticity
        sales = _make_sales_df()
        res = estimate_elasticity(sales, "NUT-ALMD-16")
        assert res.r_squared >= 0

    def test_volume_lift_capped_at_80(self):
        from models.elasticity import estimate_volume_lift
        # Very high discount should not produce > 80% lift
        lift = estimate_volume_lift(elasticity=-3.5, discount_pct=0.50)
        assert lift <= 0.80, f"Lift {lift:.2%} exceeds 80% cap"

    def test_volume_lift_positive_for_discount(self):
        from models.elasticity import estimate_volume_lift
        lift = estimate_volume_lift(elasticity=-2.0, discount_pct=0.20)
        assert lift > 0, "Discount should produce positive volume lift"

    def test_missing_sku_returns_result(self):
        """Should return a result even for an unknown SKU (fallback)."""
        from models.elasticity import estimate_elasticity
        sales = _make_sales_df()
        res = estimate_elasticity(sales, "UNKNOWN-SKU-99")
        assert res is not None


# ── Cannibalization tests ──────────────────────────────────────────────────────

class TestCannibalization:
    def test_returns_result(self):
        from models.cannibalization import compute_cannibalization
        sales = pd.concat([_make_sales_df(sku_id="NUT-ALMD-16"),
                           _make_sales_df(sku_id="NUT-PIST-16")])
        products = _make_products_df()
        res = compute_cannibalization("NUT-ALMD-16", 0.20, sales, products)
        assert res is not None
        assert res.focal_sku_id == "NUT-ALMD-16"

    def test_total_margin_loss_non_negative(self):
        from models.cannibalization import compute_cannibalization
        sales = pd.concat([_make_sales_df(sku_id="NUT-ALMD-16"),
                           _make_sales_df(sku_id="NUT-PIST-16")])
        products = _make_products_df()
        res = compute_cannibalization("NUT-ALMD-16", 0.20, sales, products)
        assert res.total_margin_loss >= 0


# ── Profit calculator tests ────────────────────────────────────────────────────

class TestProfitCalculator:
    def test_basic_pnl_structure(self):
        from models.profit_calculator import calculate_promo_pnl
        pnl = calculate_promo_pnl(
            sku_id="NUT-ALMD-16",
            product_name="Almonds 16oz",
            regular_price=10.0,
            cost_price=6.0,
            discount_pct=0.20,
            baseline_weekly_units=100.0,
            volume_lift_pct=0.30,
            promo_weeks=4,
        )
        assert pnl.promo_price == pytest.approx(8.0)
        assert pnl.incremental_units > 0
        assert pnl.recommendation_tier in ("RECOMMENDED", "MARGINAL", "NOT_RECOMMENDED")

    def test_deep_discount_hurts_profit(self):
        from models.profit_calculator import calculate_promo_pnl
        pnl_shallow = calculate_promo_pnl(
            sku_id="NUT-ALMD-16",
            product_name="Almonds 16oz",
            regular_price=10.0,
            cost_price=6.0,
            discount_pct=0.10,
            baseline_weekly_units=100.0,
            volume_lift_pct=0.15,
            promo_weeks=2,
        )
        pnl_deep = calculate_promo_pnl(
            sku_id="NUT-ALMD-16",
            product_name="Almonds 16oz",
            regular_price=10.0,
            cost_price=6.0,
            discount_pct=0.45,
            baseline_weekly_units=100.0,
            volume_lift_pct=0.60,
            promo_weeks=2,
        )
        # The net incremental profit should be worse (or the margin lower) for deep discount
        assert pnl_shallow.promo_margin_pct > pnl_deep.promo_margin_pct

    def test_find_optimal_discount(self):
        from models.profit_calculator import find_optimal_discount
        opt = find_optimal_discount(
            sku_id="NUT-ALMD-16",
            product_name="Almonds 16oz",
            regular_price=10.0,
            cost_price=6.0,
            baseline_weekly_units=100.0,
        )
        assert opt is not None
        assert 0.05 <= opt.discount_pct <= 0.40


# ── Risk scorer tests ──────────────────────────────────────────────────────────

class TestRiskScorer:
    def test_score_in_unit_interval(self):
        from models.risk_scorer import score_risk
        sales = _make_sales_df()
        promos = pd.DataFrame({
            "sku_id": ["NUT-ALMD-16"],
            "start_date": ["2024-01-01"],
            "end_date":   ["2024-01-14"],
            "discount_pct": [0.20],
        })
        result = score_risk(
            sku_id="NUT-ALMD-16",
            discount_pct=0.20,
            elasticity_rsq=0.65,
            elasticity_pvalue=0.03,
            n_cannibal_skus=2,
            sales_df=sales,
            promotions_df=promos,
            target_date=date(2025, 3, 1),
            seasonality_index={},
        )
        assert 0.0 <= result.total_score <= 1.0

    def test_band_is_valid(self):
        from models.risk_scorer import score_risk
        sales = _make_sales_df()
        promos = pd.DataFrame(columns=["sku_id", "start_date", "end_date", "discount_pct"])
        result = score_risk(
            sku_id="NUT-ALMD-16",
            discount_pct=0.15,
            elasticity_rsq=0.80,
            elasticity_pvalue=0.01,
            n_cannibal_skus=1,
            sales_df=sales,
            promotions_df=promos,
            target_date=date(2025, 6, 1),
            seasonality_index={},
        )
        assert result.band in ("LOW", "MEDIUM", "HIGH")


# ── Scenario engine smoke test ─────────────────────────────────────────────────

class TestScenarioEngine:
    def test_scenarios_to_dataframe(self):
        """Ensure the dataframe builder works without a live DB."""
        from services.scenario_engine import ScenarioRow, ScenarioComparisonResult, scenarios_to_dataframe

        rows = [
            ScenarioRow(
                discount_pct=0.10,
                discount_label="10%",
                volume_lift_pct=0.15,
                promo_units=115.0,
                promo_revenue=1035.0,
                promo_cost=690.0,
                incremental_profit=35.0,
                net_incremental_profit=35.0,
                roi=0.05,
                recommendation="MARGINAL",
                risk_score=0.4,
                risk_band="MEDIUM",
                is_optimal=True,
            )
        ]
        comparison = ScenarioComparisonResult(
            sku_id="NUT-ALMD-16",
            scenarios=rows,
            optimal_discount=0.10,
            full_results={},
        )
        df = scenarios_to_dataframe(comparison)
        assert not df.empty
        assert "discount_label" in df.columns
