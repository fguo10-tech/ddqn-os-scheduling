"""Statistics used for every reported number.

Reporting convention used everywhere in this repository
-------------------------------------------------------
``mean ± std`` means: first average a metric *within* each seed (over evaluation
episodes), then take the mean and the **sample**
standard deviation (``ddof = 1``) of those per-seed values *across* seeds. With
five seeds the standard deviation therefore has four degrees of freedom. It
describes run-to-run variation; it is not a confidence interval.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np


def mean_std(values: Iterable[float]) -> tuple[float, float]:
    """Mean and sample standard deviation (``ddof=1``) of ``values``.

    The standard deviation is ``nan`` when fewer than two values are given,
    because one run carries no information about run-to-run variation.
    """
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return math.nan, math.nan
    if array.size == 1:
        return float(array[0]), math.nan
    if not np.all(np.isfinite(array)):
        # An infinite entry gives an infinite mean, and a spread is not defined.
        return float(np.sum(array)) if not np.any(np.isnan(array)) else math.nan, math.nan
    return float(array.mean()), float(array.std(ddof=1))


def format_mean_std(mean: float, std: float, digits: int = 3, n: int | None = None) -> str:
    """Render ``mean ± std`` with a fixed number of decimals.

    A missing mean renders as ``TBD``; a missing standard deviation (single run)
    renders as ``mean (n=1)`` rather than inventing a spread.
    """
    if mean is None or (isinstance(mean, float) and math.isnan(mean)):
        return "TBD"
    if std is None or (isinstance(std, float) and math.isnan(std)):
        suffix = f" (n={n})" if n is not None else " (n=1)"
        return f"{mean:.{digits}f}{suffix}"
    return f"{mean:.{digits}f} ± {std:.{digits}f}"


def summarise_by_seed(
    rows: Iterable[Mapping[str, Any]],
    group_keys: Sequence[str],
    value_keys: Sequence[str],
    seed_key: str = "seed",
) -> list[dict[str, Any]]:
    """Two-stage aggregation: mean within each seed, then mean ± std across seeds.

    Returns one dict per group with the group keys, ``n_seeds`` and, for each value
    key ``v``, the columns ``v_mean`` and ``v_std``. Rows whose value is empty or
    non-numeric are skipped for that value.
    """
    per_seed: dict[tuple, dict[Any, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    order: list[tuple] = []
    for row in rows:
        group = tuple(row[key] for key in group_keys)
        if group not in per_seed:
            order.append(group)
        seed = row[seed_key]
        for key in value_keys:
            number = _to_float(row.get(key))
            if number is not None:
                per_seed[group][seed][key].append(number)
    summary: list[dict[str, Any]] = []
    for group in order:
        seeds = per_seed[group]
        record: dict[str, Any] = dict(zip(group_keys, group, strict=True))
        record["n_seeds"] = len(seeds)
        for key in value_keys:
            seed_means = [float(np.mean(v[key])) for v in seeds.values() if v.get(key)]
            mean, std = mean_std(seed_means)
            record[f"{key}_mean"] = mean
            record[f"{key}_std"] = std
        summary.append(record)
    return summary


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number
