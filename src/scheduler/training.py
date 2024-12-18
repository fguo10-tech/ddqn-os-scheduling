"""Training and evaluation loops, and the row builders behind the raw CSV files.

Protocol (paired design, see ``experiments/run_scheduler_benchmark.py``): for one seed
``s`` the evaluation workloads are generated once (child seeds
``derive_seed(s, "eval", load, i)``) and every method is evaluated on exactly those
workloads through the same :class:`~src.scheduler.env.SchedulerEnv` code. Training
workloads use the disjoint child seeds ``derive_seed(s, "train", episode)``.

The agent learns online in the simulator: ``[Assumption — not in paper]``.
"""

from __future__ import annotations

import dataclasses
import math
import time
from collections.abc import Sequence
from typing import Any

import numpy as np
import torch

from src.common.logging_utils import get_logger
from src.common.seeding import derive_seed

from .agent import DoubleDQNAgent
from .baselines import Policy
from .config import SchedulerConfig, with_guardrails
from .env import SchedulerEnv, obs_layout
from .guardrails import GUARDRAIL_COUNTER_FIELDS
from .metrics import CLASS_METRIC_FIELDS, EPISODE_METRIC_FIELDS, class_metrics, episode_metrics
from .tasks import Task, generate_workload

LOGGER = get_logger(__name__)

RAW_EPISODE_FIELDS = (
    "seed",
    "method",
    "load_profile",
    "episode",
    "workload_seed",
    "n_tasks",
    "n_completed",
    "truncated",
    *EPISODE_METRIC_FIELDS,
    "episode_return",
    "steps",
    *GUARDRAIL_COUNTER_FIELDS,
    "invalid_actions",
)
"""Columns of ``raw_episodes.csv``: one row per seed × method × load profile × episode.

Guardrail counters for baseline and reference methods: they run through
``SchedulerEnv.step_decision``, which never filters a decision, but the engine still watches
their completions. ``guardrail_slo_fallback_activations`` for a baseline therefore counts how
often the SLO rule *would have* fired on that baseline's schedule; its
``guardrail_*_decisions`` and ``guardrail_overrides`` are always 0."""

CLASS_EPISODE_FIELDS = (
    "seed",
    "method",
    "load_profile",
    "episode",
    "workload_seed",
    "task_class",
    *CLASS_METRIC_FIELDS,
)
"""Columns of ``class_episodes.csv``: one row per seed × method × load profile × episode ×
task class. A class without a task in a workload has no row for that workload."""

CLASS_SUMMARY_METRICS = tuple(name for name in CLASS_METRIC_FIELDS if name != "n_completed")
"""Value columns summarised in ``class_summary.csv`` (``<metric>_mean`` / ``<metric>_std``)."""

SUMMARY_METRICS = (
    "avg_turnaround_ms",
    "p95_turnaround_ms",
    "avg_response_ms",
    "avg_waiting_ms",
    "throughput_tasks_per_s",
    "windowed_throughput_tasks_per_s",
    "cpu_utilisation",
    "makespan_ms",
    "starvation_count",
    "max_wait_ms",
    "slo_violation_rate",
    "context_switches",
    "priority_adjustments",
    "episode_return",
    "n_completed",
    *GUARDRAIL_COUNTER_FIELDS,
    "invalid_actions",
)
"""Value columns summarised in ``summary.csv`` (``<metric>_mean`` / ``<metric>_std``)."""

TRAINING_LOG_FIELDS = (
    "seed",
    "episode",
    "load_profile",
    "workload_seed",
    "episode_return",
    "steps",
    "stored_transitions",
    "env_steps_total",
    "epsilon",
    "mean_loss",
    "mean_abs_q",
    "guardrail_starvation_triggers",
    "guardrail_slo_fallback_activations",
    "guardrail_q_divergence_latches",
    "guardrail_overrides",
    "avg_turnaround_ms",
    "diverged",
    "wall_seconds",
)
"""Columns of ``training_log.csv``: one row per training episode."""


@dataclasses.dataclass(frozen=True)
class EvalWorkload:
    """One evaluation workload of the paired design."""

    load_profile: str
    episode: int
    workload_seed: int
    tasks: tuple[Task, ...]


@dataclasses.dataclass
class TrainingResult:
    """Output of :func:`train_agent`."""

    agent: DoubleDQNAgent
    log: list[dict[str, Any]]
    diverged: bool
    divergence_reason: str | None
    wall_seconds: float


