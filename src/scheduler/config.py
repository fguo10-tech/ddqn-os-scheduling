"""Configuration dataclasses for the scheduler track.

Every field is required: none of the dataclasses below declares a default, and they are
built with :func:`src.common.config.from_dict`, which rejects both missing and unknown keys.
The values live in ``configs/scheduler_ddqn.yaml`` and ``configs/scheduler_baselines.yaml``,
where every key carries a comment with its unit, meaning and provenance tag. Nearly every
value there is chosen by this repository and marked ``[Assumption — not in paper]``.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from src.common.config import ConfigError, deep_update, from_dict, load_config

POLICY_NAMES = ("fcfs", "sjf", "round_robin", "priority", "srtf")
"""Names accepted by :func:`src.scheduler.baselines.make_policy` (``srtf`` is a reference,
not one of the four textbook baselines)."""

TASK_CLASS_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
"""Allowed spelling of a task-class name (it becomes a CSV value and an observation column)."""


@dataclasses.dataclass(frozen=True)
class TaskTypeConfig:
    """Distribution of one task class.

    The benchmark config defines three classes (CPU-bound, memory-bound, I/O-bound); a
    workload profile such as ``configs/scheduler_llm_workload.yaml`` defines its own.
    """

    weight: float
    cpu_median_ms: float
    cpu_sigma: float
    cpu_min_ms: float
    cpu_max_ms: float
    io_ops_min: int
    io_ops_max: int
    io_wait_min_ms: float
    io_wait_max_ms: float
    memory_min_mb: float
    memory_max_mb: float
    slo_factor: float


@dataclasses.dataclass(frozen=True)
class WorkloadConfig:
    """Synthetic workload generator settings.

    ``task_types`` maps a task-class name to its distribution; the classes and their order
    are whatever the YAML file lists. ``priority_level_weights`` is either one list (the
    same priority distribution for every class) or a mapping from every class name to its
    own list.
    """

    n_tasks_min: int
    n_tasks_max: int
    min_burst_ms: float
    slo_slack_ms: float
    priority_level_weights: list[float] | dict[str, list[float]]
    load_profiles: dict[str, float]
    task_types: dict[str, TaskTypeConfig]


@dataclasses.dataclass(frozen=True)
class MachineConfig:
    """Single-CPU machine model."""

    memory_capacity_mb: float
    thrash_penalty: float
    context_switch_ms: float
    priority_adjust_overhead_ms: float
    num_priority_levels: int


@dataclasses.dataclass(frozen=True)
class MetricsConfig:
    """Episode-metric settings."""

    starvation_threshold_ms: float


@dataclasses.dataclass(frozen=True)
class ObservationConfig:
    """Observation layout and normalisation constants."""

    num_slots: int
    clip: float
    count_norm: float
    work_norm_ms: float
    wait_norm_ms: float
    slack_norm_ms: float
    slo_slack_threshold_ms: float
    arrival_rate_norm_per_s: float
    recent_time_constant_ms: float
    recent_completions: int
    reveal_total_remaining_cpu: bool


@dataclasses.dataclass(frozen=True)
class ActionsConfig:
    """Action-space settings. ``None`` in ``time_slices_ms`` means "run until the burst ends"."""

    time_slices_ms: list[float | None]
    max_priority_adjusts_per_dispatch: int


@dataclasses.dataclass(frozen=True)
class RewardConfig:
    """Reward weights (see :mod:`src.scheduler.reward`)."""

    time_scale_ms: float
    w_wait: float
    w_turnaround: float
    w_response: float
    w_slo_violation: float
    w_completion: float
    w_utilisation: float
    invalid_action_penalty: float
    paper_sign_as_printed: bool


@dataclasses.dataclass(frozen=True)
class AgingConfig:
    """Priority aging: +1 effective priority per ``interval_ms`` of continuous waiting."""

    enabled: bool
    interval_ms: float
    max_boost: int


@dataclasses.dataclass(frozen=True)
class StarvationConfig:
    """Max-wait override."""

    enabled: bool
    max_wait_ms: float
    forced_time_slice_ms: float | None


@dataclasses.dataclass(frozen=True)
class SloFallbackConfig:
    """Fallback to Round Robin after a burst of deadline misses."""

    enabled: bool
    window_completions: int
    violation_threshold: int
    fallback_quantum_ms: float
    fallback_duration_ms: float


@dataclasses.dataclass(frozen=True)
class QDivergenceConfig:
    """Latch into a baseline when the agent's Q-values are non-finite or huge."""

    enabled: bool
    q_abs_limit: float
    fallback_policy: Literal["fcfs", "sjf", "round_robin", "priority"]
    fallback_quantum_ms: float


