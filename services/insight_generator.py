"""
services/insight_generator.py
──────────────────────────────
Generates human-readable insights from PromoAnalysisResult.

Two modes:
  1. Template-based (default, instant, no API cost)
  2. AI-powered via OpenRouter (when OPEN_ROUTER_API_KEY is set)

The AI mode sends the analysis summary to GPT-4o-mini via OpenRouter
and returns a rich 2-3 paragraph narrative insight.
"""

from __future__ import annotations

import time
import threading
from collections import deque
from typing import TYPE_CHECKING

from loguru import logger

from config.settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    USE_AI_INSIGHTS,
)

if TYPE_CHECKING:
    from services.promo_analyzer import PromoAnalysisResult

# ── Rate limiter (token-bucket style) ─────────────────────────────────────────
# OpenRouter free tier: 8 requests / 60 seconds
_RATE_LIMIT_MAX_CALLS = 7       # stay 1 under the limit to avoid edge cases
_RATE_LIMIT_WINDOW    = 60.0    # seconds
_call_timestamps: deque[float] = deque()
_rate_lock = threading.Lock()

# ── Circuit breaker ────────────────────────────────────────────────────────────
# Set to True when a non-retriable billing/auth error is encountered (402/401/403).
# Once tripped, all AI insight calls short-circuit to templates for the process lifetime.
_ai_circuit_open = False
_circuit_lock    = threading.Lock()

# Error codes that indicate a permanent billing/auth failure — no point retrying.
_FATAL_HTTP_CODES = {401, 402, 403}


def _is_fatal_error(exc_str: str) -> bool:
    """Return True if the error code indicates a permanent failure (billing/auth)."""
    for code in _FATAL_HTTP_CODES:
        if f"Error code: {code}" in exc_str or f"'code': {code}" in exc_str:
            return True
    return False


def _trip_circuit(reason: str) -> None:
    """Open the circuit breaker and log a clear one-time explanation."""
    global _ai_circuit_open
    with _circuit_lock:
        if not _ai_circuit_open:
            _ai_circuit_open = True
            logger.warning(
                f"AI insights disabled for this session: {reason}. "
                "All insights will use templates. "
                "To restore AI insights, fix the API key or increase its spend limit."
            )


def _wait_for_rate_limit() -> None:
    """Block until we are within the rate-limit window."""
    with _rate_lock:
        now = time.monotonic()
        # Purge timestamps older than the window
        while _call_timestamps and (now - _call_timestamps[0]) > _RATE_LIMIT_WINDOW:
            _call_timestamps.popleft()
        if len(_call_timestamps) >= _RATE_LIMIT_MAX_CALLS:
            # Must wait until oldest call exits the window
            sleep_time = _RATE_LIMIT_WINDOW - (now - _call_timestamps[0]) + 0.5
            if sleep_time > 0:
                logger.info(f"Rate limiter: sleeping {sleep_time:.1f}s before next AI call")
                time.sleep(sleep_time)
                # Re-purge after sleep
                now = time.monotonic()
                while _call_timestamps and (now - _call_timestamps[0]) > _RATE_LIMIT_WINDOW:
                    _call_timestamps.popleft()
        _call_timestamps.append(time.monotonic())


# ── Template bank ─────────────────────────────────────────────────────────────

