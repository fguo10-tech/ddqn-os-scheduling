"""Module A: Double DQN operating-system scheduling, as a simulator study.

The method follows the Double DQN scheduler described by Sun et al. (2025), arXiv 2503.23659.
It is implemented as a discrete-event **simulator** of a single CPU (not a kernel
modification), with:

* :mod:`~src.scheduler.tasks` / :mod:`~src.scheduler.simulator` / :mod:`~src.scheduler.metrics`
  — workload generator (task classes come from the config, so a workload profile such as the
  LLM-style mix of inference requests and fine-tuning jobs is a YAML file), machine model
  (soft memory constraint with thrashing, context switches, I/O), episode metrics and the
  same metrics per task class;
* :mod:`~src.scheduler.baselines` — FCFS, SJF, Round Robin and Priority baselines;
* :mod:`~src.scheduler.env` / :mod:`~src.scheduler.reward` — Gymnasium MDP with action masks
  and a reward in which every time term is a penalty;
* :mod:`~src.scheduler.agent` / :mod:`~src.scheduler.training` — Double DQN with the standard
  ``argmax`` target;
* :mod:`~src.scheduler.guardrails` — starvation override + aging, SLO fallback to Round Robin,
  Q-divergence latch;
* :mod:`~src.scheduler.plugin` / :mod:`~src.scheduler.adapters` — plugin interface and
  job-queue adapter sketches.

Every setting chosen by this repository lives in ``configs/scheduler_*.yaml`` and is marked
``[Assumption — not in paper]``.
"""

from __future__ import annotations

from .agent import (
    DoubleDQNAgent,
    MLPQNetwork,
    ReplayBuffer,
    SlotSharedQNetwork,
    double_dqn_targets,
    vanilla_dqn_targets,
)
from .baselines import FCFS, SJF, SRTF, Policy, PriorityPolicy, RoundRobin, make_policy
from .config import (
    BaselinesConfig,
    SchedulerConfig,
    load_baselines_config,
    load_scheduler_config,
)
from .env import SchedulerEnv, build_decision_state
from .guardrails import GuardrailEngine
from .metrics import CLASS_METRIC_FIELDS, EPISODE_METRIC_FIELDS, class_metrics, episode_metrics
from .plugin import (
    BaselineSchedulerPlugin,
    DDQNSchedulerPlugin,
    QueueSnapshot,
    SchedulerPlugin,
    SchedulingDecision,
)
from .reward import compute_reward
from .simulator import Decision, SchedulerSim, SimView, StepOutcome, TaskView, effective_priority
from .tasks import Task, TaskState, generate_workload
from .training import (
    RAW_EPISODE_FIELDS,
    TRAINING_LOG_FIELDS,
    evaluate_agent,
    evaluate_policy,
    train_agent,
)

__all__ = [
    "CLASS_METRIC_FIELDS",
    "EPISODE_METRIC_FIELDS",
    "FCFS",
    "RAW_EPISODE_FIELDS",
    "SJF",
    "SRTF",
    "TRAINING_LOG_FIELDS",
    "BaselineSchedulerPlugin",
    "BaselinesConfig",
    "DDQNSchedulerPlugin",
    "Decision",
    "DoubleDQNAgent",
    "GuardrailEngine",
    "MLPQNetwork",
    "Policy",
    "PriorityPolicy",
    "QueueSnapshot",
    "ReplayBuffer",
    "RoundRobin",
    "SchedulerConfig",
    "SchedulerEnv",
    "SchedulerPlugin",
    "SchedulerSim",
    "SchedulingDecision",
    "SimView",
    "SlotSharedQNetwork",
    "StepOutcome",
    "Task",
    "TaskState",
    "TaskView",
    "build_decision_state",
    "class_metrics",
    "compute_reward",
    "double_dqn_targets",
    "effective_priority",
    "episode_metrics",
    "evaluate_agent",
    "evaluate_policy",
    "generate_workload",
    "load_baselines_config",
    "load_scheduler_config",
    "make_policy",
    "train_agent",
    "vanilla_dqn_targets",
]
