"""Build every results table, Before / After CSV and chart from the reference run.

Reads ``configs/before_after.yaml`` and the CSV files under
``experiments/results/reference/`` and writes:

* ``generated/<block_id>.md`` — Markdown blocks that ``experiments/sync_docs.py`` injects into
  README, RESULTS.md, the project report, the poster and the slides, so a value can never
  differ between placements;
* ``before_after/*.csv`` and ``.png`` — the machine-readable Before / After tables and their
  grouped bar charts, side by side: the scheduling benchmark (``scheduling``) and the same
  benchmark on the LLM-style workload profile (``scheduling_llm``, ``scheduling_llm_by_class``);
* ``experiments/results/templates/*.csv`` — header-only schema templates of every result file.

If a CSV of the reference run does not exist, every value that depends on it is rendered as
``TBD``. This script never invents, rounds up or copies a number: paper-reported values come
only from ``src/common/paper_values.py`` and reproduced values only from the CSV files.

Usage::

    python -m experiments.build_results [--config configs/before_after.yaml] [--no-figures]
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.before_after import (
    COMPACT_COLUMNS,
    CONVENTION_NOTE,
    BeforeAfterRow,
    Measurement,
    MetricSpec,
    format_value,
    make_row,
    render_markdown,
    row_cells,
    write_rows_csv,
)
from src.common.config import load_config
from src.common.io import TRACKED_PACKAGES, ensure_dir, read_csv, read_json
from src.common.labels import PAPER_REPORTED, REPRODUCED, TARGET_TBD, TBD
from src.common.logging_utils import get_logger, setup_logging
from src.common.paper_values import PAPER_TABLE1

LOGGER = get_logger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "before_after.yaml"

# --------------------------------------------------------------------------------------
# small data helpers
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricCfg:
    """One metric entry of ``configs/before_after.yaml``."""

    key: str
    label: str
    unit: str
    higher_is_better: bool
    near_zero: float
    digits: int
    scale: float

    @property
    def spec(self) -> MetricSpec:
        return MetricSpec(
            self.key, self.label, self.unit, self.higher_is_better, self.near_zero, self.digits
        )


@dataclass(frozen=True)
class Paths:
    """Resolved output and input folders."""

    reference: Path
    generated: Path
    before_after: Path
    templates: Path


@dataclass(frozen=True)
class Study:
    """One benchmark run that gets its own Before / After tables, CSV and chart.

    ``note`` is a sentence about the workload that opens every table introduction (empty for
    the benchmark itself) and ``chart_note`` closes the chart caption.
    """

    stem: str
    note: str
    chart_note: str


BENCHMARK = Study("scheduling", "", "Synthetic workloads; simulator only.")
LLM_WORKLOAD = Study(
    "scheduling_llm",
    "Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic "
    "inference requests and fine-tuning jobs on the simulated node; no language model is run). ",
    "Synthetic LLM-style workload (inference requests and fine-tuning jobs); simulator only, "
    "no language model is run.",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Rows of a CSV file, or an empty list when the file does not exist yet."""
    if not path.is_file():
        LOGGER.warning("missing %s -> the tables that need it will show TBD", _rel(path))
        return []
    return read_csv(path)


def find_row(rows: Iterable[Mapping[str, str]], **match: str) -> Mapping[str, str] | None:
    """First row whose columns equal all ``match`` values."""
    for row in rows:
        if all(row.get(key) == value for key, value in match.items()):
            return row
    return None