@dataclasses.dataclass(frozen=True)
class GuardrailsConfig:
    """Guardrails.

    ``enabled`` is the master switch of the three *override* rules (starvation override, SLO
    fallback, Q-divergence latch). ``aging`` is part of the observation encoding and is
    controlled only by ``aging.enabled``; it is not affected by ``enabled``.
    """

    enabled: bool
    aging: AgingConfig
    starvation: StarvationConfig
    slo_fallback: SloFallbackConfig
    q_divergence: QDivergenceConfig


@dataclasses.dataclass(frozen=True)
class NetworkConfig:
    """Q-network architecture."""

    type: Literal["mlp", "slot_shared"]
    hidden_sizes: list[int]


@dataclasses.dataclass(frozen=True)
class AgentConfig:
    """Double DQN hyperparameters."""

    network: NetworkConfig
    learning_rate: float
    gamma: float
    batch_size: int
    replay_capacity: int
    target_update_interval: int
    epsilon_start: float
    epsilon_end: float
    epsilon_decay_steps: int
    learning_starts: int
    train_every: int
    loss: Literal["huber", "mse"]
    grad_clip_norm: float
    divergence_loss_limit: float
    divergence_q_limit: float


@dataclasses.dataclass(frozen=True)
class TrainingConfig:
    """Training-loop settings."""

    episodes: int
    load_profiles: list[str]
    max_steps_per_episode: int
    guardrails_in_training: bool


