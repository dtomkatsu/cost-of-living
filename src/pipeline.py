"""Shared pipeline: load baseline → CPI-adjust → weight → household costs.

This module exposes run_pipeline() so both the CLI (scripts/update_prices.py)
and the dashboard (dashboard/app.py) can share the same compute logic without
duplicating code.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .models import (
    AdjustedPrice,
    BasketConfig,
    CPIConfig,
    HouseholdConfig,
    HouseholdEstimate,
    StoreWeightsConfig,
)
from .cpi_fetcher import fetch_and_cache, load_cached_cpi
from .price_adjuster import adjust_prices, load_baseline
from .household_scaler import compute_household_costs
from .output import compute_weighted_county_prices

PROJECT_ROOT = Path(__file__).parent.parent
GET_TAX_RATE = 0.045  # Hawaii General Excise Tax, uniform across counties


def run_pipeline(
    target_date: date | None = None,
    baseline_path: Path | None = None,
    no_fetch: bool = False,
) -> dict:
    """Run the full price pipeline and return computed data objects.

    Does NOT write any files. Callers decide what to do with the results.

    Args:
        target_date: Month to compute prices for. Defaults to current month.
        baseline_path: Path to consolidated_baseline.csv. Defaults to the
            standard location in data/baseline/.
        no_fetch: If True, use cached CPI data only (no network calls).

    Returns a dict with keys:
        adjusted        list[AdjustedPrice]   — all per-store CPI-adjusted prices
        county_prices   list[AdjustedPrice]   — market-share-weighted county averages
        estimates       list[HouseholdEstimate] — household-scaled costs
        basket          BasketConfig
        target_date     date
        get_tax_rate    float                 — 0.045
        baseline_dates  set[str]              — ISO dates of baseline observations
    """
    # Resolve target date
    if target_date is None:
        today = date.today()
        target_date = date(today.year, today.month, 15)

    # Load configs
    basket = BasketConfig.load()
    cpi_config = CPIConfig.load()
    household_config = HouseholdConfig.load()
    store_weights = StoreWeightsConfig.load()

    # Load baseline prices
    if baseline_path is None:
        baseline_path = PROJECT_ROOT / "data" / "baseline" / "consolidated_baseline.csv"

    baseline_prices = load_baseline(baseline_path)

    # Determine if CPI adjustment is needed
    baseline_dates = set(bp.date for bp in baseline_prices)
    cpi_data: dict = {}

    if baseline_dates:
        first_date = date.fromisoformat(min(baseline_dates))
        baseline_month = (first_date.year, first_date.month)
        target_month = (target_date.year, target_date.month)

        if baseline_month != target_month:
            if no_fetch:
                cpi_data = load_cached_cpi() or {}
            else:
                start_year = first_date.year
                try:
                    cpi_data = fetch_and_cache(cpi_config, start_year=start_year)
                except Exception:
                    cpi_data = load_cached_cpi() or {}

    # Adjust prices
    adjusted = adjust_prices(baseline_prices, cpi_data, cpi_config, basket, target_date)

    # Collapse to weighted county averages
    county_prices = compute_weighted_county_prices(adjusted, store_weights)

    # Household scaling
    estimates = compute_household_costs(county_prices, household_config)

    return {
        "adjusted": adjusted,
        "county_prices": county_prices,
        "estimates": estimates,
        "basket": basket,
        "target_date": target_date,
        "get_tax_rate": GET_TAX_RATE,
        "baseline_dates": baseline_dates,
        "store_weights": store_weights,
    }