def to_float(value: Any) -> float | None:
    """Parse a CSV cell; empty or non-numeric cells become ``None`` (``inf`` is kept)."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def measurement(row: Mapping[str, str] | None, metric: MetricCfg) -> Measurement:
    """Mean ± std of ``metric`` from a summary row (``Measurement()`` if absent = TBD)."""
    if row is None:
        return Measurement()
    mean = to_float(row.get(f"{metric.key}_mean"))
    if mean is None:
        return Measurement()
    std = to_float(row.get(f"{metric.key}_std"))
    count = to_float(row.get("n_seeds"))
    if math.isinf(mean):
        return Measurement(mean, None, int(count) if count is not None else None)
    return Measurement(
        mean * metric.scale,
        None if std is None else std * metric.scale,
        int(count) if count is not None else None,
    )


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _label(rows: Sequence[BeforeAfterRow]) -> str:
    """Source label of a whole table or chart: Reproduced only if something was measured."""
    return REPRODUCED if any(row.status != "tbd" for row in rows) else TARGET_TBD


def _value_cell(value: Measurement, digits: int, unit: str) -> str:
    """A reproduced-value cell with its label (or TBD with the TBD label)."""
    if not value.available:
        return f"{TBD} {TARGET_TBD}"
    return f"{format_value(value, digits)} {unit} {REPRODUCED}".replace("  ", " ")


def _paper_cell(value: float | None, unit: str, digits: int) -> str:
    if value is None:
        return "not reported"
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{value:.0f}"
    return f"{text} {unit} {PAPER_REPORTED}".replace("  ", " ")


def _table(header: Sequence[str], body: Iterable[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines.extend("| " + " | ".join(cells) + " |" for cells in body)
    return "\n".join(lines) + "\n"


def _seed_note(rows: Sequence[BeforeAfterRow]) -> str:
    counts = sorted(
        {r.after.n for r in rows if r.after.n} | {r.before.n for r in rows if r.before.n}
    )
    if not counts:
        return "No run found: every value is TBD."
    seeds = " or ".join(str(count) for count in counts)
    return f"Values are mean ± sample standard deviation over {seeds} seeds."


# --------------------------------------------------------------------------------------
# scheduling: Before / After tables, findings, ablations and the tail analysis
# --------------------------------------------------------------------------------------


def build_scheduling(cfg: Mapping[str, Any], paths: Paths, figures: bool) -> dict[str, str]:
    """All generated blocks, the CSV and the chart of the scheduling benchmark."""
    track = cfg["scheduling"]
    summary = read_rows(paths.reference / track["summary_csv"])
    metrics = [MetricCfg(**entry) for entry in track["metrics"]]
    blocks, value = _comparison_blocks(track, summary, metrics, paths, figures, BENCHMARK)
    blocks["paper_vs_reproduced"] = _scheduling_paper_table(
        summary, track["method_labels"], track["load_profile"]
    )
    blocks["findings"] = _scheduling_findings(track, metrics, value)
    blocks["all_methods"] = _scheduling_all_methods(summary, track, metrics)
    blocks["ablations"] = _scheduling_ablations(track, paths)
    blocks["tail_analysis"] = _scheduling_tail(track, paths)
    return blocks


def _comparison_blocks(
    track: Mapping[str, Any],
    summary: list[dict[str, str]],
    metrics: Sequence[MetricCfg],
    paths: Paths,
    figures: bool,
    study: Study,
):
    """The four Before / After blocks, the CSV and the chart of one study.

    Returns the blocks (ids without a prefix) and the ``value(method, metric, load)`` lookup.
    """
    labels: dict[str, str] = track["method_labels"]
    after: str = track["after_method"]
    befores: list[str] = list(track["before_methods"])
    pooled: str = track["load_profile"]
    csv_rel = _rel(paths.before_after / f"{study.stem}.csv")

    def value(method: str, metric: MetricCfg, load: str) -> Measurement:
        return measurement(find_row(summary, method=method, load_profile=load), metric)

    def rows_for(load: str) -> list[BeforeAfterRow]:
        return [
            make_row(metric.spec, labels[b], value(b, metric, load), labels[after], value(after, metric, load))
            for metric in metrics
            for b in befores
        ]  # fmt: skip

    def best_rows(load: str) -> list[BeforeAfterRow]:
        chosen: list[BeforeAfterRow] = []
        for metric in metrics:
            candidates = [(b, value(b, metric, load)) for b in befores]
            usable = [(b, m) for b, m in candidates if m.finite]
            if usable:
                pick = (max if metric.higher_is_better else min)(
                    usable, key=lambda item: item[1].mean
                )
            else:
                pick = candidates[0]
            chosen.append(
                make_row(metric.spec, labels[pick[0]], pick[1], labels[after], value(after, metric, load))
            )  # fmt: skip
        return chosen

    full = rows_for(pooled)
    best = best_rows(pooled)
    blocks: dict[str, str] = {}
    intro = (
        f"Source label: {_label(full)}. {study.note}Before = FCFS, SJF, Round Robin and Priority; "
        f"After = {labels[after]}. Load profiles light, medium and heavy are pooled. "
        f"{_seed_note(full)} Underlying CSV: `{csv_rel}`.\n\n"
    )
    blocks["before_after_full"] = intro + render_markdown(full)
    blocks["before_after_summary"] = (
        f"Source label: {_label(best)}. {study.note}For each metric the Before method is the **best of the four "
        f"baselines on that metric**, which is the most demanding comparison: if the After method "
        f"loses to it, the row shows a negative Improvement %. The table against every baseline is "
        f"in `experiments/results/RESULTS.md`. {_seed_note(best)}\n\n" + render_markdown(best)
    )
    blocks["before_after_compact"] = (
        f"Source label: {_label(best)}. {study.note}Before = best of FCFS / SJF / Round Robin / Priority per "
        f"metric; After = {labels[after]}.\n\n"
        + render_markdown(best, columns=COMPACT_COLUMNS, include_convention=False)
        + "\nA positive Improvement % always means better after; a negative value is a regression.\n"
    )
    by_load = [
        f"Source label: {_label(full)}. {study.note}One table per load profile. {_seed_note(full)}\n"
    ]
    for load in track["per_load_profiles"]:
        by_load.append(f"**Load profile: {load}**\n")
        by_load.append(render_markdown(rows_for(load), include_convention=False))
    by_load.append(CONVENTION_NOTE + "\n")
    blocks["before_after_by_load"] = "\n".join(by_load)

    write_rows_csv(full, paths.before_after / f"{study.stem}.csv", track=study.stem)
    if figures:
        _scheduling_chart(
            track, metrics, value, pooled, paths, _label(full), _seed_note(full), study
        )
    return blocks, value


def _scheduling_paper_table(
    summary: list[dict[str, str]], labels: Mapping[str, str], load: str
) -> str:
    paper_metrics = [
        (
            "Average completion (turnaround) time",
            "avg_completion_time_ms",
            "avg_turnaround_ms",
            "ms",
            1,
        ),
        ("Throughput", "throughput_tasks_per_s", "throughput_tasks_per_s", "tasks/s", 3),
        ("Average response time", "avg_response_time_ms", "avg_response_ms", "ms", 1),
    ]
    methods = [
        ("FCFS", "fcfs"),
        ("SJF", "sjf"),
        ("RR", "round_robin"),
        (None, "priority"),
        (None, "srtf"),
        ("DDQN", "ddqn"),
    ]
    notes = {
        "fcfs": "Baseline.",
        "sjf": "Non-preemptive, shortest next CPU burst.",
        "round_robin": "Quantum set in `configs/scheduler_baselines.yaml`.",
        "priority": "Added by this repository.",
        "srtf": "Reference added by this repository: preemptive shortest-remaining-burst-first.",
        "ddqn": "Reward with time penalties and a completion bonus; standard Double DQN target; guardrails on.",
    }
    body = []
    for paper_name, method in methods:
        for name, paper_key, key, unit, digits in paper_metrics:
            paper_value = PAPER_TABLE1[paper_name][paper_key] if paper_name else None
            metric = MetricCfg(key, name, unit, False, 0.0, digits, 1.0)
            reproduced = measurement(find_row(summary, method=method, load_profile=load), metric)
            body.append(
                [labels[method], name, _paper_cell(paper_value, unit, 1), _value_cell(reproduced, digits, unit), notes[method]]
            )  # fmt: skip
    text = _table(["Method", "Metric", "Paper-reported", "Reproduced (mean ± std)", "Notes"], body)
    text += (
        "\nThe Paper-reported column is shown for reference only: it comes from a different setup, "
        "while the Reproduced column comes from this repository's simulator with the settings in "
        "`configs/scheduler_ddqn.yaml` (all three load profiles pooled). No difference between the "
        "two columns is computed anywhere in this repository.\n"
    )
    return text


def _scheduling_findings(track: Mapping[str, Any], metrics: Sequence[MetricCfg], value) -> str:
    """Bullet list of what the scheduling results show; every number comes from summary.csv."""
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    befores: list[str] = list(track["before_methods"])
    pooled: str = track["load_profile"]

    def row(before: str, metric: MetricCfg, load: str, after_method: str = after) -> BeforeAfterRow:
        return make_row(
            metric.spec,
            labels[before],
            value(before, metric, load),
            labels[after_method],
            value(after_method, metric, load),
        )

    def best_before(metric: MetricCfg, load: str) -> str:
        usable = [(b, value(b, metric, load)) for b in befores if value(b, metric, load).finite]
        if not usable:
            return befores[0]
        chooser = max if metric.higher_is_better else min
        return chooser(usable, key=lambda item: item[1].mean)[0]

    if not value(after, metrics[0], pooled).available:
        return f"- {TBD} {TARGET_TBD}: the scheduling benchmark has not been run.\n"

    def verdict(candidate: BeforeAfterRow) -> str:
        cells = row_cells(candidate)
        if candidate.improvement_pct is None:
            return f"no percentage ({cells['Improvement %']})"
        word = "better" if candidate.improvement_pct > 0 else "worse"
        return f"Improvement {cells['Improvement %']} ({word})"

    def relative(candidate: BeforeAfterRow) -> str:
        """How the After method stands relative to a reference method."""
        if candidate.improvement_pct is None:
            return f"no percentage: {row_cells(candidate)['Improvement %']}"
        word = "better" if candidate.improvement_pct > 0 else "worse"
        return f"{labels[after]} is {abs(candidate.improvement_pct):.1f}% {word} than the reference"

    lines = ["Load profiles pooled:", ""]
    wins = 0
    comparable = 0
    for metric in metrics:
        chosen = row(best_before(metric, pooled), metric, pooled)
        per_baseline = [row(b, metric, pooled) for b in befores]
        beaten = [r.before_method for r in per_baseline if (r.improvement_pct or 0) > 0]
        scored = [r for r in per_baseline if r.improvement_pct is not None]
        if chosen.improvement_pct is not None:
            comparable += 1
            wins += chosen.improvement_pct > 0
        cells = row_cells(chosen)
        lines.append(
            f"- **{metric.label}** ({metric.spec.direction.lower()}): {labels[after]} "
            f"{cells['After Value']} {metric.unit}; best baseline {chosen.before_method} "
            f"{cells['Before Value']} {metric.unit}; {verdict(chosen)}. Better than {len(beaten)} of "
            f"{len(scored)} baselines with a computable percentage"
            + (f" ({', '.join(beaten)})." if beaten else ".")
            + f" {REPRODUCED}"
        )
    lines.append(
        f"- Against the best baseline per metric, {labels[after]} is better on {wins} of {comparable} "
        f"metrics with a computable percentage. {REPRODUCED}"
    )

    headline = metrics[0]
    lines += ["", f"{headline.label} by load profile:", ""]
    for load in track["per_load_profiles"]:
        chosen = row(best_before(headline, load), headline, load)
        cells = row_cells(chosen)
        lines.append(
            f"- {load}: {labels[after]} {cells['After Value']} {headline.unit}; best baseline "
            f"{chosen.before_method} {cells['Before Value']} {headline.unit}; {verdict(chosen)}. {REPRODUCED}"
        )

    references = [m for m in track["reference_methods"] if value(m, headline, pooled).available]
    if references:
        lines += ["", "References that are not Before methods (pooled):", ""]
    for reference in references:
        parts = []
        for metric in metrics[:1] + [
            m for m in metrics if m.key in ("avg_response_ms", "slo_violation_rate")
        ]:
            candidate = row(reference, metric, pooled)
            cells = row_cells(candidate)
            parts.append(
                f"{metric.label}: reference {cells['Before Value']} versus {cells['After Value']} "
                f"{metric.unit} for {labels[after]} ({relative(candidate)})"
            )
        lines.append(f"- {labels[reference]} — " + "; ".join(parts) + f". {REPRODUCED}")
        for load in track["per_load_profiles"]:
            candidate = row(reference, headline, load)
            cells = row_cells(candidate)
            lines.append(
                f"  - {load}: {headline.label.lower()} reference {cells['Before Value']} versus "
                f"{cells['After Value']} {headline.unit} ({relative(candidate)})."
            )

    throughput = next((m for m in metrics if m.key == "throughput_tasks_per_s"), None)
    if throughput is not None:
        measured = [value(m, throughput, pooled) for m in befores + [after]]
        means = [m.mean for m in measured if m.finite]
        if means and min(means) > 0:
            spread = (max(means) - min(means)) / min(means) * 100.0
            lines += [
                "",
                f"- Plain throughput differs by at most {spread:.1f}% between the five compared methods "
                f"(pooled). {REPRODUCED}",
            ]
    return "\n".join(lines) + "\n"


def _scheduling_all_methods(
    summary: list[dict[str, str]],
    track: Mapping[str, Any],
    metrics: Sequence[MetricCfg],
    note: str = "",
) -> str:
    """Reproduced-only table: every method, every load profile, the headline metrics and extras."""
    extras = [
        MetricCfg("p95_turnaround_ms", "p95 turnaround", "ms", False, 0.0, 1, 1.0),
        MetricCfg(
            "windowed_throughput_tasks_per_s", "Windowed throughput", "tasks/s", True, 0.0, 3, 1.0
        ),
        MetricCfg("cpu_utilisation", "CPU utilisation", "fraction", True, 0.0, 3, 1.0),
        MetricCfg("max_wait_ms", "Longest wait", "ms", False, 0.0, 1, 1.0),
        MetricCfg("priority_adjustments", "Priority actions", "per episode", False, 0.0, 1, 1.0),
        MetricCfg("guardrail_overrides", "Guardrail overrides", "per episode", False, 0.0, 2, 1.0),
    ]
    columns = list(metrics) + [m for m in extras if any(f"{m.key}_mean" in row for row in summary)]
    methods = (
        list(track["before_methods"]) + [track["after_method"]] + list(track["reference_methods"])
    )
    labels = track["method_labels"]
    header = ["Load", "Method"] + [f"{m.label} ({m.unit})" for m in columns]
    body = []
    for load in [track["load_profile"], *track["per_load_profiles"]]:
        for method in methods:
            row = find_row(summary, method=method, load_profile=load)
            body.append(
                [load, labels[method]]
                + [format_value(measurement(row, m), m.digits) for m in columns]
            )
    any_value = any(cell != TBD for cells in body for cell in cells[2:])
    return (
        f"Source label: {REPRODUCED if any_value else TARGET_TBD}. {note}Every cell is mean ± sample standard "
        "deviation across seeds; `all` pools the three load profiles.\n\n" + _table(header, body)
    )


CHART_LABELS = {
    "fcfs": "FCFS",
    "sjf": "SJF",
    "round_robin": "RR",
    "priority": "Priority",
    "ddqn": "DDQN",
    "ddqn_unguarded": "DDQN no overrides",
    "srtf": "SRTF (ref)",
}
"""Short method names on the x-axis of the Before / After charts."""


def _scheduling_chart(
    track, metrics, value, load, paths: Paths, label: str, seed_note: str, study: Study
) -> None:
    from src.common.plotting import Bar, BeforeAfterPanel, before_after_figure

    short = CHART_LABELS
    order = (
        [(m, "before") for m in track["before_methods"]]
        + [(track["after_method"], "after")]
        + [(m, "reference") for m in track["reference_methods"]]
    )
    panels = []
    for metric in metrics:
        bars = []
        for method, role in order:
            measured = value(method, metric, load)
            bars.append(
                Bar(
                    short.get(method, method),
                    role,
                    measured.mean if measured.available else None,
                    measured.std,
                )
            )
        panels.append(
            BeforeAfterPanel(
                metric.label, metric.unit, metric.spec.direction, tuple(bars), metric.digits
            )
        )
    before_after_figure(
        panels,
        paths.before_after / f"{study.stem}.png",
        f"{track['title']}: Before / After",
        label,
        caption=(
            f"Bars: mean across seeds; error bars: sample standard deviation across seeds. {seed_note} "
            "Load profiles pooled. Grey = references that are neither Before nor After methods: preemptive "
            f"SRTF and the same agent with the guardrail overrides off. {study.chart_note}"
        ),
    )


def _scheduling_ablations(track: Mapping[str, Any], paths: Paths) -> str:
    """Ablation table: the After method retrained under one changed setting at a time."""
    base = paths.reference / "scheduler"
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    config_path = REPO_ROOT / "configs" / "scheduler_ddqn.yaml"
    ablations: Mapping[str, Mapping[str, Any]] = (
        load_config(config_path).get("ablations", {}) if config_path.is_file() else {}
    )
    columns = [
        (MetricCfg("avg_turnaround_ms", "Turnaround, pooled", "ms", False, 1e-9, 1, 1.0), "all"),
        (MetricCfg("avg_turnaround_ms", "Turnaround, heavy load", "ms", False, 1e-9, 1, 1.0), "heavy"),
        (MetricCfg("avg_response_ms", "Response time, pooled", "ms", False, 1e-9, 1, 1.0), "all"),
        (MetricCfg("slo_violation_rate", "SLO violation rate, pooled", "fraction", False, 0.005, 4, 1.0), "all"),
        (MetricCfg("starvation_count", "Starvation count, pooled", "tasks/episode", False, 0.05, 3, 1.0), "all"),
        (MetricCfg("guardrail_overrides", "Guardrail overrides, pooled", "decisions/episode", False, 1e-9, 2, 1.0), "all"),
    ]  # fmt: skip
    default_rows = read_rows(base / "summary.csv") if (base / "summary.csv").is_file() else []
    header = ["Variant", "What changed"] + [f"{m.label} ({m.unit})" for m, _ in columns]
    header.append("Pooled turnaround versus default")
    body = [
        ["default (reference run)", "nothing"]
        + [format_value(measurement(find_row(default_rows, method=after, load_profile=load), m), m.digits)
           for m, load in columns]
        + ["reference"]
    ]  # fmt: skip
    measured = any(cell != TBD for cell in body[0][2:-1])
    headline, headline_load = columns[0]
    default_value = measurement(
        find_row(default_rows, method=after, load_profile=headline_load), headline
    )
    for name, overrides in ablations.items():
        path = base / "ablations" / name / "summary.csv"
        rows = read_csv(path) if path.is_file() else []
        change = "; ".join(f"`{key}` = `{value}`" for key, value in overrides.items())
        cells = [
            format_value(measurement(find_row(rows, method=after, load_profile=load), m), m.digits)
            for m, load in columns
        ]
        measured = measured or any(cell != TBD for cell in cells)
        comparison = make_row(
            headline.spec,
            "default",
            default_value,
            name,
            measurement(find_row(rows, method=after, load_profile=headline_load), headline),
        )
        body.append([f"`{name}`", change, *cells, row_cells(comparison)["Improvement %"]])
    return (
        f"Source label: {REPRODUCED if measured else TARGET_TBD}. Each variant retrains the agent on the "
        f"same seeds with one setting changed and evaluates **{labels[after]}** on the same paired "
        "workloads as the reference run; mean ± sample standard deviation across seeds. In the last "
        "column a positive value means the variant has a lower pooled turnaround than the default, a "
        "negative value a higher one. A variant that was not run shows TBD. The baselines are not "
        "affected by any of these settings.\n\n" + _table(header, body)
    )


def _scheduling_tail(
    track: Mapping[str, Any], paths: Paths, run: str = "scheduler", note: str = ""
) -> str:
    """Per-seed values, per-episode distribution and paired win rates under each load."""
    import numpy as np

    raw = read_rows(paths.reference / run / "raw_episodes.csv")
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    methods = list(track["before_methods"]) + [after] + list(track["reference_methods"])
    if not raw:
        return f"{TBD} {TARGET_TBD}: the scheduling benchmark has not been run.\n"
    key = "avg_turnaround_ms"
    seeds = sorted({int(row["seed"]) for row in raw})
    episodes: dict[tuple[str, int, str], dict[str, float]] = {}
    for row in raw:
        episodes.setdefault((row["load_profile"], int(row["seed"]), row["episode"]), {})[
            row["method"]
        ] = float(row[key])
    parts = [
        f"Source label: {REPRODUCED}. {note}All values are average turnaround times in ms, computed from "
        f"`{_rel(paths.reference / run / 'raw_episodes.csv')}`.\n"
    ]
    heavy = "heavy" if "heavy" in track["per_load_profiles"] else track["per_load_profiles"][-1]
    body = []
    for method in methods:
        per_seed = []
        for seed in seeds:
            values = [
                v[method]
                for (load, s, _), v in episodes.items()
                if load == heavy and s == seed and method in v
            ]
            per_seed.append(float(np.mean(values)) if values else float("nan"))
        spread = float(np.std(per_seed, ddof=1)) if len(per_seed) > 1 else float("nan")
        body.append(
            [
                labels[method],
                *[f"{v:.1f}" for v in per_seed],
                f"{np.mean(per_seed):.1f} ± {spread:.1f}",
            ]
        )
    parts.append(f"**Per seed, {heavy} load** (mean over that seed's evaluation workloads):\n")
    parts.append(
        _table(["Method", *[f"Seed {seed}" for seed in seeds], "Mean ± std across seeds"], body)
    )
    body = []
    for method in methods:
        values = np.array(
            [v[method] for (load, _, _), v in episodes.items() if load == heavy and method in v]
        )
        body.append([labels[method], str(values.size), f"{np.median(values):.1f}",
                     f"{np.percentile(values, 90):.1f}", f"{values.max():.1f}"])  # fmt: skip
    parts.append(
        f"**Distribution over single evaluation workloads, {heavy} load** (all seeds together):\n"
    )
    parts.append(_table(["Method", "Workloads", "Median", "90th percentile", "Maximum"], body))
    body = []
    for load in track["per_load_profiles"]:
        cells = [load]
        paired = [v for (name, _, _), v in episodes.items() if name == load and after in v]
        cells.append(str(len(paired)))
        for rival in ("sjf", "srtf"):
            usable = [v for v in paired if rival in v]
            wins = sum(v[after] < v[rival] for v in usable)
            cells.append(f"{wins} of {len(usable)}")
        doubled = sum(v[after] > 2.0 * v["sjf"] for v in paired if "sjf" in v)
        cells.append(str(doubled))
        body.append(cells)
    parts.append(
        f"**Paired comparison on identical workloads** — in how many evaluation workloads does "
        f"{labels[after]} have a lower turnaround than the other method:\n"
    )
    parts.append(
        _table(["Load", "Workloads", f"Lower than {labels['sjf']}", f"Lower than {labels['srtf']}",
                f"More than twice {labels['sjf']}"], body)
    )  # fmt: skip
    worst = sorted(
        (row for row in raw if row["method"] == after and row["load_profile"] == heavy),
        key=lambda row: -float(row[key]),
    )[:5]
    body = [
        [row["seed"], row["episode"], row.get("n_tasks", ""), f"{float(row[key]):.1f}",
         f"{episodes[(heavy, int(row['seed']), row['episode'])].get('sjf', float('nan')):.1f}",
         row.get("guardrail_overrides", ""), row.get("guardrail_slo_fallback_activations", ""),
         row.get("guardrail_starvation_triggers", "")]
        for row in worst
    ]  # fmt: skip
    parts.append(f"**The five worst {heavy}-load workloads of {labels[after]}:**\n")
    parts.append(
        _table(["Seed", "Workload", "Tasks", f"Turnaround, {labels[after]}", f"Turnaround, {labels['sjf']}",
                "Guardrail overrides", "SLO-fallback activations", "Starvation triggers"], body)
    )  # fmt: skip
    return "\n".join(parts)


# --------------------------------------------------------------------------------------
# the same benchmark on the LLM-style workload profile
# --------------------------------------------------------------------------------------


def build_llm_workload(cfg: Mapping[str, Any], paths: Paths, figures: bool) -> dict[str, str]:
    """All generated blocks, CSVs and charts of the LLM-style workload study (ids ``llm_*``).

    The section ``scheduling_llm`` of ``configs/before_after.yaml`` names the run and the
    task classes; every key it does not set comes from the ``scheduling`` section, so both
    studies share the methods, the labels, the metric definitions and the rounding.
    """
    track = {**cfg["scheduling"], **cfg["scheduling_llm"]}
    summary = read_rows(paths.reference / track["summary_csv"])
    metrics = [MetricCfg(**entry) for entry in track["metrics"]]
    study = LLM_WORKLOAD
    core, value = _comparison_blocks(track, summary, metrics, paths, figures, study)
    blocks = {f"llm_{block_id}": text for block_id, text in core.items()}
    blocks["llm_all_methods"] = _scheduling_all_methods(summary, track, metrics, study.note)
    class_summary = read_rows(paths.reference / track["class_summary_csv"])
    blocks["llm_by_class"] = _llm_by_class(track, class_summary, metrics, paths, figures, study)
    blocks["llm_findings"] = (
        study.note.strip()
        + "\n\n"
        + _scheduling_findings(track, metrics, value)
        + "\n"
        + _llm_class_findings(track, class_summary, metrics)
    )
    blocks["llm_workload_profile"] = _llm_workload_profile(track)
    blocks["llm_guardrails"] = _llm_guardrails(track, summary, class_summary, study)
    run = Path(track["summary_csv"]).parent.as_posix()
    blocks["llm_tail_analysis"] = _scheduling_tail(track, paths, run=run, note=study.note)
    blocks["llm_ablation"] = _llm_ablation(track, paths, summary, class_summary, metrics, study)
    return blocks


def _class_metric_cfgs(track: Mapping[str, Any], metrics: Sequence[MetricCfg]) -> list[MetricCfg]:
    """Metric definitions of the per-class tables: the pooled definition with a short label."""
    by_key = {metric.key: metric for metric in metrics}
    chosen = []
    for entry in track["class_metrics"]:
        base = by_key[entry["key"]]
        chosen.append(
            MetricCfg(
                base.key,
                entry["label"],
                base.unit,
                base.higher_is_better,
                base.near_zero,
                base.digits,
                base.scale,
            )
        )
    return chosen


def _class_rows(
    track: Mapping[str, Any],
    class_summary: list[dict[str, str]],
    metrics: Sequence[MetricCfg],
    load: str,
) -> list[BeforeAfterRow]:
    """Per task class and metric: the best baseline on that metric against the After method."""
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    befores: list[str] = list(track["before_methods"])
    rows: list[BeforeAfterRow] = []
    for task_class, class_label in track["class_labels"].items():

        def value(method: str, metric: MetricCfg, _class: str = task_class) -> Measurement:
            row = find_row(class_summary, method=method, load_profile=load, task_class=_class)
            return measurement(row, metric)

        for metric in _class_metric_cfgs(track, metrics):
            candidates = [(b, value(b, metric)) for b in befores]
            usable = [(b, m) for b, m in candidates if m.finite]
            if usable:
                chooser = max if metric.higher_is_better else min
                pick = chooser(usable, key=lambda item: item[1].mean)
            else:
                pick = candidates[0]
            spec = MetricSpec(
                metric.key,
                f"{class_label}: {metric.label}",
                metric.unit,
                metric.higher_is_better,
                metric.near_zero,
                metric.digits,
            )
            rows.append(
                make_row(spec, labels[pick[0]], pick[1], labels[after], value(after, metric))
            )
    return rows


def _llm_by_class(
    track: Mapping[str, Any],
    class_summary: list[dict[str, str]],
    metrics: Sequence[MetricCfg],
    paths: Paths,
    figures: bool,
    study: Study,
) -> str:
    """Per-task-class tables (and chart): Before / After against the best baseline, then every
    method for the pooled and the heavy load profile."""
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    pooled: str = track["load_profile"]
    class_metric_cfgs = _class_metric_cfgs(track, metrics)
    rows = _class_rows(track, class_summary, metrics, pooled)
    csv_path = paths.before_after / f"{study.stem}_by_class.csv"
    write_rows_csv(rows, csv_path, track=f"{study.stem}_by_class")
    methods = (
        list(track["before_methods"]) + [track["after_method"]] + list(track["reference_methods"])
    )
    parts = [
        f"Source label: {_label(rows)}. {study.note}The same run, with every metric computed "
        "separately for the tasks of one class. For each class and metric the Before method is the "
        f"**best of the four baselines on that metric**; After = {labels[after]}. Load profiles "
        f"light, medium and heavy are pooled. {_seed_note(rows)} A workload that happens to "
        "contain no task of a class contributes nothing to that class. Underlying CSV: "
        f"`{_rel(csv_path)}`.\n",
        render_markdown(rows),
    ]
    heavy = "heavy" if "heavy" in track["per_load_profiles"] else track["per_load_profiles"][-1]
    for load, heading in ((pooled, "load profiles pooled"), (heavy, f"{heavy} load only")):
        header = ["Method"]
        for class_label in track["class_labels"].values():
            header.extend(f"{class_label}: {m.label} ({m.unit})" for m in class_metric_cfgs)
        body = []
        for method in methods:
            cells = [labels[method]]
            for task_class in track["class_labels"]:
                row = find_row(
                    class_summary, method=method, load_profile=load, task_class=task_class
                )
                cells.extend(format_value(measurement(row, m), m.digits) for m in class_metric_cfgs)
            body.append(cells)
        parts.append(
            f"**Every method per task class, {heading}** (mean ± sample standard deviation across seeds):\n"
        )
        parts.append(_table(header, body))
    if figures:
        _llm_class_chart(track, class_summary, metrics, pooled, paths, rows, study)
    return "\n".join(parts)


def _llm_class_chart(
    track: Mapping[str, Any],
    class_summary: list[dict[str, str]],
    metrics: Sequence[MetricCfg],
    load: str,
    paths: Paths,
    rows: Sequence[BeforeAfterRow],
    study: Study,
) -> None:
    from src.common.plotting import Bar, BeforeAfterPanel, before_after_figure

    order = (
        [(m, "before") for m in track["before_methods"]]
        + [(track["after_method"], "after")]
        + [(m, "reference") for m in track["reference_methods"]]
    )
    panels = []
    for task_class, class_label in track["class_labels"].items():
        for metric in _class_metric_cfgs(track, metrics):
            bars = []
            for method, role in order:
                row = find_row(
                    class_summary, method=method, load_profile=load, task_class=task_class
                )
                measured = measurement(row, metric)
                bars.append(
                    Bar(
                        CHART_LABELS.get(method, method),
                        role,
                        measured.mean if measured.available else None,
                        measured.std,
                    )
                )
            axis = metric.label[:1].upper() + metric.label[1:]
            panels.append(
                BeforeAfterPanel(
                    f"{class_label}: {metric.label}",
                    metric.unit,
                    metric.spec.direction,
                    tuple(bars),
                    metric.digits,
                    ylabel=f"{axis} ({metric.unit})",
                )
            )
    before_after_figure(
        panels,
        paths.before_after / f"{study.stem}_by_class.png",
        f"{track['title']}, per task class: Before / After",
        _label(rows),
        caption=(
            "One row of panels per task class. Bars: mean across seeds; error bars: sample standard "
            f"deviation across seeds. {_seed_note(rows)} Load profiles pooled. Grey = references that are "
            "neither Before nor After methods: preemptive SRTF and the same agent with the guardrail "
            f"overrides off. {study.chart_note}"
        ),
        columns=len(track["class_metrics"]),
    )


def _llm_class_findings(
    track: Mapping[str, Any],
    class_summary: list[dict[str, str]],
    metrics: Sequence[MetricCfg],
) -> str:
    """Bullet list per task class; every number comes from class_summary.csv."""
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    pooled: str = track["load_profile"]
    rows = _class_rows(track, class_summary, metrics, pooled)
    if not any(row.status != "tbd" for row in rows):
        return f"- {TBD} {TARGET_TBD}: the per-class summary of this study has not been produced.\n"
    lines = ["Per task class (load profiles pooled, best baseline on each metric):", ""]
    wins = 0
    scored = 0
    for row in rows:
        cells = row_cells(row)
        if row.improvement_pct is None:
            verdict = f"no percentage ({cells['Improvement %']})"
        else:
            scored += 1
            wins += row.improvement_pct > 0
            word = "better" if row.improvement_pct > 0 else "worse"
            verdict = f"Improvement {cells['Improvement %']} ({word})"
        lines.append(
            f"- **{row.metric.label}** ({row.metric.direction.lower()}): {labels[after]} "
            f"{cells['After Value']} {row.metric.unit}; best baseline {row.before_method} "
            f"{cells['Before Value']} {row.metric.unit}; {verdict}. {REPRODUCED}"
        )
    lines.append(
        f"- Against the best baseline per class and metric, {labels[after]} is better in {wins} of "
        f"{scored} comparisons with a computable percentage. {REPRODUCED}"
    )
    references = [
        m
        for m in track["reference_methods"]
        if find_row(class_summary, method=m, load_profile=pooled) is not None
    ]
    if references:
        lines += ["", "References that are not Before methods, per task class (pooled):", ""]
    class_metric_cfgs = _class_metric_cfgs(track, metrics)
    for reference in references:
        for task_class, class_label in track["class_labels"].items():
            parts = []
            for metric in class_metric_cfgs:
                ref = measurement(
                    find_row(
                        class_summary, method=reference, load_profile=pooled, task_class=task_class
                    ),
                    metric,
                )
                mine = measurement(
                    find_row(
                        class_summary, method=after, load_profile=pooled, task_class=task_class
                    ),
                    metric,
                )
                parts.append(
                    f"{metric.label} {format_value(ref, metric.digits)} versus "
                    f"{format_value(mine, metric.digits)} {metric.unit} for {labels[after]}"
                )
            lines.append(
                f"- {labels[reference]}, {class_label.lower()}: "
                + "; ".join(parts)
                + f". {REPRODUCED}"
            )
    return "\n".join(lines) + "\n"


def _llm_guardrails(
    track: Mapping[str, Any],
    summary: list[dict[str, str]],
    class_summary: list[dict[str, str]],
    study: Study,
) -> str:
    """How often each override rule fired for the After method, next to the turnaround of the
    same agent with and without the overrides, and the tasks per class that waited longer than
    the starvation threshold; every number comes from summary.csv and class_summary.csv."""
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    unguarded = "ddqn_unguarded"
    counters = [
        MetricCfg("guardrail_starvation_triggers", "Starvation overrides", "per episode", False, 0.0, 2, 1.0),
        MetricCfg("guardrail_slo_fallback_activations", "SLO-fallback activations", "per episode", False, 0.0, 2, 1.0),
        MetricCfg("guardrail_q_divergence_latches", "Q-divergence latches", "per episode", False, 0.0, 2, 1.0),
        MetricCfg("guardrail_overrides", "Decisions overridden", "per episode", False, 0.0, 2, 1.0),
    ]  # fmt: skip
    turnaround = MetricCfg("avg_turnaround_ms", "Turnaround", "ms", False, 1e-9, 1, 1.0)
    header = (
        ["Load"]
        + [f"{m.label} ({m.unit})" for m in counters]
        + [f"Turnaround, {labels[after]} (ms)", f"Turnaround, {labels[unguarded]} (ms)"]
    )
    body = []
    for load in [*track["per_load_profiles"], track["load_profile"]]:
        guarded = find_row(summary, method=after, load_profile=load)
        plain = find_row(summary, method=unguarded, load_profile=load)
        body.append(
            [load]
            + [format_value(measurement(guarded, m), m.digits) for m in counters]
            + [
                format_value(measurement(guarded, turnaround), turnaround.digits),
                format_value(measurement(plain, turnaround), turnaround.digits),
            ]
        )
    measured = any(cell != TBD for cells in body for cell in cells[1:])
    starved = MetricCfg("starvation_count", "Starved tasks", "per episode", False, 0.05, 2, 1.0)
    class_header = ["Load"]
    for class_label in track["class_labels"].values():
        class_header.append(f"{class_label}, {labels[after]}")
        class_header.append(f"{class_label}, {labels[unguarded]}")
    class_body = []
    for load in [*track["per_load_profiles"], track["load_profile"]]:
        cells = [load]
        for task_class in track["class_labels"]:
            for method in (after, unguarded):
                row = find_row(
                    class_summary, method=method, load_profile=load, task_class=task_class
                )
                cells.append(format_value(measurement(row, starved), starved.digits))
        class_body.append(cells)
    return (
        f"Source label: {REPRODUCED if measured else TARGET_TBD}. {study.note}Counts are for "
        f"{labels[after]}: how often each override rule fired in one evaluation workload, mean ± "
        "sample standard deviation across seeds. The last two columns put the turnaround of that "
        "agent next to the same trained network evaluated with the three override rules off; "
        f"`{track['load_profile']}` pools the load profiles.\n\n"
        + _table(header, body)
        + "\n**Tasks that waited longer than the starvation threshold, per task class** (tasks "
        "per evaluation workload whose longest continuous wait exceeded "
        "`metrics.starvation_threshold_ms`; mean ± sample standard deviation across seeds):\n\n"
        + _table(class_header, class_body)
    )


UNGUARDED = "ddqn_unguarded"
SRTF = "srtf"


def _paired_gap(
    raw: list[dict[str, str]], key: str, load: str, after: str, pooled: str
) -> tuple[float, float, int, int] | None:
    """Per seed, ``after`` minus the same network with the override rules off, for one metric.

    Both values are the mean over that seed's evaluation workloads of ``load`` (every load for
    the pooled row), which are the same workloads for the two methods. Returns the mean of the
    per-seed differences, their sample standard deviation, the number of seeds with a positive
    difference and the number of seeds; ``None`` when a side is missing.
    """
    import numpy as np

    per_seed: dict[int, dict[str, list[float]]] = {}
    for row in raw:
        if row["method"] not in (after, UNGUARDED):
            continue
        if load != pooled and row["load_profile"] != load:
            continue
        per_seed.setdefault(int(row["seed"]), {}).setdefault(row["method"], []).append(
            float(row[key])
        )
    gaps = [
        float(np.mean(values[after]) - np.mean(values[UNGUARDED]))
        for _, values in sorted(per_seed.items())
        if after in values and UNGUARDED in values
    ]
    if not gaps:
        return None
    spread = float(np.std(gaps, ddof=1)) if len(gaps) > 1 else float("nan")
    return float(np.mean(gaps)), spread, sum(gap > 0 for gap in gaps), len(gaps)


def _seeds_better(
    reference_rows: list[dict[str, str]],
    variant_rows: list[dict[str, str]],
    metric: MetricCfg,
    method: str,
    pooled: str,
    **match: str,
) -> str:
    """In how many seeds ``method`` has a better per-seed mean of ``metric`` in the variant.

    Both runs use the same seeds and the same evaluation workloads, so the comparison is
    paired by seed; the per-seed mean is taken over that seed's rows matching ``match``.
    """
    import numpy as np

    def per_seed(rows: list[dict[str, str]]) -> dict[int, float]:
        values: dict[int, list[float]] = {}
        for row in rows:
            if row["method"] != method:
                continue
            if any(v != pooled and row.get(k) != v for k, v in match.items()):
                continue
            number = to_float(row.get(metric.key))
            if number is not None:
                values.setdefault(int(row["seed"]), []).append(number)
        return {seed: float(np.mean(items)) for seed, items in values.items()}

    before, after_values = per_seed(reference_rows), per_seed(variant_rows)
    seeds = sorted(set(before) & set(after_values))
    if not seeds:
        return TBD
    if metric.higher_is_better:
        better = sum(after_values[seed] > before[seed] for seed in seeds)
    else:
        better = sum(after_values[seed] < before[seed] for seed in seeds)
    return f"{better} of {len(seeds)}"


def _gap_cell(gap: tuple[float, float, int, int] | None, digits: int) -> str:
    return TBD if gap is None else f"{gap[0]:+.{digits}f} ± {gap[1]:.{digits}f}"


def _yaml_value(value: Any) -> str:
    """A config value the way the YAML file spells it."""
    if value is None:
        return "null"
    return str(value).lower() if isinstance(value, bool) else str(value)


def _llm_ablation(
    track: Mapping[str, Any],
    paths: Paths,
    summary: list[dict[str, str]],
    class_summary: list[dict[str, str]],
    metrics: Sequence[MetricCfg],
    study: Study,
) -> str:
    """The post hoc variant of the LLM-style study next to its reference run.

    Three parts: the agent with the override rules on and off in both runs, the reading rule of
    ``scheduling_llm.ablation`` applied to those gaps, and the After method of the variant next
    to the reference run and the best baseline. Every number comes from the CSV files of the
    two runs; the verdict is computed from the rule, not written by hand.
    """
    rule: Mapping[str, Any] = track["ablation"]
    name: str = rule["name"]
    check_load: str = rule["check_load_profile"]
    limit = float(rule["max_gap_ratio"])
    labels: Mapping[str, str] = track["method_labels"]
    after: str = track["after_method"]
    pooled: str = track["load_profile"]
    run = Path(track["summary_csv"]).parent
    variant_dir = paths.reference / run / "ablations" / name
    profile = load_config(REPO_ROOT / track["workload_config"])
    overrides: Mapping[str, Any] = (profile.get("ablations") or {}).get(name, {})
    changes = []
    for dotted, new_value in overrides.items():
        current: Any = profile
        for part in dotted.split("."):
            current = current[part]
        changes.append(
            f"`{dotted}` = `{_yaml_value(new_value)}` (reference run: `{_yaml_value(current)}`)"
        )
    intro = (
        f"{study.note}Post hoc variant `{name}`: {'; '.join(changes)}. It was added after the "
        "reference results of this profile had been seen and is not part of the Before / After "
        "tables above. The agent is retrained on the same seeds with this one setting changed, in "
        "training and in evaluation, and is evaluated on the same paired workloads, with the "
        "override rules on and with them off."
    )
    if not (variant_dir / "summary.csv").is_file():
        return f"Source label: {TARGET_TBD}. {intro} {TBD}: the variant has not been run.\n"
    variant = read_rows(variant_dir / "summary.csv")
    variant_classes = read_rows(variant_dir / "class_summary.csv")
    raws = {
        "Reference run": read_rows(paths.reference / run / "raw_episodes.csv"),
        f"Variant `{name}`": read_rows(variant_dir / "raw_episodes.csv"),
    }
    summaries = {"Reference run": summary, f"Variant `{name}`": variant}
    loads = [check_load, pooled]
    turnaround = MetricCfg("avg_turnaround_ms", "Turnaround", "ms", False, 1e-9, 1, 1.0)
    starved = MetricCfg("starvation_count", "Starved tasks", "per episode", False, 0.05, 2, 1.0)
    counters = [
        MetricCfg("guardrail_starvation_triggers", "Starvation overrides", "per episode", False, 0.0, 2, 1.0),
        MetricCfg("guardrail_overrides", "Decisions overridden", "per episode", False, 0.0, 2, 1.0),
    ]  # fmt: skip

    def on_off_table(metric: MetricCfg, with_counters: bool) -> str:
        header = ["Run", "Load"]
        if with_counters:
            header += [f"{m.label} ({m.unit})" for m in counters]
        header += ["Rules on", "Rules off", "Gap, on − off", "Seeds with a higher value with the rules on"]  # fmt: skip
        body = []
        for run_label, rows in summaries.items():
            for load in loads:
                guarded = find_row(rows, method=after, load_profile=load)
                plain = find_row(rows, method=UNGUARDED, load_profile=load)
                gap = _paired_gap(raws[run_label], metric.key, load, after, pooled)
                cells = [run_label, load]
                if with_counters:
                    cells += [format_value(measurement(guarded, m), m.digits) for m in counters]
                cells += [
                    format_value(measurement(guarded, metric), metric.digits),
                    format_value(measurement(plain, metric), metric.digits),
                    _gap_cell(gap, metric.digits),
                    TBD if gap is None else f"{gap[2]} of {gap[3]}",
                ]
                body.append(cells)
        return _table(header, body)

    verdict_body = []
    supported = []
    for metric, quantity in (
        (turnaround, "Turnaround (ms)"),
        (starved, "Tasks waiting past the starvation threshold (per episode)"),
    ):
        reference_gap = _paired_gap(raws["Reference run"], metric.key, check_load, after, pooled)
        variant_gap = _paired_gap(raws[f"Variant `{name}`"], metric.key, check_load, after, pooled)
        if reference_gap is None or variant_gap is None or reference_gap[0] <= 0:
            verdict_body.append([quantity, _gap_cell(reference_gap, metric.digits),
                                 _gap_cell(variant_gap, metric.digits), "not applicable", "not applicable"])  # fmt: skip
            continue
        ratio = variant_gap[0] / reference_gap[0]
        supported.append(ratio < limit)
        verdict_body.append([
            quantity, f"{reference_gap[0]:+.{metric.digits}f}", f"{variant_gap[0]:+.{metric.digits}f}",
            f"{ratio:.2f}", "yes" if ratio < limit else "no",
        ])  # fmt: skip
    if not supported:
        verdict = "not applicable (the reference run shows no gap to explain)"
    elif all(supported):
        verdict = "supported"
    elif any(supported):
        verdict = "partly supported"
    else:
        verdict = "not supported"

    befores: list[str] = list(track["before_methods"])

    def best_baseline(rows: list[dict[str, str]], metric: MetricCfg, **match: str):
        candidates = [(b, measurement(find_row(rows, method=b, **match), metric)) for b in befores]
        usable = [(b, m) for b, m in candidates if m.finite]
        if not usable:
            return candidates[0]
        return (max if metric.higher_is_better else min)(usable, key=lambda item: item[1].mean)

    whole_rows: list[BeforeAfterRow] = []
    whole_body = []

    def add(
        scope: str, metric: MetricCfg, ref_rows, var_rows, ref_raw, var_raw, **match: str
    ) -> None:
        base_name, base = best_baseline(ref_rows, metric, **match)
        reference = measurement(find_row(ref_rows, method=after, **match), metric)
        changed = measurement(find_row(var_rows, method=after, **match), metric)
        spec = MetricSpec(metric.key, f"{metric.label}, {scope}", metric.unit,
                          metric.higher_is_better, metric.near_zero, metric.digits)  # fmt: skip
        versus_reference = make_row(spec, "Reference run", reference, f"Variant {name}", changed)
        versus_baseline = make_row(spec, labels[base_name], base, f"Variant {name}", changed)
        whole_rows.append(versus_reference)
        others = [
            format_value(measurement(find_row(ref_rows, method=m, **match), metric), metric.digits)
            for m in (SRTF, UNGUARDED)
        ]
        whole_body.append([
            f"{metric.label} ({metric.unit})", scope,
            f"{labels[base_name]} {format_value(base, metric.digits)}", *others,
            format_value(reference, metric.digits), format_value(changed, metric.digits),
            row_cells(versus_reference)["Improvement %"],
            _seeds_better(ref_raw, var_raw, metric, after, pooled, **match),
            row_cells(versus_baseline)["Improvement %"],
        ])  # fmt: skip

    episodes = list(raws.values())
    class_episodes = [
        read_rows(paths.reference / run / "class_episodes.csv"),
        read_rows(variant_dir / "class_episodes.csv"),
    ]
    for metric in metrics:
        add("all loads", metric, summary, variant, *episodes, load_profile=pooled)
    for load in track["per_load_profiles"]:
        add(f"{load} load", metrics[0], summary, variant, *episodes, load_profile=load)
    class_metric_cfgs = _class_metric_cfgs(track, metrics)
    for task_class, class_label in track["class_labels"].items():
        for metric in class_metric_cfgs:
            wide = MetricCfg(metric.key, metric.label[:1].upper() + metric.label[1:], metric.unit,
                             metric.higher_is_better, metric.near_zero, metric.digits, metric.scale)  # fmt: skip
            add(f"{class_label.lower()}, all loads", wide, class_summary, variant_classes,
                *class_episodes, load_profile=pooled, task_class=task_class)  # fmt: skip
    csv_path = paths.before_after / f"{study.stem}_ablation.csv"
    write_rows_csv(whole_rows, csv_path, track=f"{study.stem}_ablation")
    return (
        f"Source label: {REPRODUCED}. {intro} Mean ± sample standard deviation across seeds. The "
        "gap is the per-seed difference between the agent with the override rules on and the same "
        "trained network with them off, on identical workloads: a positive gap means the rules "
        f"cost that much. `{pooled}` pools the load profiles.\n\n"
        f"**Turnaround of {labels[after]} with the override rules on and off (ms):**\n\n"
        + on_off_table(turnaround, True)
        + "\n**Tasks that waited longer than the starvation threshold** (tasks per evaluation "
        "workload whose longest continuous wait exceeded `metrics.starvation_threshold_ms`):\n\n"
        + on_off_table(starved, False)
        + f"\n**Reading rule, fixed before the variant was run** (`scheduling_llm.ablation` in "
        f"`configs/before_after.yaml`). On the `{check_load}` load profile, the explanation — the "
        "length of the forced dispatch is what makes the override rules costly on this profile — "
        "counts as supported on a quantity when the gap in the variant is smaller than "
        f"{limit:g} × the gap in the reference run:\n\n"
        + _table(["Quantity", "Gap, reference run", "Gap, variant", "Variant gap ÷ reference gap",
                  f"Below {limit:g}?"], verdict_body)  # fmt: skip
        + f"\n**By this rule the explanation is {verdict}.** {REPRODUCED}\n\n"
        f"**{labels[after]} in the variant, next to the reference run, the best baseline and the "
        "two references.** The baselines and SRTF do not use this setting, so their values are "
        "those of the reference run; the guardrail-overrides-off column is the network of the "
        "reference run evaluated with the rules off. In the two percentage columns a positive "
        "value means the variant is better, a negative value worse. Both runs use the same seeds "
        "and the same evaluation workloads, so the column between them counts the seeds in which "
        "the per-seed mean of the variant is the better one. Underlying CSV (variant against "
        f"reference run): `{_rel(csv_path)}`.\n\n"
        + _table(["Metric", "Scope", "Best baseline", labels[SRTF],
                  f"{labels[UNGUARDED]}, reference run", f"{labels[after]}, reference run",
                  f"{labels[after]}, variant", "Variant versus reference run",
                  "Seeds in which the variant is better", "Variant versus best baseline"],
                 whole_body)  # fmt: skip
    )


def _llm_workload_profile(track: Mapping[str, Any]) -> str:
    """The task classes of the profile (from its config) and the mix the generator produced
    for the evaluation workloads of the reporting seeds."""
    import numpy as np

    from src.scheduler.config import load_scheduler_config, priority_weights_for
    from src.scheduler.training import make_eval_workloads

    config_path = REPO_ROOT / track["workload_config"]
    if not config_path.is_file():
        return f"{TBD} {TARGET_TBD}: `{track['workload_config']}` does not exist.\n"
    cfg = load_scheduler_config(config_path)
    class_labels: Mapping[str, str] = track["class_labels"]
    work = cfg.workload

    def span(low: float, high: float, unit: str) -> str:
        return f"{low:g} to {high:g} {unit}"

    header = ["Setting", *[class_labels.get(name, name) for name in work.task_types]]
    settings = [
        ("Config key under `workload.task_types`", lambda n, t: f"`{n}`"),
        ("Share of tasks (mixture weight)", lambda n, t: f"{t.weight:g}"),
        (
            "Compute demand per task",
            lambda n, t: f"lognormal, median {t.cpu_median_ms:g} ms, sigma {t.cpu_sigma:g}, "
            f"clipped to {span(t.cpu_min_ms, t.cpu_max_ms, 'ms')}",
        ),
        ("Waits inside a task", lambda n, t: f"{t.io_ops_min} to {t.io_ops_max}"),
        ("Length of one wait", lambda n, t: span(t.io_wait_min_ms, t.io_wait_max_ms, "ms")),
        ("Memory footprint", lambda n, t: span(t.memory_min_mb, t.memory_max_mb, "MB")),
        (
            "Deadline",
            lambda n, t: f"arrival + {t.slo_factor:g} × (compute + waits) + "
            f"{work.slo_slack_ms:g} ms",
        ),
        (
            "Priority level weights (level 0 lowest)",
            lambda n, t: "[" + ", ".join(f"{w:g}" for w in priority_weights_for(work, n)) + "]",
        ),
    ]
    body = [
        [name, *[render(n, t) for n, t in work.task_types.items()]] for name, render in settings
    ]
    parts = [
        f"Every value in this table is read from `{track['workload_config']}`, where each key "
        "carries the tag `[Assumption — not in paper]`: the values were chosen by hand to give the "
        "mix its shape and were not measured on an LLM system or fitted to a trace. Machine: one "
        f"processor, {cfg.machine.memory_capacity_mb:g} MB of memory, "
        f"{cfg.machine.context_switch_ms:g} ms per context switch (inherited from "
        "`configs/scheduler_ddqn.yaml`).\n",
        _table(header, body),
    ]

    stats_header = [
        "Load profile",
        "Task class",
        "Tasks per workload",
        "Share of tasks",
        "Share of compute demand",
        "Compute demand per task (ms)",
        "Memory per task (MB)",
    ]
    stats_body = []
    workloads = [w for seed in cfg.seeds for w in make_eval_workloads(cfg, int(seed))]
    loads = [*cfg.evaluation.load_profiles, "all"]
    for load in loads:
        chosen = [w for w in workloads if load == "all" or w.load_profile == load]
        total_tasks = sum(len(w.tasks) for w in chosen)
        total_work = sum(t.total_cpu_ms for w in chosen for t in w.tasks)
        for name in work.task_types:
            tasks = [t for w in chosen for t in w.tasks if t.task_type == name]
            if not tasks:
                continue
            class_work = sum(t.total_cpu_ms for t in tasks)
            stats_body.append(
                [
                    load,
                    class_labels.get(name, name),
                    f"{len(tasks) / len(chosen):.1f}",
                    f"{100.0 * len(tasks) / total_tasks:.1f}%",
                    f"{100.0 * class_work / total_work:.1f}%",
                    f"{class_work / len(tasks):.1f}",
                    f"{float(np.mean([t.memory_mb for t in tasks])):.0f}",
                ]
            )
    parts.append(
        f"**The mix the generator produced** {REPRODUCED} — computed from the "
        f"{len(workloads)} evaluation workloads of the reporting seeds "
        f"({', '.join(str(seed) for seed in cfg.seeds)}; {cfg.evaluation.episodes_per_load} "
        "workloads per load profile and seed); `all` pools the load profiles. These are properties "
        "of the generated input, not results of a scheduler.\n"
    )
    parts.append(_table(stats_header, stats_body))
    return "\n".join(parts)


# --------------------------------------------------------------------------------------
# blocks that do not depend on the Before / After definition
# --------------------------------------------------------------------------------------


def build_static(paths: Paths) -> dict[str, str]:
    """Config listings, CSV schemas, state / action tables, run information."""
    blocks: dict[str, str] = {}
    for config_path in sorted((REPO_ROOT / "configs").rglob("*.yaml")):
        block_id = "config_" + config_path.stem
        blocks[block_id] = (
            f"`{_rel(config_path)}` (verbatim; comments carry the provenance tag of every key):\n\n"
            f"```yaml\n{config_path.read_text(encoding='utf-8').rstrip()}\n```\n"
        )
    blocks["csv_schemas"] = _csv_schemas(paths)
    blocks["reference_run_info"] = _run_info(paths)
    blocks.update(_code_tables())
    blocks.update(_diagram_blocks())
    return blocks


DIAGRAM_FILES = {
    "diagram_system_overview": "01-system-overview.md",
    "diagram_scheduler_detail": "02-scheduler-detail.md",
    "diagram_experiment_flow": "03-experiment-flow.md",
    "diagram_deployment_sketch": "04-deployment-sketch.md",
}

REFERENCE_RUNS = ("scheduler", "scheduler_llm")


def _code_tables() -> dict[str, str]:
    """Tables generated from constants in the code, so the docs cannot drift from it."""
    from src.scheduler import env as scheduler_env

    return {
        "scheduler_state_table": scheduler_env.observation_table_markdown().rstrip("\n") + "\n",
        "scheduler_action_table": scheduler_env.action_table_markdown().rstrip("\n") + "\n",
    }


def _diagram_blocks() -> dict[str, str]:
    """The first Mermaid block of each architecture file, so every document embeds the same one."""
    blocks: dict[str, str] = {}
    for block_id, name in DIAGRAM_FILES.items():
        path = REPO_ROOT / "docs" / "architecture" / name
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        start = text.find("```mermaid")
        end = text.find("```", start + 10) if start >= 0 else -1
        if start < 0 or end < 0:
            blocks[block_id] = (
                f"Diagram `docs/architecture/{name}` has not been written yet. {TARGET_TBD}\n"
            )
            continue
        blocks[block_id] = text[start : end + 3] + "\n"
    return blocks


def _csv_schemas(paths: Paths) -> str:
    """Schema table and header-only templates, read from the reference run's own CSV files."""
    body = []
    ensure_dir(paths.templates)
    for csv_path in sorted(paths.reference.rglob("*.csv")):
        relative = csv_path.relative_to(paths.reference)
        if relative.parts[0] in ("generated", "before_after") and relative.parts[0] == "generated":
            continue
        if "figures" in relative.parts or "ablations" in relative.parts:
            continue
        with csv_path.open("r", encoding="utf-8") as handle:
            header = handle.readline().strip()
        if not header:
            continue
        template = paths.templates / ("__".join(relative.parts))
        template.write_text(header + "\n", encoding="utf-8")
        body.append(
            [f"`{relative.as_posix()}`", ", ".join(f"`{name}`" for name in header.split(","))]
        )
    if not body:
        return f"{TBD} {TARGET_TBD}: no reference run found, so no CSV schema can be listed yet.\n"
    return (
        "Column lists are read from the header line of each CSV in `experiments/results/reference/`; "
        "header-only copies are in `experiments/results/templates/`.\n\n"
        + _table(["File", "Columns"], body)
    )