@dataclasses.dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation protocol settings."""

    episodes_per_load: int
    load_profiles: list[str]
    epsilon: float


@dataclasses.dataclass(frozen=True)
class SchedulerConfig:
    """Everything ``configs/scheduler_ddqn.yaml`` holds."""

    seeds: list[int]
    workload: WorkloadConfig
    machine: MachineConfig
    metrics: MetricsConfig
    observation: ObservationConfig
    actions: ActionsConfig
    reward: RewardConfig
    guardrails: GuardrailsConfig
    agent: AgentConfig
    training: TrainingConfig
    evaluation: EvaluationConfig
    ablations: dict[str, dict[str, Any]]


@dataclasses.dataclass(frozen=True)
class RoundRobinConfig:
    """Round Robin baseline."""

    quantum_ms: float


@dataclasses.dataclass(frozen=True)
class PriorityBaselineConfig:
    """Non-preemptive Priority baseline (added by this repository)."""

    use_aging: bool
    aging_interval_ms: float
    aging_max_boost: int


@dataclasses.dataclass(frozen=True)
class SrtfConfig:
    """Preemptive SRTF reference policy (not a textbook baseline)."""

    quantum_ms: float


@dataclasses.dataclass(frozen=True)
class BaselinesConfig:
    """Everything ``configs/scheduler_baselines.yaml`` holds.

    ``methods`` are the textbook baselines of the Before / After comparison;
    ``reference_methods`` are evaluated on the same workloads but drawn as references.
    """

    methods: list[Literal["fcfs", "sjf", "round_robin", "priority"]]
    reference_methods: list[Literal["srtf"]]
    round_robin: RoundRobinConfig
    priority: PriorityBaselineConfig
    srtf: SrtfConfig


def task_class_names(workload: WorkloadConfig) -> tuple[str, ...]:
    """Task-class names in the order the config lists them.

    The order is part of the experiment: the generator indexes its class draw with it and the
    observation has one one-hot column per class in this order.
    """
    return tuple(workload.task_types)


def priority_weights_for(workload: WorkloadConfig, task_class: str) -> list[float]:
    """Sampling weights of the priority levels for ``task_class`` (not normalised)."""
    weights = workload.priority_level_weights
    if isinstance(weights, Mapping):
        return list(weights[task_class])
    return list(weights)


def _check_weights(values: Iterable[float], where: str) -> None:
    values = list(values)
    if any(value < 0 for value in values) or sum(values) <= 0:
        raise ConfigError(f"{where}: weights must be non-negative with a positive sum")


def validate_scheduler_config(cfg: SchedulerConfig) -> SchedulerConfig:
    """Check cross-field constraints that a type check cannot express; return ``cfg``."""
    work = cfg.workload
    names = task_class_names(work)
    if not names:
        raise ConfigError("workload.task_types must define at least one task class")
    for name in names:
        if not TASK_CLASS_NAME.match(name):
            raise ConfigError(
                f"workload.task_types.{name}: a task-class name must match "
                f"{TASK_CLASS_NAME.pattern} (lower case, digits, underscores)"
            )
    _check_weights((t.weight for t in work.task_types.values()), "workload.task_types.*.weight")
    levels = cfg.machine.num_priority_levels
    if isinstance(work.priority_level_weights, Mapping):
        if set(work.priority_level_weights) != set(names):
            raise ConfigError(
                "workload.priority_level_weights: a per-class mapping must have exactly the "
                f"task classes {list(names)}"
            )
        per_class = {name: priority_weights_for(work, name) for name in names}
    else:
        per_class = {"": list(work.priority_level_weights)}
    for name, weights in per_class.items():
        where = "workload.priority_level_weights" + (f".{name}" if name else "")
        if len(weights) != levels:
            raise ConfigError(f"{where} must have machine.num_priority_levels entries")
        _check_weights(weights, where)
    if not 1 <= work.n_tasks_min <= work.n_tasks_max:
        raise ConfigError("workload: need 1 <= n_tasks_min <= n_tasks_max")
    for name, tcfg in work.task_types.items():
        if tcfg.memory_max_mb > cfg.machine.memory_capacity_mb:
            raise ConfigError(f"workload.task_types.{name}: memory_max_mb exceeds capacity")
        if not (0 <= tcfg.io_ops_min <= tcfg.io_ops_max):
            raise ConfigError(f"workload.task_types.{name}: bad io_ops range")
        if not (0 < tcfg.cpu_min_ms <= tcfg.cpu_max_ms):
            raise ConfigError(f"workload.task_types.{name}: bad cpu range")
        if tcfg.io_ops_max > 0 and tcfg.io_wait_min_ms <= 0:
            raise ConfigError(f"workload.task_types.{name}: io_wait_min_ms must be > 0")
    for name, rho in work.load_profiles.items():
        if not 0 < rho:
            raise ConfigError(f"workload.load_profiles.{name} must be positive")
    for profile in [*cfg.training.load_profiles, *cfg.evaluation.load_profiles]:
        if profile not in work.load_profiles:
            raise ConfigError(f"unknown load profile {profile!r}")
    if not cfg.actions.time_slices_ms:
        raise ConfigError("actions.time_slices_ms must not be empty")
    for value in cfg.actions.time_slices_ms:
        if value is not None and value <= 0:
            raise ConfigError("actions.time_slices_ms entries must be positive or null")
    if cfg.observation.num_slots < 1:
        raise ConfigError("observation.num_slots must be >= 1")
    if not 0.0 <= cfg.agent.gamma <= 1.0:
        raise ConfigError("agent.gamma must be in [0, 1]")
    slo = cfg.guardrails.slo_fallback
    if not 1 <= slo.violation_threshold <= slo.window_completions:
        raise ConfigError("guardrails.slo_fallback: need 1 <= violation_threshold <= window")
    return cfg


def scheduler_config_from_dict(data: Mapping[str, Any]) -> SchedulerConfig:
    """Build and validate a :class:`SchedulerConfig` from a plain mapping."""
    return validate_scheduler_config(from_dict(SchedulerConfig, data))


def load_scheduler_config(
    path: str | Path,
    overrides: Iterable[str] | None = None,
    smoke: bool = False,
) -> SchedulerConfig:
    """Load ``configs/scheduler_ddqn.yaml`` (or a variant) into a validated dataclass."""
    return scheduler_config_from_dict(load_config(path, overrides=overrides, smoke=smoke))


def load_baselines_config(
    path: str | Path,
    overrides: Iterable[str] | None = None,
    smoke: bool = False,
) -> BaselinesConfig:
    """Load ``configs/scheduler_baselines.yaml`` into a dataclass."""
    return from_dict(BaselinesConfig, load_config(path, overrides=overrides, smoke=smoke))


def nest_dotted(flat: Mapping[str, Any]) -> dict[str, Any]:
    """Turn ``{"agent.gamma": 0.9}`` into ``{"agent": {"gamma": 0.9}}``."""
    nested: dict[str, Any] = {}
    for dotted, value in flat.items():
        keys = [part for part in str(dotted).split(".") if part]
        if not keys:
            raise ConfigError(f"empty override key: {dotted!r}")
        cursor = nested
        for key in keys[:-1]:
            cursor = cursor.setdefault(key, {})
            if not isinstance(cursor, dict):
                raise ConfigError(f"override {dotted!r} conflicts with another override")
        cursor[keys[-1]] = value
    return nested


def apply_ablation(raw: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Return the raw config dict with ablation ``name`` (dotted-key overrides) applied."""
    ablations = raw.get("ablations") or {}
    if name not in ablations:
        raise ConfigError(f"unknown ablation {name!r}; known: {sorted(ablations)}")
    return deep_update(raw, nest_dotted(ablations[name]))


def with_guardrails(cfg: SchedulerConfig, enabled: bool) -> SchedulerConfig:
    """Copy of ``cfg`` with the override master switch set to ``enabled``.

    Only the three override rules change; aging and the observation encoding stay the same.
    """
    return dataclasses.replace(cfg, guardrails=dataclasses.replace(cfg.guardrails, enabled=enabled))