TEMPLATES = {
    "RECOMMENDED_no_cannibal": (
        "This promotion is projected to generate **${inc_profit:,.0f}** in incremental profit "
        "with a **{roi:.1f}x ROI**. Volume lift of **+{lift_pct:.0f}%** (+{lift_units:,.0f} units) "
        "is supported by historical elasticity data. No material cannibalization detected "
        "from related SKUs. Risk is rated **{risk_band}**."
    ),
    "RECOMMENDED_with_cannibal": (
        "This promotion is projected to generate **${inc_profit:,.0f}** in net incremental profit "
        "after accounting for cannibalization. Volume lift of **+{lift_pct:.0f}%** is strong, "
        "but note that {cannibal_product} is projected to lose **${cannibal_cost:,.0f}** in margin "
        "({cannibal_pct:.0f}% volume depression). Net ROI remains positive at **{roi:.1f}x**."
    ),
    "MARGINAL": (
        "This promotion is marginally profitable at **${inc_profit:,.0f}** net incremental profit. "
        "The volume lift ({lift_pct:.0f}%) is partially offset by cannibalization costs "
        "(**${cannibal_cost:,.0f}**). Consider running this as a shorter promotion or pairing "
        "it with a vendor-funded deal to improve margin. Risk: **{risk_band}**."
    ),
    "NOT_RECOMMENDED_margin": (
        "This promotion is projected to lose **${loss:,.0f}** in margin after discount erosion "
        "and cannibalization. The {discount_pct:.0f}% discount is deeper than the margin improvement "
        "from the volume lift ({lift_pct:.0f}%). "
        "At **{alt_disc:.0f}% off**, the estimated net profit is **${alt_profit:,.0f}** — "
        "consider this as a more sustainable alternative."
    ),
    "NOT_RECOMMENDED_no_alt": (
        "This promotion is projected to generate a net loss of **${loss:,.0f}**. "
        "The primary driver is heavy margin erosion ({discount_pct:.0f}% discount) combined with "
        "cannibalization costs of **${cannibal_cost:,.0f}**. "
        "Consider a lower discount depth or a vendor-funded deal to make this viable."
    ),
    "high_cannibalization_warning": (
        "Cannibalization alert: Promoting {product} at {discount_pct:.0f}% off is "
        "projected to pull **{cannibal_pct:.0f}%** of {cannibal_product} sales. If both "
        "products are planned for the same promo window, consider staggering them by 2+ weeks."
    ),
    "seasonal_boost": (
        "Seasonal note: This promotion falls during a high-demand period "
        "(×{seas_mult:.1f}× baseline). The elevated natural demand means both the volume "
        "opportunity and the risk of stockout are higher than a normal week. "
        "Ensure sufficient inventory before running."
    ),
    "low_elasticity_warning": (
        "Elasticity note: {product} has low price sensitivity (elasticity: {elasticity:.2f}). "
        "Discounts will drive less volume lift than typical. Consider a feature + display "
        "promotion over pure price reduction to maintain margin while driving visibility."
    ),
    "INSUFFICIENT_DATA": (
        "**Not enough data** to reliably assess this promotion for **{product}**. "
        "Only {elast_obs} sales observations and {forecast_weeks} non-promo weeks are available "
        "in the selected scope. Metrics shown are rough estimates with very low confidence. "
        "To get a reliable assessment, either (a) wait for more sales history, "
        "(b) broaden the store/channel scope, or (c) confirm this SKU has transaction data "
        "in the selected channel."
    ),
}


def _build_context(result: "PromoAnalysisResult") -> dict:
    """Extract all values needed for template formatting."""
    cannibal_cost    = result.cannibalization.total_margin_loss
    worst_cannibal   = result.cannibalization.worst_affected

    # Get seasonality multiplier from the forecast result
    target_week = result.start_date.isocalendar()[1]
    seas_index  = result.forecast.seasonality_index if hasattr(result.forecast, 'seasonality_index') else {}
    seas_mult   = seas_index.get(int(target_week), 1.0)

    return {
        "product":         result.pnl.product_name,
        "sku_id":          result.sku_id,
        "discount_pct":    result.discount_pct * 100,
        "lift_pct":        result.lift_pct,
        "lift_units":      result.pnl.incremental_units,
        "inc_profit":      result.pnl.net_incremental_profit,
        "loss":            abs(result.pnl.net_incremental_profit),
        "roi":             result.pnl.promo_roi,
        "cannibal_cost":   cannibal_cost,
        "cannibal_product": worst_cannibal.affected_product_name if worst_cannibal else "related SKUs",
        "cannibal_pct":    worst_cannibal.pct_volume_depressed if worst_cannibal else 0.0,
        "risk_band":       result.risk.band,
        "risk_score":      result.risk.total_score,
        "elasticity":      result.elasticity.elasticity,
        "alt_disc":        (result.alt_discount_pct or 0.0) * 100,
        "alt_profit":      result.alt_pnl.net_incremental_profit if result.alt_pnl else 0.0,
        "seas_mult":       seas_mult,
        "elast_obs":       result.elasticity.n_observations,
        "forecast_weeks":  getattr(result.forecast, 'n_weeks_used', 0),
        "data_quality":    getattr(result, 'data_quality', 'good'),
    }


def generate_template_insights(result: "PromoAnalysisResult") -> list[str]:
    """
    Generate 1–3 insight strings from templates.
    Returns a list of markdown strings suitable for display.
    """
    ctx    = _build_context(result)
    rec    = result.recommendation
    has_c  = result.cannibalization.has_cannibalization

    insights: list[str] = []

    # Primary recommendation insight
    if rec == "INSUFFICIENT_DATA":
        insights.append(TEMPLATES["INSUFFICIENT_DATA"].format(**ctx))
        return insights  # no supplementary insights for insufficient data

    if rec == "RECOMMENDED":
        key = "RECOMMENDED_with_cannibal" if has_c else "RECOMMENDED_no_cannibal"
        insights.append(TEMPLATES[key].format(**ctx))
    elif rec == "MARGINAL":
        insights.append(TEMPLATES["MARGINAL"].format(**ctx))
    else:  # NOT_RECOMMENDED
        if result.alt_discount_pct and result.alt_pnl and result.alt_pnl.net_incremental_profit > 0:
            insights.append(TEMPLATES["NOT_RECOMMENDED_margin"].format(**ctx))
        else:
            insights.append(TEMPLATES["NOT_RECOMMENDED_no_alt"].format(**ctx))

    # Supplementary: high cannibalization warning
    if has_c and ctx["cannibal_pct"] > 15:
        insights.append(TEMPLATES["high_cannibalization_warning"].format(**ctx))

    # Supplementary: seasonal boost note
    if ctx["seas_mult"] > 1.3:
        insights.append(TEMPLATES["seasonal_boost"].format(**ctx))

    # Supplementary: low elasticity note
    if abs(result.elasticity.elasticity) < 1.2:
        insights.append(TEMPLATES["low_elasticity_warning"].format(**ctx))

    return insights


