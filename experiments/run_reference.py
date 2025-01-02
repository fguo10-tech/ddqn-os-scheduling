"""Re-create the reference runs that the documentation cites.

Runs the benchmark exactly as fixed in the configs (reporting seeds 0-4) and the ablations into
``experiments/results/reference/scheduler/``, then the same benchmark on the LLM-style
workload profile (``configs/scheduler_llm_workload.yaml``) and the ablation that profile
defines itself into ``experiments/results/reference/scheduler_llm/``, and records the measured
wall-clock time of each part in that part's ``metadata.json``. Afterwards run ``make results``
to rebuild the tables.

This overwrites the committed reference results. Do it on purpose, not by accident::

    python -m experiments.run_reference --workers 8                 # everything
    python -m experiments.run_reference --skip-ablations            # no ablations
    python -m experiments.run_reference --only llm_workload         # the LLM-style profile only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from src.common.config import load_config
from src.common.io import read_json, write_json
from src.common.logging_utils import get_logger, setup_logging

LOGGER = get_logger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "experiments" / "results" / "reference"
SCHEDULER_CONFIG = "configs/scheduler_ddqn.yaml"
BASELINES_CONFIG = "configs/scheduler_baselines.yaml"
LLM_WORKLOAD_CONFIG = "configs/scheduler_llm_workload.yaml"
PARTS = ("scheduler", "llm_workload")


def _run(module: str, *arguments: str) -> float:
    """Run ``python -m module arguments`` from the repository root; return the seconds it took."""
    command = [sys.executable, "-m", module, *arguments]
    LOGGER.info("running: %s", " ".join(command[1:]))
    started = time.perf_counter()
    subprocess.run(command, cwd=REPO_ROOT, check=True)
    return time.perf_counter() - started


def _record_timing(run_dir: Path, seconds: float, workers: int) -> None:
    """Add the measured wall-clock time to a run's ``metadata.json``."""
    path = run_dir / "metadata.json"
    if not path.is_file():
        LOGGER.warning("no metadata.json in %s; timing not recorded", run_dir)
        return
    metadata = read_json(path)
    extra = dict(metadata.get("extra") or {})
    extra.update({"wall_clock_seconds": round(seconds, 1), "workers": workers})
    metadata["extra"] = extra
    write_json(path, metadata)


def run_scheduler(workers: int, ablations: bool) -> None:
    """The paired benchmark over seeds 0-4, its figures and the ablations."""
    out = REFERENCE / "scheduler"
    seconds = _run(
        "experiments.run_scheduler_benchmark",
        "--config", SCHEDULER_CONFIG, "--baselines-config", BASELINES_CONFIG,
        "--out", str(out), "--workers", str(workers), "--no-checkpoints",
    )  # fmt: skip
    _record_timing(out, seconds, workers)
    _run("experiments.plot_scheduler", "--run-dir", str(out))
    if not ablations:
        return
    for name in load_config(REPO_ROOT / SCHEDULER_CONFIG).get("ablations", {}):
        elapsed = _run(
            "experiments.run_scheduler_benchmark",
            "--config", SCHEDULER_CONFIG, "--baselines-config", BASELINES_CONFIG,
            "--out", str(out), "--workers", str(workers), "--no-checkpoints", "--ablation", name,
        )  # fmt: skip
        _record_timing(out / "ablations" / name, elapsed, workers)


def own_ablations(config: str, base_config: str) -> list[str]:
    """Names of the ablations ``config`` defines itself, i.e. the ones not in ``base_config``."""
    inherited = load_config(REPO_ROOT / base_config).get("ablations", {})
    defined = load_config(REPO_ROOT / config).get("ablations", {})
    return [name for name in defined if name not in inherited]


def run_llm_workload(workers: int, ablations: bool) -> None:
    """The same paired benchmark on the LLM-style workload profile, with per-class metrics.

    The profile inherits every setting except the task classes from the benchmark config; the
    agent is trained from scratch on it. Of the ablations, only the ones the profile defines
    itself are run on it; the ones it inherits from the benchmark config are not.
    """
    out = REFERENCE / "scheduler_llm"
    seconds = _run(
        "experiments.run_scheduler_benchmark",
        "--config", LLM_WORKLOAD_CONFIG, "--baselines-config", BASELINES_CONFIG,
        "--out", str(out), "--workers", str(workers), "--no-checkpoints", "--class-metrics",
    )  # fmt: skip
    _record_timing(out, seconds, workers)
    _run("experiments.plot_scheduler", "--run-dir", str(out), "--title", "LLM-style workload")
    if not ablations:
        return
    for name in own_ablations(LLM_WORKLOAD_CONFIG, SCHEDULER_CONFIG):
        elapsed = _run(
            "experiments.run_scheduler_benchmark",
            "--config", LLM_WORKLOAD_CONFIG, "--baselines-config", BASELINES_CONFIG,
            "--out", str(out), "--workers", str(workers), "--no-checkpoints", "--class-metrics",
            "--ablation", name,
        )  # fmt: skip
        _record_timing(out / "ablations" / name, elapsed, workers)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workers", type=int, default=4, help="worker processes")
    parser.add_argument("--skip-ablations", action="store_true", help="do not run the ablations")
    parser.add_argument(
        "--only", choices=PARTS, default=None, help="re-create only this part (default: both)"
    )
    args = parser.parse_args(argv)
    setup_logging("INFO")
    if args.only in (None, "scheduler"):
        run_scheduler(args.workers, not args.skip_ablations)
    if args.only in (None, "llm_workload"):
        run_llm_workload(args.workers, not args.skip_ablations)
    LOGGER.info(
        "reference run written to %s; now run `make results`", REFERENCE.relative_to(REPO_ROOT)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
