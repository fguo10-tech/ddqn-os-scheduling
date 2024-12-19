"""Statistics conventions and seed derivation."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.common.metrics import format_mean_std, mean_std, summarise_by_seed
from src.common.seeding import derive_seed, rng_from_seed


def test_mean_std_uses_sample_standard_deviation() -> None:
    mean, std = mean_std([1.0, 2.0, 3.0, 4.0, 5.0])
    assert mean == pytest.approx(3.0)
    assert std == pytest.approx(math.sqrt(2.5))  # ddof = 1
    single_mean, single_std = mean_std([7.0])
    assert single_mean == 7.0 and math.isnan(single_std)
    assert format_mean_std(3.0, math.sqrt(2.5), digits=2) == "3.00 ± 1.58"
    assert format_mean_std(7.0, math.nan, digits=1) == "7.0 (n=1)"
    assert format_mean_std(math.nan, math.nan) == "TBD"


def test_summarise_by_seed_averages_within_seed_first() -> None:
    rows = [
        {"method": "a", "seed": 0, "value": 1.0},
        {"method": "a", "seed": 0, "value": 3.0},  # seed 0 mean = 2
        {"method": "a", "seed": 1, "value": 4.0},  # seed 1 mean = 4
        {"method": "b", "seed": 0, "value": 10.0},
        {"method": "b", "seed": 1, "value": ""},  # missing value is skipped
    ]
    summary = {row["method"]: row for row in summarise_by_seed(rows, ["method"], ["value"])}
    assert summary["a"]["n_seeds"] == 2
    assert summary["a"]["value_mean"] == pytest.approx(3.0)
    assert summary["a"]["value_std"] == pytest.approx(math.sqrt(2.0))
    assert summary["b"]["value_mean"] == pytest.approx(10.0)
    assert math.isnan(summary["b"]["value_std"])


def test_seed_derivation_is_stable_and_label_sensitive() -> None:
    assert derive_seed(3, "client", 1) == derive_seed(3, "client", 1)
    assert derive_seed(3, "client", 1) != derive_seed(3, "client", 2)
    assert derive_seed(3, "client", 1) != derive_seed(4, "client", 1)
    first = rng_from_seed(5, "x").normal(size=4)
    second = rng_from_seed(5, "x").normal(size=4)
    assert np.array_equal(first, second)
