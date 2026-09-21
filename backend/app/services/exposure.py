"""Aggregation of look-through leaves into the exposure tables the UI shows."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable

from ..models import AssetClass, ExposureRow, LookthroughReport
from .lookthrough import Leaf, LookthroughResult

UNKNOWN_LABEL = "Not disclosed / unclassified"

ASSET_CLASS_LABELS = {
    AssetClass.EQUITY: "Equity",
    AssetClass.BOND: "Bonds & fixed income",
    AssetClass.CASH: "Cash & equivalents",
    AssetClass.COMMODITY: "Commodities",
    AssetClass.REAL_ESTATE: "Real estate",
    AssetClass.CRYPTO: "Crypto",
    AssetClass.DERIVATIVE: "Derivatives",
    AssetClass.OTHER: "Other",
}


def _aggregate(
    leaves: Iterable[Leaf],
    key_fn: Callable[[Leaf], str],
    label_fn: Callable[[Leaf], str],
    total: float,
) -> list[ExposureRow]:
    buckets: dict[str, dict] = {}
    for leaf in leaves:
        key = key_fn(leaf)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "label": label_fn(leaf),
                "value": 0.0,
                "sources": defaultdict(float),
                "direct": 0.0,
                "indirect": 0.0,
                "asset_class": leaf.asset_class,
                "sector": leaf.sector,
                "country": leaf.country,
            }
            buckets[key] = bucket
        bucket["value"] += leaf.value
        bucket["sources"][leaf.origin] += leaf.value
        if leaf.depth == 0:
            bucket["direct"] += leaf.value
        else:
            bucket["indirect"] += leaf.value
        # Prefer a real label over a bare ticker if one turns up later.
        if bucket["label"] == key and label_fn(leaf) != key:
            bucket["label"] = label_fn(leaf)

    rows = [
        ExposureRow(
            key=key,
            label=b["label"],
            value=round(b["value"], 2),
            weight=(b["value"] / total) if total else 0.0,
            sources={k: round(v, 2) for k, v in sorted(b["sources"].items(), key=lambda kv: -kv[1])},
            direct_value=round(b["direct"], 2),
            indirect_value=round(b["indirect"], 2),
            asset_class=b["asset_class"],
            sector=b["sector"],
            country=b["country"],
        )
        for key, b in buckets.items()
    ]
    rows.sort(key=lambda r: r.value, reverse=True)
    return rows


def _asset_class_key(leaf: Leaf) -> str:
    return leaf.asset_class.value if leaf.asset_class else "unknown"


def _asset_class_label(leaf: Leaf) -> str:
    if leaf.asset_class is None:
        return UNKNOWN_LABEL
    return ASSET_CLASS_LABELS.get(leaf.asset_class, leaf.asset_class.value.title())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_report(result: LookthroughResult, scaled: bool = False) -> LookthroughReport:
    total = result.total_value
    leaves = result.leaves

    return LookthroughReport(
        total_value=round(total, 2),
        resolved_value=round(result.resolved_value, 2),
        unresolved_value=round(result.unresolved_value, 2),
        by_asset=_aggregate(leaves, lambda l: l.key, lambda l: l.label, total),
        by_asset_class=_aggregate(leaves, _asset_class_key, _asset_class_label, total),
        by_sector=_aggregate(
            leaves,
            lambda l: (l.sector or "unknown").strip().lower(),
            lambda l: l.sector or UNKNOWN_LABEL,
            total,
        ),
        by_country=_aggregate(
            leaves,
            lambda l: (l.country or "unknown").strip().lower(),
            lambda l: l.country or UNKNOWN_LABEL,
            total,
        ),
        fund_coverage={k: round(v, 4) for k, v in sorted(result.coverage.items())},
        fund_sources=dict(sorted(result.sources.items())),
        warnings=_dedupe(result.warnings),
        scaled=scaled,
    )


def concentration(rows: list[ExposureRow], top_n: int = 10) -> float:
    """Share of the portfolio held by the largest `top_n` base assets."""
    resolved = [r for r in rows if not r.key.startswith("__unresolved__")]
    return sum(r.weight for r in resolved[:top_n])
