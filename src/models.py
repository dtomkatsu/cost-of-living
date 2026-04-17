"""Data models for the Hawaii Grocery Price Tracker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BaselinePrice:
    """A single manually-collected price observation."""

    slot_id: str
    chain: str
    store_id: str
    county: str
    geoid: str
    date: str  # ISO date
    product_name: str
    price: float
    size_qty: float
    size_unit: str
    per_unit_price: float
    is_substitution: bool = False
    substitution_note: str | None = None


@dataclass
class AdjustedPrice:
    """A baseline price adjusted forward by CPI change."""

    slot_id: str
    chain: str
    store_id: str
    county: str
    geoid: str
    baseline_date: str
    adjusted_date: str
    baseline_price: float
    adjusted_price: float
    per_unit_price: float
    cpi_category: str
    cpi_ratio: float  # current_CPI / baseline_CPI


@dataclass
class HouseholdEstimate:
    """Estimated grocery cost for a specific household type and county."""

    household_type: str
    household_label: str
    county: str
    geoid: str
    date: str
    basket_total: float  # full 4-person reference basket
    household_cost: float  # scaled for this household type
    effective_factor: float


@dataclass
class BasketConfig:
    """Loaded basket configuration."""

    items: list[dict]

    @classmethod
    def load(cls, path: Path | None = None) -> BasketConfig:
        if path is None:
            path = Path(__file__).parent.parent / "config" / "basket.json"
        with open(path) as f:
            data = json.load(f)
        return cls(items=data["items"])

    def get_item(self, slot_id: str) -> dict | None:
        for item in self.items:
            if item["slot_id"] == slot_id:
                return item
        return None

    @property
    def slot_ids(self) -> list[str]:
        return [item["slot_id"] for item in self.items]


@dataclass
class StoreConfig:
    """Loaded store configuration."""

    counties: dict
    chains: dict

    @classmethod
    def load(cls, path: Path | None = None) -> StoreConfig:
        if path is None:
            path = Path(__file__).parent.parent / "config" / "stores.json"
        with open(path) as f:
            data = json.load(f)
        return cls(counties=data["counties"], chains=data["chains"])

    def get_geoid(self, county: str) -> str:
        return self.counties[county]["geoid"]

    def all_stores(self) -> list[dict]:
        stores = []
        for chain_id, chain_data in self.chains.items():
            for store in chain_data["stores"]:
                stores.append({**store, "chain": chain_id})
        return stores


@dataclass
class CPIConfig:
    """Loaded CPI series configuration."""

    categories: dict

    @classmethod
    def load(cls, path: Path | None = None) -> CPIConfig:
        if path is None:
            path = Path(__file__).parent.parent / "config" / "cpi_series.json"
        with open(path) as f:
            data = json.load(f)
        return cls(categories=data["categories"])

    def get_series_for_item(self, slot_id: str) -> tuple[str, str]:
        """Return (cpi_category, series_id) for a basket item."""
        for cat_id, cat_data in self.categories.items():
            if slot_id in cat_data["basket_items"]:
                return cat_id, cat_data["series_id"]
        raise ValueError(f"No CPI category found for {slot_id}")

    @property
    def all_series_ids(self) -> list[str]:
        return [cat["series_id"] for cat in self.categories.values()]


@dataclass
class StoreWeightsConfig:
    """Loaded store market share weights per chain per county."""

    weights: dict[str, dict[str, float]]  # county -> chain -> weight

    @classmethod
    def load(cls, path: Path | None = None) -> StoreWeightsConfig | None:
        """Load store weights. Returns None if file doesn't exist."""
        if path is None:
            path = Path(__file__).parent.parent / "config" / "store_weights.json"
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return cls(weights=data["weights"])

    def get_weight(self, county: str, chain: str) -> float | None:
        """Get the market share weight for a chain in a county.

        Returns None if county or chain not found.
        """
        county_weights = self.weights.get(county)
        if county_weights is None:
            return None
        return county_weights.get(chain)


@dataclass
class HouseholdConfig:
    """Loaded household scaling configuration."""

    household_types: dict
    individual_shares: dict
    size_multipliers: dict

    @classmethod
    def load(cls, path: Path | None = None) -> HouseholdConfig:
        if path is None:
            path = Path(__file__).parent.parent / "config" / "household_scales.json"
        with open(path) as f:
            data = json.load(f)
        return cls(
            household_types=data["household_types"],
            individual_shares=data["individual_shares"],
            size_multipliers=data["household_size_multipliers"],
        )
