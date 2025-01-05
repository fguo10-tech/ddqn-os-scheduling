"""Figures for one scheduler benchmark run directory.

Usage::

    python -m experiments.plot_scheduler --run-dir experiments/results/runs/scheduler \\
        [--title "Scheduler benchmark"]

Writes into ``<run-dir>/figures/`` (each PNG next to a same-named CSV with the plotted
numbers):

* ``metrics_<load>.png`` for every load profile and ``all``: average turnaround ("task
  completion time"), throughput, windowed throughput, response time and waiting time by
  method, one panel per metric. Baselines are drawn in the "Before" colour, the guarded
  Double DQN in the "After" colour, and the SRTF reference and the unguarded ablation in
  the reference colour.
  Error bars are the sample standard deviation across seeds.
* ``training_reward.png``: training episode return, mean ± std across seeds, smoothed with
  a trailing moving average of ``--smooth`` episodes.
* ``guardrail_triggers.png``: mean guardrail trigger counts per evaluation episode of the
  guarded agent, by load profile.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from src.common.io import ensure_dir, read_csv, read_json, write_csv
from src.common.labels import REPRODUCED
from src.common.logging_utils import get_logger, setup_logging
from src.common.metrics import mean_std
from src.common.plotting import (
    AFTER_COLOR,
    Bar,
    BeforeAfterPanel,
    apply_style,
    bar_panel,
    before_after_figure,
    line_with_band,
    save_figure,
    use_headless_backend,
)

LOGGER = get_logger("experiments.plot_scheduler")

METRIC_PANELS = (
    ("avg_turnaround_ms", "Avg completion (turnaround) time", "ms", "Lower is better", 1),
    ("throughput_tasks_per_s", "Throughput", "tasks/s", "Higher is better", 2),
    ("windowed_throughput_tasks_per_s", "Windowed throughput", "tasks/s", "Higher is better", 2),
    ("avg_response_ms", "Avg response time", "ms", "Lower is better", 1),
    ("avg_waiting_ms", "Avg waiting time", "ms", "Lower is better", 1),
)
"""(summary metric, title, unit, direction, digits) of the per-load metric figures."""

GUARDRAIL_PANELS = (
    ("guardrail_starvation_triggers", "Starvation overrides"),
    ("guardrail_slo_fallback_activations", "SLO fallback activations"),
    ("guardrail_q_divergence_latches", "Q-divergence latches"),
    ("guardrail_overrides", "Decisions overridden"),
)
METRIC_CSV_FIELDS = ("load_profile", "method", "role", "metric", "unit", "mean", "std", "n_seeds")
TRAINING_CSV_FIELDS = ("episode", "return_mean", "return_std", "n_seeds", "smooth_window")
GUARDRAIL_CSV_FIELDS = ("load_profile", "counter", "mean_per_episode", "std", "n_seeds")

AGENT = "ddqn"
ABLATION = "ddqn_unguarded"
REFERENCES = ("srtf", ABLATION)
"""Methods drawn in the reference colour (not part of the Before / After comparison)."""


def _role(method: str) -> str:
    if method == AGENT:
        return "after"
    if method in REFERENCES:
        return "reference"
    return "before"


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _caption(run_dir: Path) -> str:
    meta_path = run_dir / "metadata.json"
    if not meta_path.is_file():
        return ""
    meta = read_json(meta_path)
    extra = meta.get("extra", {})
    parts = [f"seeds {meta.get('seeds')}"]
    if extra.get("smoke"):
        parts.append("SMOKE RUN (tiny settings, not a result)")
    if extra.get("ablation"):
        parts.append(f"ablation {extra['ablation']}")
    parts.append("mean ± sample std across seeds; simulator study")
    return "; ".join(parts)


def plot_metrics(
    run_dir: Path, fig_dir: Path, caption: str, title: str = "Scheduler benchmark"
) -> list[Path]:
    """One small-multiples figure per load profile from ``summary.csv``."""
    summary = read_csv(run_dir / "summary.csv")
    loads: list[str] = []
    for row in summary:
        if row["load_profile"] not in loads:
            loads.append(row["load_profile"])
    written: list[Path] = []
    for load in loads:
        rows = [r for r in summary if r["load_profile"] == load]
        methods = [r["method"] for r in rows]
        order = [m for m in methods if _role(m) == "before"] + [
            m for m in (AGENT, *REFERENCES) if m in methods
        ]
        by_method = {r["method"]: r for r in rows}
        panels = []
        csv_rows = []
        for key, title, unit, direction, digits in METRIC_PANELS:
            bars = []
            for method in order:
                row = by_method[method]
                mean = _float(row.get(f"{key}_mean"))
                std = _float(row.get(f"{key}_std"))
                bars.append(Bar(method, _role(method), mean, None if math.isnan(std) else std))
                csv_rows.append(
                    {
                        "load_profile": load,
                        "method": method,
                        "role": _role(method),
                        "metric": key,
                        "unit": unit,
                        "mean": mean,
                        "std": std,
                        "n_seeds": row["n_seeds"],
                    }
                )
            panels.append(BeforeAfterPanel(title, unit, direction, tuple(bars), digits))
        path = fig_dir / f"metrics_{load}.png"
        write_csv(path.with_suffix(".csv"), csv_rows, METRIC_CSV_FIELDS)
        before_after_figure(
            panels,
            path,
            title=f"{title} — {load} load",
            source_label=REPRODUCED,
            caption="Before = textbook baselines; After = DDQN + guardrails; Reference = "
            "preemptive SRTF and DDQN with override rules off (same network and encoding). "
            + caption,
        )
        written.append(path)
    return written


def plot_training(run_dir: Path, fig_dir: Path, smooth: int, caption: str) -> Path | None:
    """Training return per episode, mean ± std across seeds."""
    log = read_csv(run_dir / "training_log.csv")
    if not log:
        LOGGER.info("training_log.csv is empty (--skip-ddqn?); no training figure")
        return None
    per_seed: dict[str, dict[int, float]] = defaultdict(dict)
    for row in log:
        per_seed[row["seed"]][int(row["episode"])] = _float(row["episode_return"])
    smoothed: dict[str, dict[int, float]] = {}
    for seed, series in per_seed.items():
        episodes = sorted(series)
        values = np.array([series[e] for e in episodes])
        out = {}
        for i, episode in enumerate(episodes):
            lo = max(0, i - smooth + 1)
            out[episode] = float(np.mean(values[lo : i + 1]))
        smoothed[seed] = out
    max_episode = max(max(s) for s in smoothed.values())
    rows = []
    for episode in range(max_episode + 1):
        values = [s[episode] for s in smoothed.values() if episode in s]
        mean, std = mean_std(values)
        rows.append(
            {
                "episode": episode,
                "return_mean": mean,
                "return_std": std,
                "n_seeds": len(values),
                "smooth_window": smooth,
            }
        )
    path = fig_dir / "training_reward.png"
    write_csv(path.with_suffix(".csv"), rows, TRAINING_CSV_FIELDS)
    import matplotlib.pyplot as plt

    apply_style()
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    line_with_band(
        ax,
        [r["episode"] for r in rows],
        [r["return_mean"] for r in rows],
        [r["return_std"] for r in rows],
        label=f"DDQN training return (trailing mean of {smooth} episodes)",
        color=AFTER_COLOR,
        marker="",
    )
    ax.set_xlabel("Training episode")
    ax.set_ylabel("Episode return (reward units)")
    ax.set_title(f"Training reward, mean ± std across seeds {REPRODUCED}", loc="left")
    ax.legend(loc="lower right")
    if caption:
        fig.text(0.01, 0.005, caption, ha="left", va="bottom", fontsize=7.5, wrap=True)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
    return save_figure(fig, path)


def plot_guardrails(run_dir: Path, fig_dir: Path, caption: str) -> Path | None:
    """Mean guardrail trigger counts per evaluation episode of the guarded agent."""
    raw = [r for r in read_csv(run_dir / "raw_episodes.csv") if r["method"] == AGENT]
    if not raw:
        LOGGER.info("no %s rows; no guardrail figure", AGENT)
        return None
    loads: list[str] = []
    for row in raw:
        if row["load_profile"] not in loads:
            loads.append(row["load_profile"])
    rows = []
    for key, _ in GUARDRAIL_PANELS:
        for load in loads:
            per_seed: dict[str, list[float]] = defaultdict(list)
            for row in raw:
                if row["load_profile"] == load:
                    per_seed[row["seed"]].append(_float(row[key]))
            mean, std = mean_std([float(np.mean(v)) for v in per_seed.values()])
            rows.append(
                {
                    "load_profile": load,
                    "counter": key,
                    "mean_per_episode": mean,
                    "std": std,
                    "n_seeds": len(per_seed),
                }
            )
    path = fig_dir / "guardrail_triggers.png"
    write_csv(path.with_suffix(".csv"), rows, GUARDRAIL_CSV_FIELDS)
    import matplotlib.pyplot as plt

    apply_style()
    fig, axes = plt.subplots(1, len(GUARDRAIL_PANELS), figsize=(3.0 * len(GUARDRAIL_PANELS), 3.4),
                             squeeze=False)  # fmt: skip
    for ax, (key, title) in zip(axes[0], GUARDRAIL_PANELS, strict=True):
        selected = [r for r in rows if r["counter"] == key]
        bar_panel(
            ax,
            [r["load_profile"] for r in selected],
            [r["mean_per_episode"] for r in selected],
            [r["std"] for r in selected],
            [AFTER_COLOR] * len(selected),
            ylabel="count per episode",
            title=title,
            digits=2,
        )
    fig.suptitle(f"Guardrail triggers of the guarded DDQN agent {REPRODUCED}", x=0.01,
                 ha="left", fontsize=11, fontweight="bold")  # fmt: skip
    if caption:
        fig.text(0.01, 0.005, caption, ha="left", va="bottom", fontsize=7.5, wrap=True)
    fig.tight_layout(rect=(0, 0.06 if caption else 0, 1, 0.93))
    return save_figure(fig, path)


def main(argv: list[str] | None = None) -> list[Path]:
    """Draw every figure for ``--run-dir``; return the PNG paths."""
    parser = argparse.ArgumentParser(description="Plot a scheduler benchmark run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--smooth", type=int, default=10, help="trailing window (episodes)")
    parser.add_argument(
        "--title",
        default="Scheduler benchmark",
        help="figure title prefix of the metric figures (name the workload profile here)",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    use_headless_backend()
    run_dir = Path(args.run_dir)
    fig_dir = ensure_dir(run_dir / "figures")
    caption = _caption(run_dir)
    written = plot_metrics(run_dir, fig_dir, caption, args.title)
    for path in (
        plot_training(run_dir, fig_dir, max(1, args.smooth), caption),
        plot_guardrails(run_dir, fig_dir, caption),
    ):
        if path is not None:
            written.append(path)
    LOGGER.info("wrote %d figures into %s", len(written), fig_dir)
    return written


if __name__ == "__main__":
    main()