def generate_ai_insight(result: "PromoAnalysisResult", max_retries: int = 3) -> str:
    """
    Call OpenRouter API to generate a rich NL insight narrative.
    Includes:
      - Circuit breaker: instantly falls back to templates if a billing/auth
        error (402/401/403) has been seen this session.
      - Rate limiting: respects the free-tier 8 req/min cap.
      - Exponential-backoff retry: only on transient 429 errors.
    Falls back to templates on any persistent failure.
    """
    # ── Circuit breaker check ──────────────────────────────────────────────
    if _ai_circuit_open:
        return "\n\n".join(generate_template_insights(result))

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )

        ctx = _build_context(result)
        summary = (
            f"Product: {ctx['product']} | Discount: {ctx['discount_pct']:.0f}%\n"
            f"Recommendation: {result.recommendation}\n"
            f"Volume lift: +{ctx['lift_pct']:.1f}% (+{ctx['lift_units']:,.0f} units)\n"
            f"Net incremental profit: ${ctx['inc_profit']:,.0f}\n"
            f"Promo ROI: {ctx['roi']:.2f}x\n"
            f"Cannibalization: {ctx['cannibal_product']} loses {ctx['cannibal_pct']:.0f}% volume "
            f"(margin cost: ${ctx['cannibal_cost']:,.0f})\n"
            f"Risk: {ctx['risk_band']} ({ctx['risk_score']:.2f}/1.0)\n"
            f"Price elasticity: {ctx['elasticity']:.2f}\n"
        )
        if result.alt_discount_pct:
            summary += (
                f"Better alternative: {ctx['alt_disc']:.0f}% off → "
                f"${ctx['alt_profit']:,.0f} net profit\n"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior retail pricing analyst. You communicate in clear, "
                    "direct business language — no jargon, no hedging. "
                    "Speak in terms of dollars, ROI, and risk. "
                    "Keep your response to 2-3 concise paragraphs."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here is a promotion analysis summary for a retail category manager:\n\n"
                    f"{summary}\n\n"
                    "Write a 2-3 paragraph business insight that: "
                    "(1) explains the key recommendation in plain language, "
                    "(2) highlights the most important risk or opportunity, "
                    "(3) gives a specific actionable next step."
                ),
            },
        ]

        # ── Retry loop ─────────────────────────────────────────────────────
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                _wait_for_rate_limit()
                response = client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=messages,
                    max_tokens=400,
                    temperature=0.3,
                )
                return response.choices[0].message.content.strip()

            except Exception as api_exc:
                last_exc = api_exc
                exc_str  = str(api_exc)

                # ── Billing / auth — permanent, trip circuit and stop ─────
                if _is_fatal_error(exc_str):
                    _trip_circuit(exc_str[:120])
                    return "\n\n".join(generate_template_insights(result))

                # ── Rate limit (429) — transient, back off and retry ──────
                is_rate_limit = "429" in exc_str or "rate" in exc_str.lower()
                if is_rate_limit and attempt < max_retries - 1:
                    backoff = (2 ** attempt) * 10  # 10s, 20s, 40s
                    logger.info(
                        f"AI insight 429 on attempt {attempt + 1}/{max_retries} — "
                        f"retrying in {backoff}s"
                    )
                    time.sleep(backoff)
                else:
                    # Unknown error — don't retry
                    break

        logger.warning(
            f"AI insight generation failed after {max_retries} attempts: "
            f"{last_exc} — falling back to templates"
        )
        return "\n\n".join(generate_template_insights(result))

    except Exception as exc:
        logger.warning(f"AI insight generation failed: {exc} — falling back to templates")
        return "\n\n".join(generate_template_insights(result))


def generate_insights(result: "PromoAnalysisResult") -> list[str]:
    """
    Main entry point.
    Uses AI if OPEN_ROUTER_API_KEY is set and the circuit breaker is closed,
    otherwise uses templates.
    """
    if USE_AI_INSIGHTS and not _ai_circuit_open:
        ai_text = generate_ai_insight(result)
        # Return as single item list so caller can render as one block
        return [ai_text]
    return generate_template_insights(result)
