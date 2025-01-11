"""The Before / After rules: sign convention, near-zero baselines, TBD and regressions."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.common.before_after import (
    COLUMNS,
    COMPACT_COLUMNS,
    CONVENTION_NOTE,
    HIGHER,
    LOWER,
    Measurement,
    MetricSpec,
    compute_delta,
    compute_improvement_pct,
    make_row,
    render_markdown,
    row_cells,
    write_rows_csv,
)
from src.common.io import read_csv
from src.common.labels import NOT_COMPARABLE, PAPER_REPORTED, REPRODUCED, TARGET_TBD, TBD
from src.common.plotting import Bar, BeforeAfterPanel, before_after_figure

TURNAROUND = MetricSpec("avg_turnaround_ms", "Turnaround time", "ms", False, 1e-9, 1)
UTILISATION = MetricSpec("cpu_utilisation", "CPU utilisation", "fraction", True, 1e-9, 4)
STARVATION = MetricSpec("starvation_count", "Starvation count", "tasks", False, 1e-9, 2)


def test_lower_is_better_improvement_is_positive_when_after_is_smaller() -> None:
    assert compute_delta(200.0, 150.0) == -50.0
    assert compute_improvement_pct(200.0, 150.0, higher_is_better=False) == pytest.approx(25.0)
    assert compute_improvement_pct(200.0, 250.0, higher_is_better=False) == pytest.approx(-25.0)


def test_higher_is_better_improvement_is_positive_when_after_is_larger() -> None:
    assert compute_improvement_pct(0.80, 0.84, higher_is_better=True) == pytest.approx(5.0)
    assert compute_improvement_pct(0.80, 0.76, higher_is_better=True) == pytest.approx(-5.0)


def test_negative_baseline_uses_absolute_value_in_the_denominator() -> None:
    # A training return that rises from -200 to -150 is a 25% improvement, not -25%.
    assert compute_improvement_pct(-200.0, -150.0, higher_is_better=True) == pytest.approx(25.0)


def test_regression_is_reported_as_negative_not_hidden() -> None:
    row = make_row(UTILISATION, "SJF", Measurement(0.85, 0.002, 5),
                   "DDQN", Measurement(0.80, 0.004, 5))  # fmt: skip
    assert row.status == "ok"
    assert row.delta == pytest.approx(-0.05)
    assert row.improvement_pct == pytest.approx(-5.882352941)
    cells = row_cells(row)
    assert cells["Improvement %"] == "-5.9%"
    assert cells["Delta (absolute)"] == "-0.0500"
    assert cells["Direction"] == HIGHER
    assert cells["Before Value"] == "0.8500 ± 0.0020"


def test_zero_baseline_gives_delta_but_no_percentage() -> None:
    row = make_row(STARVATION, "FCFS", Measurement(0.0, 0.0, 5), "DDQN", Measurement(0.4, 0.5, 5))
    assert row.status == "not_comparable"
    assert row.delta == pytest.approx(0.4)
    assert row.improvement_pct is None
    cells = row_cells(row)
    assert cells["Improvement %"] == NOT_COMPARABLE
    assert cells["Delta (absolute)"] == "+0.40"
    assert "near zero" in row.note


def test_not_comparable_sides_get_neither_delta_nor_percentage() -> None:
    row = make_row(UTILISATION, "Reference (different setup)", Measurement(0.35),
                   "DDQN in this simulator", Measurement(0.84, 0.001, 5),
                   source_label=PAPER_REPORTED, comparable=False)  # fmt: skip
    assert row.status == "not_comparable"
    assert row.delta is None and row.improvement_pct is None
    cells = row_cells(row)
    assert cells["Delta (absolute)"] == NOT_COMPARABLE
    assert cells["Improvement %"] == NOT_COMPARABLE


def test_unrun_side_is_tbd_everywhere() -> None:
    row = make_row(TURNAROUND, "FCFS", Measurement(310.0, 12.0, 5), "DDQN", Measurement())
    assert row.status == "tbd"
    cells = row_cells(row)
    assert cells["After Value"] == TBD
    assert cells["Delta (absolute)"] == TBD
    assert cells["Improvement %"] == TBD
    assert (
        cells["Source Label"] == TARGET_TBD
    ), "an unmeasured row must never be labelled Reproduced"
    nan_row = make_row(TURNAROUND, "FCFS", Measurement(math.nan), "DDQN", Measurement(1.0))
    assert nan_row.status == "tbd"


def test_infinite_baseline_is_not_turned_into_a_ratio() -> None:
    longest_wait = MetricSpec("max_wait_ms", "Longest wait", "ms", False, 1e-9, 2)
    row = make_row(longest_wait, "FCFS", Measurement(math.inf), "DDQN",
                   Measurement(3.0, 0.0, 5))  # fmt: skip
    assert row.status == "not_comparable"
    cells = row_cells(row)
    assert cells["Before Value"] == "∞"
    assert cells["Improvement %"] == NOT_COMPARABLE


def test_source_label_must_be_one_of_the_three() -> None:
    with pytest.raises(ValueError):
        make_row(
            UTILISATION, "a", Measurement(0.5), "b", Measurement(0.6), source_label="[Measured]"
        )


def test_markdown_has_exact_columns_notes_and_convention(tmp_path: Path) -> None:
    rows = [
        make_row(
            TURNAROUND, "FCFS", Measurement(200.0, 10.0, 5), "DDQN", Measurement(150.0, 8.0, 5)
        ),
        make_row(STARVATION, "FCFS", Measurement(0.0, 0.0, 5), "DDQN", Measurement(0.0, 0.0, 5)),
    ]
    text = render_markdown(rows)
    header = text.splitlines()[0]
    assert header == "| " + " | ".join(COLUMNS) + " |"
    assert COLUMNS == (
        "Metric", "Unit", "Direction", "Before Method", "Before Value", "After Method",
        "After Value", "Delta (absolute)", "Improvement %", "Source Label",
    )  # fmt: skip
    assert "| Turnaround time | ms | Lower is better | FCFS | 200.0 ± 10.0 | DDQN |" in text
    assert "+25.0%" in text and REPRODUCED in text
    assert CONVENTION_NOTE in text
    assert "Starvation count, FCFS → DDQN" in text
    assert LOWER in text
    compact = render_markdown(rows, columns=COMPACT_COLUMNS, include_convention=False)
    assert compact.splitlines()[0] == "| " + " | ".join(COMPACT_COLUMNS) + " |"
    assert CONVENTION_NOTE not in compact

    csv_path = write_rows_csv(rows, tmp_path / "track.csv", track="scheduling")
    records = read_csv(csv_path)
    assert records[0]["improvement_pct"] == "25.0"
    assert records[1]["improvement_pct"] == "" and records[1]["status"] == "not_comparable"


def test_before_after_figure_is_written_and_handles_tbd(tmp_path: Path) -> None:
    panels = [
        BeforeAfterPanel("Turnaround time", "ms", LOWER,
                         (Bar("FCFS", "before", 200.0, 10.0), Bar("SJF", "before", 160.0, 9.0),
                          Bar("DDQN", "after", 150.0, 8.0)), digits=1),  # fmt: skip
        BeforeAfterPanel("Throughput", "tasks/s", HIGHER,
                         (Bar("FCFS", "before", 0.84, 0.0), Bar("DDQN", "after", None)), digits=3),  # fmt: skip
    ]
    path = before_after_figure(panels, tmp_path / "chart.png", "Scheduling", REPRODUCED,
                               caption="Test caption.")  # fmt: skip
    assert path.is_file() and path.stat().st_size > 5_000
