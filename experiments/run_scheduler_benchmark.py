"""Scheduler benchmark: baselines vs Double DQN (guarded) vs Double DQN (unguarded ablation).

Paired design: for each seed ``s`` the evaluation workloads ``W_s`` are generated once
(``evaluation.episodes_per_load`` per load profile, child seeds
``derive_seed(s, "eval", load, i)``), one agent is trained with seed ``s``, and every method
is evaluated on exactly ``W_s``.

Usage (from the repository root)::

    python -m experiments.run_scheduler_benchmark \\
        --config configs/scheduler_ddqn.yaml --baselines-config configs/scheduler_baselines.yaml \\
        --out experiments/results/runs/scheduler [--seeds 0 1 2 3 4] [--workers N] [--smoke] \\
        [--set key=value ...] [--skip-ddqn] [--ablation NAME] [--class-metrics]

Outputs in ``--out`` (``<out>/ablations/NAME`` with ``--ablation``): ``config_used.yaml``,
``metadata.json``, ``raw_episodes.csv``, ``training_log.csv``, ``summary.csv`` and
``checkpoints/seed_<s>.pt``. Draw the figures with ``python -m experiments.plot_scheduler
--run-dir <out>``. Results do not depend on ``--workers``.

``--class-metrics`` additionally writes ``class_episodes.csv`` (one row per seed × method ×
load profile × episode × task class) and ``class_summary.csv`` (mean ± standard deviation
across seeds per method × load profile × task class). It changes none of the other files.

``--config`` may be a workload profile that inherits from ``configs/scheduler_ddqn.yaml``,
for example ``configs/scheduler_llm_workload.yaml`` (LLM-style tasks: inference requests and
fine-tuning jobs).

Methods: the textbook baselines (``methods`` in the baselines config), the ``srtf``
reference (``reference_methods``), ``ddqn`` (guardrails on, the reported method) and
``ddqn_unguarded`` (ablation: same network and observation encoding, the three override
rules off).

Seeds 0-4 are the reporting seeds; use seeds >= 100 for development and tuning.
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import time
from pathlib import Path
from typing import Any

from src.common.config import load_config, to_dict
from src.common.io import ensure_dir, save_run_metadata, write_csv
from src.common.logging_utils import get_logger, setup_logging
from src.common.metrics import summarise_by_seed
from src.scheduler.baselines import make_policy
from src.scheduler.config import (
    BaselinesConfig,
    SchedulerConfig,
    apply_ablation,
    load_baselines_config,
    scheduler_config_from_dict,
)
from src.scheduler.training import (
    CLASS_EPISODE_FIELDS,
    CLASS_SUMMARY_METRICS,
    RAW_EPISODE_FIELDS,
    SUMMARY_METRICS,
    TRAINING_LOG_FIELDS,
    evaluate_agent,
    evaluate_policy,
    make_eval_workloads,
    train_agent,
)

LOGGER = get_logger("experiments.run_scheduler_benchmark")

DDQN_METHOD = "ddqn"
DDQN_UNGUARDED_METHOD = "ddqn_unguarded"
SUMMARY_GROUP_FIELDS = ("method", "load_profile", "n_seeds")
SUMMARY_FIELDS = (
    *SUMMARY_GROUP_FIELDS,
    *[f"{m}_{s}" for m in SUMMARY_METRICS for s in ("mean", "std")],
)
"""Columns of ``summary.csv``."""

CLASS_SUMMARY_GROUP_FIELDS = ("method", "load_profile", "task_class", "n_seeds")
CLASS_SUMMARY_FIELDS = (
    *CLASS_SUMMARY_GROUP_FIELDS,
    *[f"{m}_{s}" for m in CLASS_SUMMARY_METRICS for s in ("mean", "std")],
)
"""Columns of ``class_summary.csv`` (written with ``--class-metrics``)."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True, help="scheduler_ddqn.yaml")
    parser.add_argument("--baselines-config", required=True, help="scheduler_baselines.yaml")
    parser.add_argument("--out", default="experiments/results/runs/scheduler")
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    parser.add_argument("--skip-ddqn", action="store_true")
    parser.add_argument("--ablation", default=None)
    parser.add_argument("--no-checkpoints", action="store_true")
    parser.add_argument(
        "--class-metrics",
        action="store_true",
        help="also write class_episodes.csv and class_summary.csv (metrics per task class)",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def run_seed(job: dict[str, Any]) -> dict[str, Any]:
    """Everything for one seed: workloads, baselines, training, agent evaluation."""
    import torch

    torch.set_num_threads(1)
    cfg: SchedulerConfig = job["cfg"]
    bcfg: BaselinesConfig = job["bcfg"]
    seed = int(job["seed"])
    start = time.perf_counter()
    workloads = make_eval_workloads(cfg, seed)
    rows: list[dict[str, Any]] = []
    per_class: list[dict[str, Any]] | None = [] if job.get("class_metrics") else None
    for method in [*bcfg.methods, *bcfg.reference_methods]:
        rows.extend(
            evaluate_policy(cfg, make_policy(method, bcfg), workloads, seed, method, per_class)
        )
    baseline_seconds = time.perf_counter() - start
    log: list[dict[str, Any]] = []
    info: dict[str, Any] = {"seed": seed, "baseline_eval_seconds": baseline_seconds}
    if not job["skip_ddqn"]:
        result = train_agent(cfg, seed)
        log = result.log
        info.update(
            training_seconds=result.wall_seconds,
            training_env_steps=result.agent.env_steps,
            diverged=result.diverged,
            divergence_reason=result.divergence_reason,
        )
        eval_start = time.perf_counter()
        rows.extend(
            evaluate_agent(cfg, result.agent, workloads, seed, DDQN_METHOD, True, per_class)
        )
        rows.extend(
            evaluate_agent(
                cfg, result.agent, workloads, seed, DDQN_UNGUARDED_METHOD, False, per_class
            )
        )
        info["agent_eval_seconds"] = time.perf_counter() - eval_start
        if job["checkpoint_dir"] is not None:
            result.agent.save(Path(job["checkpoint_dir"]) / f"seed_{seed}.pt")
    info["seed_seconds"] = time.perf_counter() - start
    return {"rows": rows, "log": log, "info": info, "class_rows": per_class or []}


def summarise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per method × load profile, plus per method over all loads (``load_profile = "all"``)."""
    per_load = summarise_by_seed(rows, ["method", "load_profile"], SUMMARY_METRICS)
    all_rows = [{**row, "load_profile": "all"} for row in rows]
    overall = summarise_by_seed(all_rows, ["method", "load_profile"], SUMMARY_METRICS)
    return per_load + overall


def summarise_classes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per method × load profile × task class, plus all loads pooled (``load_profile = "all"``).

    Same two-stage aggregation as :func:`summarise`: the mean over a seed's evaluation
    workloads first (workloads without a task of the class contribute nothing), then mean ±
    sample standard deviation across seeds.
    """
    groups = ["method", "load_profile", "task_class"]
    per_load = summarise_by_seed(rows, groups, CLASS_SUMMARY_METRICS)
    all_rows = [{**row, "load_profile": "all"} for row in rows]
    return per_load + summarise_by_seed(all_rows, groups, CLASS_SUMMARY_METRICS)


def main(argv: list[str] | None = None) -> Path:
    """Run the benchmark; return the output directory."""
    args = parse_args(argv)
    setup_logging(args.log_level)
    raw = load_config(args.config, overrides=args.overrides, smoke=args.smoke)
    out = Path(args.out)
    if args.ablation:
        raw = apply_ablation(raw, args.ablation)
        out = out / "ablations" / args.ablation
    cfg = scheduler_config_from_dict(raw)
    bcfg = load_baselines_config(args.baselines_config, smoke=args.smoke)
    seeds = list(args.seeds) if args.seeds else list(cfg.seeds)
    shortest = min((s for s in cfg.actions.time_slices_ms if s is not None), default=None)
    if "srtf" in bcfg.reference_methods and shortest != bcfg.srtf.quantum_ms:
        LOGGER.warning("srtf.quantum_ms (%s) differs from the agent's shortest time slice (%s)",
                       bcfg.srtf.quantum_ms, shortest)  # fmt: skip
    ensure_dir(out)
    checkpoint_dir = None if (args.no_checkpoints or args.skip_ddqn) else out / "checkpoints"
    jobs = [
        {
            "cfg": cfg,
            "bcfg": bcfg,
            "seed": seed,
            "skip_ddqn": args.skip_ddqn,
            "checkpoint_dir": str(checkpoint_dir) if checkpoint_dir else None,
            "class_metrics": args.class_metrics,
        }
        for seed in seeds
    ]
    LOGGER.info("seeds %s, %d worker(s), smoke=%s, ablation=%s", seeds, args.workers,
                args.smoke, args.ablation)  # fmt: skip
    start = time.perf_counter()
    if args.workers > 1 and len(jobs) > 1:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=min(args.workers, len(jobs))) as pool:
            results = pool.map(run_seed, jobs, chunksize=1)
    else:
        results = [run_seed(job) for job in jobs]
    wall = time.perf_counter() - start

    rows = [row for result in results for row in result["rows"]]
    log = [row for result in results for row in result["log"]]
    write_csv(out / "raw_episodes.csv", rows, RAW_EPISODE_FIELDS)
    write_csv(out / "training_log.csv", log, TRAINING_LOG_FIELDS)
    summary = summarise(rows)
    write_csv(out / "summary.csv", summary, SUMMARY_FIELDS)
    if args.class_metrics:
        per_class = [row for result in results for row in result["class_rows"]]
        write_csv(out / "class_episodes.csv", per_class, CLASS_EPISODE_FIELDS)
        write_csv(out / "class_summary.csv", summarise_classes(per_class), CLASS_SUMMARY_FIELDS)
    save_run_metadata(
        out,
        {
            "scheduler": to_dict(cfg),
            "baselines": to_dict(bcfg),
            "run": {"smoke": args.smoke, "ablation": args.ablation, "skip_ddqn": args.skip_ddqn},
        },
        seeds,
        command=" ".join([sys.executable, "-m", "experiments.run_scheduler_benchmark",
                          *(argv if argv is not None else sys.argv[1:])]),
        extra={
            "workers": args.workers,
            "wall_seconds": wall,
            "per_seed": [result["info"] for result in results],
            "smoke": args.smoke,
            "ablation": args.ablation,
            "class_metrics": args.class_metrics,
        },
    )  # fmt: skip
    _log_summary(summary)
    LOGGER.info("wrote %s in %.1f s", out, wall)
    return out


def _log_summary(summary: list[dict[str, Any]]) -> None:
    for row in summary:
        LOGGER.info(
            "%-15s %-7s turnaround %8.1f ± %6.1f ms  response %7.1f ms  waiting %7.1f ms  "
            "slo %.3f  (n_seeds=%d)",
            row["method"],
            row["load_profile"],
            row["avg_turnaround_ms_mean"],
            row["avg_turnaround_ms_std"],
            row["avg_response_ms_mean"],
            row["avg_waiting_ms_mean"],
            row["slo_violation_rate_mean"],
            row["n_seeds"],
        )


if __name__ == "__main__":
    main()