def make_eval_workloads(cfg: SchedulerConfig, seed: int) -> list[EvalWorkload]:
    """``evaluation.episodes_per_load`` workloads per evaluation load profile for ``seed``."""
    workloads: list[EvalWorkload] = []
    for load in cfg.evaluation.load_profiles:
        for i in range(cfg.evaluation.episodes_per_load):
            wseed = derive_seed(seed, "eval", load, i)
            tasks = generate_workload(cfg.workload, load, wseed)
            workloads.append(EvalWorkload(load, i, wseed, tuple(tasks)))
    return workloads


def _counts(env: SchedulerEnv) -> dict[str, int]:
    return {name: int(env.guardrails.counts.get(name, 0)) for name in GUARDRAIL_COUNTER_FIELDS}


def episode_row(
    seed: int,
    method: str,
    workload: EvalWorkload,
    env: SchedulerEnv,
) -> dict[str, Any]:
    """One ``raw_episodes.csv`` row for a finished (or truncated) episode in ``env``."""
    assert env.sim is not None
    metrics = episode_metrics(env.sim, env.config.metrics.starvation_threshold_ms)
    row: dict[str, Any] = {
        "seed": seed,
        "method": method,
        "load_profile": workload.load_profile,
        "episode": workload.episode,
        "workload_seed": workload.workload_seed,
    }
    row.update(metrics)
    row["episode_return"] = env.episode_return
    row["steps"] = env.steps
    row.update(_counts(env))
    row["invalid_actions"] = env.invalid_actions
    return {key: row[key] for key in RAW_EPISODE_FIELDS}


def class_rows(
    seed: int,
    method: str,
    workload: EvalWorkload,
    env: SchedulerEnv,
) -> list[dict[str, Any]]:
    """The ``class_episodes.csv`` rows of a finished (or truncated) episode in ``env``."""
    assert env.sim is not None
    per_class = class_metrics(env.sim, env.config.metrics.starvation_threshold_ms)
    rows = []
    for task_class, metrics in per_class.items():
        row: dict[str, Any] = {
            "seed": seed,
            "method": method,
            "load_profile": workload.load_profile,
            "episode": workload.episode,
            "workload_seed": workload.workload_seed,
            "task_class": task_class,
        }
        row.update(metrics)
        rows.append({key: row[key] for key in CLASS_EPISODE_FIELDS})
    return rows


def run_policy_episode(env: SchedulerEnv, policy: Policy, workload: EvalWorkload) -> None:
    """Play one episode of a baseline through ``env.step_decision`` (no guardrails)."""
    policy.reset()
    env.reset(seed=workload.workload_seed, options={"workload": list(workload.tasks)})
    while True:
        _, _, terminated, truncated, _ = env.step_decision(policy.decide(env.view()))
        if terminated or truncated:
            return


def run_agent_episode(
    env: SchedulerEnv,
    agent: DoubleDQNAgent,
    workload: EvalWorkload,
    epsilon: float,
    rng: np.random.Generator,
) -> None:
    """Play one episode with the agent (Q-values reported to the guardrails before acting)."""
    obs, info = env.reset(seed=workload.workload_seed, options={"workload": list(workload.tasks)})
    while True:
        q = agent.q_values(obs)
        env.report_q_values(q)
        action = agent.select_action(q, info["action_mask"], epsilon, rng)
        obs, _, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            return