def _run_info(paths: Paths) -> str:
    body = []
    for name in REFERENCE_RUNS:
        meta_path = paths.reference / name / "metadata.json"
        if not meta_path.is_file():
            body.append([name, TBD, TBD, TBD, TBD])
            continue
        meta = read_json(meta_path)
        environment = meta.get("environment", {})
        packages = environment.get("packages", {})
        shown = ", ".join(
            f"{k} {v}"
            for k, v in packages.items()
            if v != "not installed" and k in TRACKED_PACKAGES
        )
        seeds = ", ".join(str(seed) for seed in meta.get("seeds", []))
        extra = meta.get("extra", {}) or {}
        runtime = extra.get("wall_clock_seconds")
        runtime_text = (
            f"{float(runtime):.0f} s with {extra.get('workers', '?')} worker processes"
            if runtime
            else "not recorded"
        )
        body.append([
            name, meta.get("created_utc", "?"), seeds,
            f"Python {environment.get('python', '?')} on {environment.get('platform', '?')}; {shown}", runtime_text,
        ])  # fmt: skip
    return _table(
        ["Reference run", "Created (UTC)", "Seeds", "Environment", "Wall-clock time"], body
    )


# --------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Before / After definitions")
    parser.add_argument("--no-figures", action="store_true", help="write tables and CSV only")
    args = parser.parse_args(argv)
    setup_logging("INFO")
    cfg = load_config(args.config)
    paths = Paths(
        reference=REPO_ROOT / cfg["reference_root"],
        generated=ensure_dir(REPO_ROOT / cfg["generated_dir"]),
        before_after=ensure_dir(REPO_ROOT / cfg["before_after_dir"]),
        templates=REPO_ROOT / cfg["templates_dir"],
    )
    figures = not args.no_figures
    if figures:
        from src.common.plotting import use_headless_backend

        use_headless_backend()
    blocks: dict[str, str] = {}
    blocks.update(build_scheduling(cfg, paths, figures))
    blocks.update(build_llm_workload(cfg, paths, figures))
    blocks.update(build_static(paths))
    for block_id, text in sorted(blocks.items()):
        (paths.generated / f"{block_id}.md").write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    LOGGER.info("wrote %d generated blocks to %s", len(blocks), _rel(paths.generated))
    LOGGER.info("Before / After CSV and charts are in %s", _rel(paths.before_after))
    return 0


if __name__ == "__main__":
    sys.exit(main())
