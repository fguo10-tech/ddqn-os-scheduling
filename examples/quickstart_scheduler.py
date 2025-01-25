"""Quickstart: baselines vs a tiny Double DQN agent on one workload, then one plugin decision.

Run from the repository root (takes a few seconds)::

    python examples/quickstart_scheduler.py

It uses the ``--smoke`` settings of ``configs/scheduler_ddqn.yaml`` and development seed
100, so the agent is barely trained: the table shows that the pipeline works, not how well
the method performs. For results run ``experiments/run_scheduler_benchmark.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging_utils import get_logger, setup_logging  # noqa: E402
from src.scheduler.baselines import make_policy  # noqa: E402
from src.scheduler.config import load_baselines_config, load_scheduler_config  # noqa: E402
from src.scheduler.env import RecentStats  # noqa: E402
from src.scheduler.plugin import DDQNSchedulerPlugin, snapshot_from_view  # noqa: E402
from src.scheduler.simulator import SchedulerSim  # noqa: E402
from src.scheduler.training import (  # noqa: E402
    evaluate_agent,
    evaluate_policy,
    make_eval_workloads,
    train_agent,
)

LOGGER = get_logger("examples.quickstart_scheduler")
CONFIG = REPO_ROOT / "configs" / "scheduler_ddqn.yaml"
BASELINES = REPO_ROOT / "configs" / "scheduler_baselines.yaml"
SEED = 100  # development seed (seeds 0-4 are reserved for the reference benchmark)
LOAD = "medium"


def main() -> None:
    """Run the quickstart and print a comparison table."""
    setup_logging("WARNING")
    cfg = load_scheduler_config(CONFIG, smoke=True)
    bcfg = load_baselines_config(BASELINES, smoke=True)
    workload = [w for w in make_eval_workloads(cfg, SEED) if w.load_profile == LOAD][:1]

    rows = []
    for method in bcfg.methods:
        rows += evaluate_policy(cfg, make_policy(method, bcfg), workload, SEED, method)
    result = train_agent(cfg, SEED)
    rows += evaluate_agent(cfg, result.agent, workload, SEED, "ddqn", guardrails=True)
    rows += evaluate_agent(cfg, result.agent, workload, SEED, "ddqn_unguarded", guardrails=False)

    print(f"config: {CONFIG.relative_to(REPO_ROOT)} (smoke settings), seed {SEED}, "
          f"load {LOAD}, {rows[0]['n_tasks']} tasks, {len(result.log)} training episodes")  # fmt: skip
    print(f"{'method':<16}{'turnaround ms':>15}{'response ms':>13}{'waiting ms':>12}"
          f"{'SLO viol.':>11}")  # fmt: skip
    for row in rows:
        print(f"{row['method']:<16}{row['avg_turnaround_ms']:>15.1f}"
              f"{row['avg_response_ms']:>13.1f}{row['avg_waiting_ms']:>12.1f}"
              f"{row['slo_violation_rate']:>11.3f}")  # fmt: skip
    print("(barely trained agent, one workload: a pipeline check, not a result)")

    plugin = DDQNSchedulerPlugin(result.agent, cfg)
    sim = SchedulerSim(workload[0].tasks, cfg.machine)
    snapshot = snapshot_from_view(sim.view(), RecentStats(0.0, 0.0, 0.0))
    decision = plugin.decide(snapshot)
    print(f"plugin decision at t={snapshot.now_ms:.1f} ms with {len(snapshot.jobs)} waiting "
          f"job(s): job {decision.job_id}, slice {decision.time_slice_ms}, "
          f"priority change {decision.priority_change}, decided by {decision.decided_by}")  # fmt: skip


if __name__ == "__main__":
    main()
