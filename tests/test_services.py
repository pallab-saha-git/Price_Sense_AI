"""
tests/test_services.py
──────────────────────
Unit tests for service layer (promo_analyzer, scenario_engine, insight_generator).
Run with:  pytest tests/test_services.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

import pytest
import pandas as pd
from datetime import date


class TestPromoAnalyzer:
    """Test the main analyzer orchestration."""
    
    def test_invalidate_cache(self):
        """Ensure cache invalidation works."""
        from services.promo_analyzer import _cache, invalidate_cache
        # Invalidate and check it's empty
        invalidate_cache()
        # Access _cache via module (it's global)
        import services.promo_analyzer as pa
        assert pa._cache == {}
    
    def test_load_data_structure(self):
        """Test that _load_data returns expected structure."""
        from services.promo_analyzer import _load_data, invalidate_cache
        invalidate_cache()
        data = _load_data()
        
        # Check all expected keys exist
        required_keys = {"products", "promos", "sales", "calendar", "seas", "stores", "segments"}
        assert required_keys.issubset(data.keys())
        
        # Check all values are DataFrames
        for key, df in data.items():
            assert isinstance(df, pd.DataFrame), f"{key} is not a DataFrame"


class TestInsightGenerator:
    """Test insight generation (templates and AI)."""
    
    def test_template_insights_returns_list(self):
        """Template insights should return a list of strings."""
        from services.insight_generator import generate_template_insights
        from services.promo_analyzer import PromoAnalysisResult
        from models.elasticity import ElasticityResult
        from models.cannibalization import CannibalizationResult
        from models.demand_forecast import ForecastResult
        from models.profit_calculator import PromoPnL
        from models.risk_scorer import RiskResult, RiskFactor
        
        # Create minimal mock result
        mock_result = PromoAnalysisResult(
            sku_id="TEST-SKU",
            discount_pct=0.20,
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 17),
            elasticity=ElasticityResult(
                sku_id="TEST-SKU",
                elasticity=-2.0,
                r_squared=0.65,
                p_value=0.02,
                conf_int_low=-2.5,
                conf_int_high=-1.5,
                n_observations=50,
                is_reliable=True,
            ),
            cannibalization=CannibalizationResult(
                focal_sku_id="TEST-SKU",
                discount_pct=0.20,
                impacts=[],
                total_margin_loss=0.0,
            ),
            forecast=ForecastResult(
                sku_id="TEST-SKU",
                baseline_weekly=100.0,
                forecast_df=pd.DataFrame({"ds": [date(2026, 3, 10)], "yhat": [100.0], "yhat_lower": [90.0], "yhat_upper": [110.0]}),
                mape=5.0,
                seasonality_index={10: 1.0},
                model_used="prophet",
                data_quality="good",
                n_weeks_used=50,
            ),
            pnl=PromoPnL(
                sku_id="TEST-SKU",
                product_name="Test Product",
                regular_price=10.0,
                cost_price=6.0,
                discount_pct=0.20,
                baseline_weekly_units=100.0,
            ),
            risk=RiskResult(
                total_score=0.35,
                band="MEDIUM",
                factors=[
                    RiskFactor("Test factor", 0.25, 0.4, "Test description")
                ],
            ),
            recommendation="RECOMMENDED",
            recommendation_label="RECOMMENDED",
            data_quality="good",
        )
        
        insights = generate_template_insights(mock_result)
        assert isinstance(insights, list)
        assert len(insights) > 0
        assert all(isinstance(i, str) for i in insights)


class TestScenarioEngine:
    """Test scenario comparison optimization."""
    
    def test_scenarios_to_dataframe_structure(self):
        """Ensure scenarios_to_dataframe produces correct columns."""
        from services.scenario_engine import scenarios_to_dataframe, ScenarioRow, ScenarioComparisonResult
        
        rows = [
            ScenarioRow(
                discount_pct=0.10,
                discount_label="10% off",
                lift_pct=15.0,
                lift_units=115.0,
                incremental_revenue=1035.0,
                net_incremental_profit=35.0,
                promo_roi=0.35,
                risk_band="MEDIUM",
                risk_score=0.4,
                cannibalization_cost=10.0,
                recommendation="MARGINAL",
                is_optimal=True,
            )
        ]
        
        comparison = ScenarioComparisonResult(
            sku_id="TEST-SKU",
            product_name="Test Product",
            scenarios=rows,
            optimal_discount=0.10,
            optimal_row=rows[0],
            full_results={},
        )
        
        df = scenarios_to_dataframe(comparison)
        
        # Check expected columns exist
        expected_cols = ["Discount", "Volume Lift", "Net Profit", "ROI", "Risk"]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"
        
        assert len(df) == 1
        assert df["Optimal?"].iloc[0] == "Best"
