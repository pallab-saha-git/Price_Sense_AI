"""
models/demand_forecast.py
──────────────────────────
Demand baseline forecasting with a robust model cascade:

    1. Prophet  (best: trend + yearly seasonality + holiday effects)
    2. SARIMAX  (reliable: seasonal ARIMA from statsmodels — no binary deps)
    3. Moving Average  (safe fallback: always works)

Goal: Estimate what sales WOULD BE without a promotion (the counterfactual).
      The promo lift = Actual promo sales − Baseline forecast.

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

warnings.filterwarnings("ignore")  # suppress Prophet/statsmodels warnings

# ── Prophet availability probe ─────────────────────────────────────────────────
try:
    from prophet import Prophet as _Prophet
    _probe = _Prophet()
    del _probe
    HAS_PROPHET: bool = True
except Exception as _prophet_err:
    HAS_PROPHET = False
    logger.info(
        f"Prophet unavailable — will use SARIMAX/MA fallback. "
        f"({type(_prophet_err).__name__}: {_prophet_err})"
    )

# ── SARIMAX availability probe ─────────────────────────────────────────────────
try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX as _SARIMAX  # noqa: F401
    HAS_SARIMAX: bool = True
except ImportError:
    HAS_SARIMAX = False
    logger.warning("statsmodels SARIMAX unavailable — will use MA fallback only.")


@dataclass
class ForecastResult:
    sku_id:             str
    baseline_weekly:    float          # average baseline weekly units (no promo)
    forecast_df:        pd.DataFrame   # columns: ds, yhat, yhat_lower, yhat_upper
    mape:               float          # Mean Absolute Percentage Error on holdout
    seasonality_index:  dict           # {week_of_year: multiplier}
    model_used:         str = "prophet"   # 'prophet' | 'sarimax' | 'moving_average'
    data_quality:       str = "good"      # 'good' | 'limited' | 'insufficient'
    n_weeks_used:       int = 0           # number of non-promo weeks available

    def get_baseline_for_week(self, target_date: date) -> float:
        """Get the point-estimate baseline for a specific week."""
        target_str = pd.Timestamp(target_date).strftime("%Y-%m-%d")
        row = self.forecast_df[self.forecast_df["ds"].astype(str) >= target_str]
        if row.empty:
            return self.baseline_weekly
        return max(0.0, float(row.iloc[0]["yhat"]))


# ── Public API ─────────────────────────────────────────────────────────────────

def forecast_baseline(
    sales_df: pd.DataFrame,
    sku_id: str,
    periods: int = 8,
    calendar_df: Optional[pd.DataFrame] = None,
    aggregate_stores: bool = True,
) -> ForecastResult:
    """
    Forecast demand baseline using the best available model.

    Cascade:  Prophet → SARIMAX → Moving Average
    """
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
    n_weeks = len(weekly)

    # ── Insufficient data guard ────────────────────────────────────────────
    if n_weeks < 4:
        fallback_val = float(weekly["y"].mean()) if n_weeks > 0 else 100.0
        logger.warning(f"Very few non-promo weeks for {sku_id} ({n_weeks}) — insufficient data")
        return _ma_forecast(sku_id, fallback_val, periods, weekly if n_weeks > 1 else None,
                            data_quality="insufficient", n_weeks_used=n_weeks)

    if n_weeks < 12:
        fallback_val = float(weekly["y"].mean())
        logger.info(f"Limited non-promo weeks for {sku_id} ({n_weeks}) — using SARIMAX/MA")
        return _try_sarimax_or_ma(sku_id, weekly, periods, data_quality="limited",
                                   n_weeks_used=n_weeks, seasonal=False)

    if n_weeks < 20:
        fallback_val = float(weekly["y"].mean())
        logger.info(f"Moderate data for {sku_id} ({n_weeks} weeks) — using SARIMAX")
        return _try_sarimax_or_ma(sku_id, weekly, periods, data_quality="good",
                                   n_weeks_used=n_weeks, seasonal=False)

    # ── Sufficient data (≥ 20 weeks) — try full model cascade ──────────────
    result = _try_prophet(sku_id, weekly, periods, calendar_df, n_weeks)
    if result is not None:
        return result

    result = _try_sarimax(sku_id, weekly, periods, n_weeks, seasonal=(n_weeks >= 52))
    if result is not None:
        return result

    # Final fallback
    baseline_weekly = float(weekly["y"].mean())
    logger.info(f"All models failed for {sku_id} — using MA fallback")
    return _ma_forecast(sku_id, baseline_weekly, periods, weekly,
                        data_quality="good", n_weeks_used=n_weeks)


# ── Prophet ────────────────────────────────────────────────────────────────────

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


def _try_prophet(
    sku_id: str,
    weekly: pd.DataFrame,
    periods: int,
    calendar_df: Optional[pd.DataFrame],
    n_weeks: int,
) -> Optional[ForecastResult]:
    """Try Prophet; return None if unavailable or fails."""
    if not HAS_PROPHET:
        return None

    from prophet import Prophet

    holdout = weekly.tail(8)
    train   = weekly.iloc[:-8] if len(weekly) > 16 else weekly
    baseline_weekly = float(train["y"].mean())
    seas_idx = _build_seasonality_index(weekly)

    try:
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
        model.fit(train)

        future   = model.make_future_dataframe(periods=len(holdout) + periods, freq="W")
        forecast = model.predict(future)
        forecast["yhat"] = forecast["yhat"].clip(lower=0)
    except Exception as exc:
        logger.debug(f"Prophet fit failed for {sku_id} ({exc!r}) — trying SARIMAX")
        return None

    mape = _compute_mape(holdout, forecast)

    logger.info(f"Prophet forecast OK for {sku_id} (MAPE={mape:.1f}%, {n_weeks} weeks)")
    return ForecastResult(
        sku_id=sku_id,
        baseline_weekly=round(baseline_weekly, 1),
        forecast_df=forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(periods),
        mape=round(mape, 1),
        seasonality_index=seas_idx,
        model_used="prophet",
        data_quality="good",
        n_weeks_used=n_weeks,
    )


# ── SARIMAX ───────────────────────────────────────────────────────────────────

def _try_sarimax(
    sku_id: str,
    weekly: pd.DataFrame,
    periods: int,
    n_weeks: int,
    seasonal: bool = True,
) -> Optional[ForecastResult]:
    """
    Fit SARIMAX and forecast.

    - seasonal=True  uses SARIMAX(1,1,1)(1,1,1,52) for yearly seasonality (needs ≥ 52 weeks)
    - seasonal=False uses SARIMAX(1,1,1)(0,0,0,0)  — a simple ARIMA(1,1,1)
    """
    if not HAS_SARIMAX:
        return None

    from statsmodels.tsa.statespace.sarimax import SARIMAX

    holdout_size = min(8, max(1, len(weekly) // 5))
    train   = weekly.iloc[:-holdout_size] if len(weekly) > holdout_size + 4 else weekly
    holdout = weekly.tail(holdout_size) if len(weekly) > holdout_size + 4 else pd.DataFrame()

    ts = train.set_index("ds")["y"].asfreq("W-SUN")
    # Fill any missing weeks with interpolation
    ts = ts.interpolate(method="linear").bfill().ffill()
    if ts.isna().any() or len(ts) < 4:
        return None

    baseline_weekly = float(ts.mean())
    seas_idx = _build_seasonality_index(weekly)

    # Choose SARIMAX order
    if seasonal and n_weeks >= 104:
        order = (1, 1, 1)
        seasonal_order = (1, 1, 1, 52)
    elif seasonal and n_weeks >= 52:
        order = (1, 1, 1)
        seasonal_order = (1, 0, 1, 52)
    else:
        order = (1, 1, 1)
        seasonal_order = (0, 0, 0, 0)

    try:
        model = SARIMAX(
            ts,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False, maxiter=200)

        fc = fit.get_forecast(steps=holdout_size + periods)
        fc_mean = fc.predicted_mean.clip(lower=0)
        fc_ci   = fc.conf_int(alpha=0.20)

        forecast_df = pd.DataFrame({
            "ds":          fc_mean.index,
            "yhat":        fc_mean.values,
            "yhat_lower":  fc_ci.iloc[:, 0].clip(lower=0).values,
            "yhat_upper":  fc_ci.iloc[:, 1].values,
        })

    except Exception as exc:
        logger.debug(f"SARIMAX fit failed for {sku_id} ({exc!r}) — falling back to MA")
        return None

    # MAPE on holdout
    if not holdout.empty:
        holdout_pred = forecast_df.head(holdout_size)
        if len(holdout_pred) == len(holdout):
            actuals   = holdout["y"].values
            predicted = holdout_pred["yhat"].values
            mask = actuals > 0
            if mask.any():
                mape = float(np.mean(np.abs((actuals[mask] - predicted[mask]) / actuals[mask])) * 100)
            else:
                mape = 20.0
        else:
            mape = 20.0
    else:
        mape = 20.0

    forecast_future = forecast_df.tail(periods).reset_index(drop=True)

    model_label = f"sarimax({order[0]},{order[1]},{order[2]})"
    if seasonal_order[3] > 0:
        model_label += f"x({seasonal_order[0]},{seasonal_order[1]},{seasonal_order[2]},{seasonal_order[3]})"

    logger.info(f"SARIMAX forecast OK for {sku_id} ({model_label}, MAPE={mape:.1f}%, {n_weeks} weeks)")
    return ForecastResult(
        sku_id=sku_id,
        baseline_weekly=round(baseline_weekly, 1),
        forecast_df=forecast_future,
        mape=round(mape, 1),
        seasonality_index=seas_idx,
        model_used=model_label,
        data_quality="good",
        n_weeks_used=n_weeks,
    )


def _try_sarimax_or_ma(
    sku_id: str,
    weekly: pd.DataFrame,
    periods: int,
    data_quality: str,
    n_weeks_used: int,
    seasonal: bool = False,
) -> ForecastResult:
    """Try SARIMAX first, fall back to MA."""
    result = _try_sarimax(sku_id, weekly, periods, n_weeks_used, seasonal=seasonal)
    if result is not None:
        result.data_quality = data_quality
        return result

    baseline = float(weekly["y"].mean())
    return _ma_forecast(sku_id, baseline, periods, weekly,
                        data_quality=data_quality, n_weeks_used=n_weeks_used)


# ── Moving Average fallback ───────────────────────────────────────────────────

def _ma_forecast(
    sku_id: str,
    baseline: float,
    periods: int,
    weekly: Optional[pd.DataFrame] = None,
    data_quality: str = "limited",
    n_weeks_used: int = 0,
) -> ForecastResult:
    """Simple moving average fallback — always works."""
    if weekly is not None and len(weekly) >= 12:
        ma_baseline = float(weekly["y"].rolling(12).mean().dropna().iloc[-1])
    elif weekly is not None and len(weekly) >= 4:
        ma_baseline = float(weekly["y"].rolling(4).mean().dropna().iloc[-1])
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

    seas_idx = _build_seasonality_index(weekly)

    return ForecastResult(
        sku_id=sku_id,
        baseline_weekly=round(ma_baseline, 1),
        forecast_df=forecast_df,
        mape=25.0,
        seasonality_index=seas_idx,
        model_used="moving_average",
        data_quality=data_quality,
        n_weeks_used=n_weeks_used,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_seasonality_index(weekly: Optional[pd.DataFrame]) -> dict:
    """Compute {week_of_year: multiplier} from historical data."""
    if weekly is None or len(weekly) < 2:
        return {}
    wk = weekly.copy()
    wk["woy"] = pd.to_datetime(wk["ds"]).dt.isocalendar().week
    overall_avg = float(wk["y"].mean())
    if overall_avg == 0:
        return {}
    return {
        int(k): round(float(v / overall_avg), 3)
        for k, v in wk.groupby("woy")["y"].mean().items()
    }


def _compute_mape(holdout: pd.DataFrame, forecast: pd.DataFrame) -> float:
    """Compute MAPE between holdout actuals and forecast predictions."""
    holdout_pred = forecast[forecast["ds"].isin(holdout["ds"])]
    if not holdout_pred.empty and len(holdout) > 0:
        merged = holdout.merge(holdout_pred[["ds", "yhat"]], on="ds", how="left")
        merged = merged[merged["y"] > 0]
        if len(merged) > 0:
            return float(np.mean(np.abs((merged["y"] - merged["yhat"]) / merged["y"])) * 100)
    return 20.0
