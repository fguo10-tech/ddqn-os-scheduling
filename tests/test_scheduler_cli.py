"""Smoke runs through the real command-line entry points."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from src.common.io import read_csv, read_json
from src.scheduler.tasks import WORKLOAD_CSV_FIELDS
from src.scheduler.training import CLASS_EPISODE_FIELDS, RAW_EPISODE_FIELDS, TRAINING_LOG_FIELDS

METHODS = {"fcfs", "sjf", "round_robin", "priority", "srtf", "ddqn", "ddqn_unguarded"}


def run(repo_root, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(repo_root / ".pytest_cache" / "mpl"))
    return subprocess.run(
        [sys.executable, *args], cwd=repo_root, env=env, capture_output=True, text=True,
        timeout=120, check=False,
    )  # fmt: skip


@pytest.mark.slow
def test_benchmark_smoke_and_plots(repo_root, tmp_path) -> None:
    out = tmp_path / "run"
    proc = run(
        repo_root, "-m", "experiments.run_scheduler_benchmark",
        "--config", "configs/scheduler_ddqn.yaml",
        "--baselines-config", "configs/scheduler_baselines.yaml",
        "--smoke", "--out", str(out),
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-3000:]
    for name in ("config_used.yaml", "metadata.json", "raw_episodes.csv", "training_log.csv",
                 "summary.csv"):  # fmt: skip
        assert (out / name).is_file(), name
    raw = read_csv(out / "raw_episodes.csv")
    assert tuple(raw[0]) == RAW_EPISODE_FIELDS
    assert {r["method"] for r in raw} == METHODS
    assert {r["load_profile"] for r in raw} == {"light", "medium", "heavy"}
    assert all(int(r["seed"]) >= 100 for r in raw)
    log = read_csv(out / "training_log.csv")
    assert tuple(log[0]) == TRAINING_LOG_FIELDS and log
    summary = read_csv(out / "summary.csv")
    assert {(r["method"], r["load_profile"]) for r in summary} >= {(m, "all") for m in METHODS}
    assert "avg_turnaround_ms_mean" in summary[0] and "avg_turnaround_ms_std" in summary[0]
    assert read_json(out / "metadata.json")["extra"]["smoke"] is True
    assert not (out / "class_episodes.csv").exists(), "per-class files need --class-metrics"

    proc = run(repo_root, "-m", "experiments.plot_scheduler", "--run-dir", str(out))
    assert proc.returncode == 0, proc.stderr[-3000:]
    figures = out / "figures"
    for stem in ("metrics_light", "metrics_medium", "metrics_heavy", "metrics_all",
                 "training_reward", "guardrail_triggers"):  # fmt: skip
        assert (figures / f"{stem}.png").is_file() and (figures / f"{stem}.csv").is_file()


@pytest.mark.slow
def test_results_do_not_depend_on_worker_count(repo_root, tmp_path) -> None:
    """The same seeds give the same raw rows whether seeds run in one process or in two."""
    for workers in ("1", "2"):
        proc = run(
            repo_root, "-m", "experiments.run_scheduler_benchmark",
            "--config", "configs/scheduler_ddqn.yaml",
            "--baselines-config", "configs/scheduler_baselines.yaml",
            "--smoke", "--no-checkpoints", "--workers", workers,
            "--out", str(tmp_path / f"w{workers}"),
        )  # fmt: skip
        assert proc.returncode == 0, proc.stderr[-3000:]
    for name in ("raw_episodes.csv", "summary.csv"):
        assert read_csv(tmp_path / "w1" / name) == read_csv(tmp_path / "w2" / name), name


@pytest.mark.slow
def test_llm_workload_profile_smoke_with_class_metrics(repo_root, tmp_path) -> None:
    """The same entry point on the LLM-style profile, with the per-class files."""
    out = tmp_path / "llm"
    proc = run(
        repo_root, "-m", "experiments.run_scheduler_benchmark",
        "--config", "configs/scheduler_llm_workload.yaml",
        "--baselines-config", "configs/scheduler_baselines.yaml",
        "--smoke", "--no-checkpoints", "--class-metrics", "--out", str(out),
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-3000:]
    raw = read_csv(out / "raw_episodes.csv")
    assert tuple(raw[0]) == RAW_EPISODE_FIELDS and {r["method"] for r in raw} == METHODS
    assert all(int(r["seed"]) >= 100 for r in raw)
    per_class = read_csv(out / "class_episodes.csv")
    assert tuple(per_class[0]) == CLASS_EPISODE_FIELDS
    classes = {r["task_class"] for r in per_class}
    assert "inference_request" in classes and classes <= {"inference_request", "finetune_job"}
    assert {r["method"] for r in per_class} == METHODS
    summary = read_csv(out / "class_summary.csv")
    assert {r["load_profile"] for r in summary} >= {"all"}
    assert "slo_violation_rate_mean" in summary[0] and "task_class" in summary[0]
    assert read_json(out / "metadata.json")["extra"]["class_metrics"] is True
    proc = run(
        repo_root, "-m", "experiments.plot_scheduler", "--run-dir", str(out),
        "--title", "LLM-style workload",
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert (out / "figures" / "metrics_all.png").is_file()


def test_workload_cli_accepts_a_workload_profile(repo_root, tmp_path) -> None:
    target = tmp_path / "llm.csv"
    proc = run(
        repo_root, "data/synthetic/generate_scheduler_workload.py",
        "--config", "configs/scheduler_llm_workload.yaml",
        "--load", "heavy", "--seed", "100", "--out", str(target),
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-3000:]
    rows = read_csv(target)
    assert tuple(rows[0]) == WORKLOAD_CSV_FIELDS
    assert {r["task_type"] for r in rows} <= {"inference_request", "finetune_job"}


def test_workload_cli(repo_root, tmp_path) -> None:
    target = tmp_path / "w.csv"
    proc = run(
        repo_root, "data/synthetic/generate_scheduler_workload.py",
        "--load", "medium", "--seed", "100", "--out", str(target),
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-3000:]
    rows = read_csv(target)
    assert tuple(rows[0]) == WORKLOAD_CSV_FIELDS and 40 <= len(rows) <= 60


@pytest.mark.slow
def test_quickstart_example(repo_root) -> None:
    proc = run(repo_root, "examples/quickstart_scheduler.py")
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "ddqn" in proc.stdout and "plugin decision" in proc.stdout
