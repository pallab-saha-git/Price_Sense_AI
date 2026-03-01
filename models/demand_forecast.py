"""
models/demand_forecast.py
──────────────────────────
Prophet-based demand baseline forecasting.

Goal: Estimate what sales WOULD BE without a promotion (the counterfactual).
      The promo lift = Actual promo sales − Baseline forecast.

Prophet components:
  ŷ(t) = trend + seasonality(weekly/yearly) + holidays + ε

Usage:
  result = forecast_baseline(sales_df, sku_id="NUT-PIST-16", periods=4)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")  # suppress Prophet stan warnings


@dataclass
class ForecastResult:
    sku_id:             str
    baseline_weekly:    float      # average baseline weekly units (no promo)
    forecast_df:        pd.DataFrame   # columns: ds, yhat, yhat_lower, yhat_upper
    mape:               float      # Mean Absolute Percentage Error on last 8wk holdout
    seasonality_index:  dict       # {week_of_year: multiplier}
    model_used:         str = "prophet"

    def get_baseline_for_week(self, target_date: date) -> float:
        """Get the point-estimate baseline for a specific week."""
        target_str = pd.Timestamp(target_date).strftime("%Y-%m-%d")
        row = self.forecast_df[self.forecast_df["ds"].astype(str) >= target_str]
        if row.empty:
            return self.baseline_weekly
        return max(0.0, float(row.iloc[0]["yhat"]))


def _build_prophet_holidays(calendar_df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Convert CalendarEvents DataFrame to Prophet's holidays format."""
    if calendar_df is None or calendar_df.empty:
        return None
    hols = calendar_df[["date", "event_name"]].copy()
    hols.columns = ["ds", "holiday"]
    hols["ds"] = pd.to_datetime(hols["ds"])
    hols["lower_window"] = -1
    hols["upper_window"] = 1
    return hols


def forecast_baseline(
    sales_df: pd.DataFrame,
    sku_id: str,
    periods: int = 8,
    calendar_df: Optional[pd.DataFrame] = None,
    aggregate_stores: bool = True,
) -> ForecastResult:
    """
    Fit Prophet on non-promo weeks and forecast `periods` weeks into the future.

    Parameters
    ----------
    sales_df         : All sales data
    sku_id           : SKU to forecast
    periods          : Number of future weekly periods to predict
    calendar_df      : Optional calendar events for holiday effects
    aggregate_stores : If True, aggregate all stores; if False, keep store-level
    """
    try:
        from prophet import Prophet
        HAS_PROPHET = True
    except ImportError:
        HAS_PROPHET = False
        logger.warning("Prophet not installed — using simple moving average baseline")

    sku_data = sales_df[sales_df["sku_id"] == sku_id].copy()
    sku_data["date"] = pd.to_datetime(sku_data["date"])

    # Aggregate to weekly total across all stores
    weekly = (
        sku_data.groupby("date")["units_sold"]
        .sum()
        .reset_index()
        .rename(columns={"date": "ds", "units_sold": "y"})
        .sort_values("ds")
    )

    # Filter out promo weeks for a cleaner baseline
    if "is_promo" in sku_data.columns:
        promo_dates = set(sku_data[sku_data["is_promo"] == True]["date"].dt.normalize())
        weekly = weekly[~weekly["ds"].isin(promo_dates)]

    weekly = weekly[weekly["y"] > 0].copy()

    if len(weekly) < 20:
        fallback_val = float(weekly["y"].mean()) if len(weekly) > 0 else 100.0
        logger.warning(f"Insufficient non-promo weeks for {sku_id} — using MA fallback")
        return _fallback_forecast(sku_id, fallback_val, periods)

    # Holdout last 8 weeks for MAPE calculation
    holdout = weekly.tail(8)
    train   = weekly.iloc[:-8] if len(weekly) > 16 else weekly

    baseline_weekly = float(train["y"].mean())

    if not HAS_PROPHET:
        return _fallback_forecast(sku_id, baseline_weekly, periods, weekly)

    # Build seasonality index from actual data
    weekly_temp = weekly.copy()
    weekly_temp["woy"] = weekly_temp["ds"].dt.isocalendar().week
    seas_idx = (
        weekly_temp.groupby("woy")["y"].mean() / weekly_temp["y"].mean()
    ).to_dict()
    seas_idx = {int(k): round(float(v), 3) for k, v in seas_idx.items()}

    # Train Prophet
    holidays_df = _build_prophet_holidays(calendar_df)
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        holidays=holidays_df,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.15,
        interval_width=0.80,
    )

    try:
        model.fit(train)
    except Exception as exc:
        logger.error(f"Prophet fit failed for {sku_id}: {exc}")
        return _fallback_forecast(sku_id, baseline_weekly, periods, weekly)

    # Forecast
    future = model.make_future_dataframe(periods=len(holdout) + periods, freq="W")
    try:
        forecast = model.predict(future)
    except Exception as exc:
        logger.error(f"Prophet predict failed for {sku_id}: {exc}")
        return _fallback_forecast(sku_id, baseline_weekly, periods, weekly)

    forecast["yhat"] = forecast["yhat"].clip(lower=0)

    # MAPE on holdout
    holdout_pred = forecast[forecast["ds"].isin(holdout["ds"])]
    if not holdout_pred.empty and len(holdout) > 0:
        merged_ho = holdout.merge(holdout_pred[["ds", "yhat"]], on="ds", how="left")
        merged_ho = merged_ho[merged_ho["y"] > 0]
        if len(merged_ho) > 0:
            mape = float(np.mean(np.abs((merged_ho["y"] - merged_ho["yhat"]) / merged_ho["y"])) * 100)
        else:
            mape = 20.0
    else:
        mape = 20.0

    return ForecastResult(
        sku_id=sku_id,
        baseline_weekly=round(baseline_weekly, 1),
        forecast_df=forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(periods),
        mape=round(mape, 1),
        seasonality_index=seas_idx,
        model_used="prophet",
    )


def _fallback_forecast(
    sku_id: str,
    baseline: float,
    periods: int,
    weekly: Optional[pd.DataFrame] = None,
) -> ForecastResult:
    """Simple moving average fallback when Prophet is unavailable."""
    if weekly is not None and len(weekly) >= 12:
        ma_baseline = float(weekly["y"].rolling(12).mean().dropna().iloc[-1])
    else:
        ma_baseline = baseline

    last_date = pd.Timestamp.now().normalize()
    future_ds = pd.date_range(last_date, periods=periods, freq="W")
    forecast_df = pd.DataFrame({
        "ds":          future_ds,
        "yhat":        [ma_baseline] * periods,
        "yhat_lower":  [ma_baseline * 0.85] * periods,
        "yhat_upper":  [ma_baseline * 1.15] * periods,
    })

    # Compute basic seasonality index
    if weekly is not None and len(weekly) > 1:
        weekly_temp = weekly.copy()
        weekly_temp["woy"] = pd.to_datetime(weekly_temp["ds"]).dt.isocalendar().week
        overall_avg = float(weekly_temp["y"].mean())
        seas_idx = {
            int(k): round(float(v / overall_avg), 3)
            for k, v in weekly_temp.groupby("woy")["y"].mean().items()
        }
    else:
        seas_idx = {}

    return ForecastResult(
        sku_id=sku_id,
        baseline_weekly=round(ma_baseline, 1),
        forecast_df=forecast_df,
        mape=25.0,
        seasonality_index=seas_idx,
        model_used="moving_average",
    )