def evaluate_policy(
    cfg: SchedulerConfig,
    policy: Policy,
    workloads: Sequence[EvalWorkload],
    seed: int,
    method: str | None = None,
    per_class: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate a baseline on every workload; one row per workload.

    If a list is passed as ``per_class``, the per-task-class rows of every episode
    (:func:`class_rows`) are appended to it.
    """
    env = SchedulerEnv(cfg)
    rows = []
    for workload in workloads:
        run_policy_episode(env, policy, workload)
        rows.append(episode_row(seed, method or policy.name, workload, env))
        if per_class is not None:
            per_class.extend(class_rows(seed, method or policy.name, workload, env))
    return rows


def evaluate_agent(
    cfg: SchedulerConfig,
    agent: DoubleDQNAgent,
    workloads: Sequence[EvalWorkload],
    seed: int,
    method: str,
    guardrails: bool,
    per_class: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate the agent with guardrails on or off (``evaluation.epsilon``-greedy).

    If a list is passed as ``per_class``, the per-task-class rows of every episode
    (:func:`class_rows`) are appended to it.
    """
    env = SchedulerEnv(with_guardrails(cfg, guardrails and cfg.guardrails.enabled))
    rows = []
    for workload in workloads:
        rng = np.random.default_rng(
            derive_seed(seed, "eval_explore", method, workload.workload_seed)
        )
        run_agent_episode(env, agent, workload, cfg.evaluation.epsilon, rng)
        rows.append(episode_row(seed, method, workload, env))
        if per_class is not None:
            per_class.extend(class_rows(seed, method, workload, env))
    return rows


def _diverged(cfg: SchedulerConfig, loss: float, mean_abs_q: float) -> str | None:
    agent_cfg = cfg.agent
    if not math.isfinite(loss) or not math.isfinite(mean_abs_q):
        return "non-finite loss or Q-value"
    if loss > agent_cfg.divergence_loss_limit:
        return f"loss {loss:.4g} > divergence_loss_limit"
    if mean_abs_q > agent_cfg.divergence_q_limit:
        return f"mean |Q| {mean_abs_q:.4g} > divergence_q_limit"
    return None


def train_agent(cfg: SchedulerConfig, seed: int) -> TrainingResult:
    """Train a Double DQN agent on freshly generated workloads.

    The load profile of each episode is drawn uniformly from ``training.load_profiles``.
    The three override rules are active during training when
    ``training.guardrails_in_training`` (and the override master switch) are true;
    transitions whose decision a guardrail overrode are not stored. Aging and the rest of
    the observation encoding are the same either way.
    On divergence (non-finite or huge loss / Q) training stops, the weights of the last
    healthy episode are restored and the result is flagged.
    """
    torch.set_num_threads(1)
    start = time.perf_counter()
    train_cfg = with_guardrails(cfg, cfg.guardrails.enabled and cfg.training.guardrails_in_training)
    env = SchedulerEnv(train_cfg)
    agent = DoubleDQNAgent(obs_layout(cfg), cfg.agent, seed)
    profile_rng = np.random.default_rng(derive_seed(seed, "train_profiles"))
    agent_cfg = cfg.agent
    log: list[dict[str, Any]] = []
    good_weights = agent.weights()
    reason: str | None = None

    for episode in range(cfg.training.episodes):
        episode_start = time.perf_counter()
        load = cfg.training.load_profiles[
            int(profile_rng.integers(len(cfg.training.load_profiles)))
        ]
        wseed = derive_seed(seed, "train", episode)
        obs, info = env.reset(seed=wseed, options={"load_profile": load})
        losses: list[float] = []
        qs: list[float] = []
        stored = 0
        while True:
            q = agent.q_values(obs)
            env.report_q_values(q)
            epsilon = agent.epsilon()
            action = agent.select_action(q, info["action_mask"], epsilon)
            next_obs, reward, terminated, truncated, next_info = env.step(action)
            agent.env_steps += 1
            if not next_info["overridden"] and not next_info["invalid_action"]:
                agent.store(obs, action, reward, next_obs, terminated, next_info["action_mask"])
                stored += 1
            if (
                agent.env_steps >= agent_cfg.learning_starts
                and agent.env_steps % agent_cfg.train_every == 0
                and len(agent.replay) >= agent_cfg.batch_size
            ):
                stats = agent.update()
                losses.append(stats.loss)
                qs.append(stats.mean_abs_q)
                reason = _diverged(cfg, stats.loss, stats.mean_abs_q)
                if reason is not None:
                    break
            obs, info = next_obs, next_info
            if terminated or truncated:
                break
        assert env.sim is not None
        metrics = episode_metrics(env.sim, cfg.metrics.starvation_threshold_ms)
        counts = env.guardrails.counts
        log.append(
            {
                "seed": seed,
                "episode": episode,
                "load_profile": load,
                "workload_seed": wseed,
                "episode_return": env.episode_return,
                "steps": env.steps,
                "stored_transitions": stored,
                "env_steps_total": agent.env_steps,
                "epsilon": agent.epsilon(),
                "mean_loss": float(np.mean(losses)) if losses else math.nan,
                "mean_abs_q": float(np.mean(qs)) if qs else math.nan,
                "guardrail_starvation_triggers": counts["guardrail_starvation_triggers"],
                "guardrail_slo_fallback_activations": counts["guardrail_slo_fallback_activations"],
                "guardrail_q_divergence_latches": counts["guardrail_q_divergence_latches"],
                "guardrail_overrides": counts["guardrail_overrides"],
                "avg_turnaround_ms": metrics["avg_turnaround_ms"],
                "diverged": reason is not None,
                "wall_seconds": time.perf_counter() - episode_start,
            }
        )
        if reason is not None:
            LOGGER.warning("seed %d: training diverged at episode %d (%s); restoring last "
                           "healthy weights", seed, episode, reason)  # fmt: skip
            agent.load_weights(good_weights)
            break
        good_weights = agent.weights()

    return TrainingResult(
        agent=agent,
        log=log,
        diverged=reason is not None,
        divergence_reason=reason,
        wall_seconds=time.perf_counter() - start,
    )
