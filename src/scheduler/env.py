"""Gymnasium environment around :class:`~src.scheduler.simulator.SchedulerSim`.

The state covers queue status, system load and available resources; the actions raise or
lower a task's priority or dispatch a task with a chosen CPU time slice. The encoding and
the action count below are ``[Assumption — not in paper]``.

Visible window
    The agent sees the top ``K = observation.num_slots`` READY tasks ordered by
    (effective priority descending, ``ready_seq`` ascending); effective priority includes
    aging when ``guardrails.aging.enabled``. Aging is part of the *observation encoding*:
    it does not depend on ``guardrails.enabled``, which switches only the three override
    rules (starvation override, SLO fallback, Q-divergence latch). The guarded and the
    unguarded agent therefore see identical observations and masks. Empty slots are 0.

What the agent and the baselines know about burst lengths (information parity)
    Baselines (SJF, SRTF) use the exact remaining time of each READY task's *current* CPU
    burst. By default the agent gets exactly that and nothing about future bursts: its slot
    features include ``current_burst_remaining`` but not the total remaining CPU work, the
    global work feature sums current bursts only, and deadline slack is
    ``deadline − now − current burst remaining``. With
    ``observation.reveal_total_remaining_cpu: true`` (an oracle the baselines do not have;
    ablation ``oracle_total_remaining``) the agent additionally sees each task's total
    remaining CPU work and the queue's total remaining work, and slack subtracts the total.
    Indirect hint not removed: the task-class one-hot (I/O-bound tasks have more bursts).

Task classes
    Each slot ends with a one-hot over the task classes of ``workload.task_types`` (in the
    order the config lists them), so the slot width ``F`` depends on the number of classes
    and an agent is trained for one set of classes.

Observation
    A flat float32 vector of ``G + K × F`` features, every one listed (name, description,
    normalisation) in ``env.OBSERVATION_FIELDS``. The list and the vector are produced from
    the same feature tables (:data:`GLOBAL_FEATURES`, :data:`SLOT_FEATURES`) by
    :func:`build_decision_state`, which the plugin also calls (one code path, no train /
    serve skew). Every value is clipped to ``[-observation.clip, observation.clip]``.

Actions (``Discrete(K × J + 2 × K)``, ``J = len(actions.time_slices_ms)``)
    ``DISPATCH(k, j)`` = index ``k × J + j``: run the task in slot ``k`` for slice ``j``.
    ``PRIORITY(k, d)`` = index ``K × J + 2k + d`` (``d = 0`` raise, ``d = 1`` lower).
    Mask: empty slot invalid; a priority change that leaves ``[0, levels − 1]`` invalid; after
    ``actions.max_priority_adjusts_per_dispatch`` consecutive priority actions only dispatch
    actions are valid. An invalid action passed to :meth:`SchedulerEnv.step` is replaced by
    the first valid dispatch and costs ``reward.invalid_action_penalty``.

Guardrails
    ``step(action)`` converts the action to a :class:`Decision`, passes it through the
    :class:`~src.scheduler.guardrails.GuardrailEngine`, executes what comes back and reports
    ``info["guardrail"]`` and ``info["overridden"]``. ``step_decision(decision)`` executes a
    decision directly (baselines; no guardrail) and returns the same 5-tuple.
"""

from __future__ import annotations

import dataclasses
import functools
import math
import re
from collections import deque
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np

from .config import AgingConfig, SchedulerConfig, task_class_names
from .guardrails import GuardrailEngine
from .reward import compute_reward
from .simulator import Decision, SchedulerSim, SimView, StepOutcome, TaskView, effective_priority
from .tasks import Task, generate_workload


@dataclasses.dataclass(frozen=True)
class RecentStats:
    """Recent-history signals that are part of the observation.

    In the simulator they come from :class:`RecentStatsTracker`; a platform using the plugin
    supplies its own measurements in the queue snapshot.
    """

    cpu_utilisation: float
    arrival_rate_per_s: float
    slo_violation_rate: float


class RecentStatsTracker:
    """Exponentially decaying CPU utilisation and arrival rate (time constant
    ``observation.recent_time_constant_ms``) and the late fraction of the last
    ``observation.recent_completions`` completions."""

    def __init__(self, time_constant_ms: float, completions: int) -> None:
        self.time_constant_ms = float(time_constant_ms)
        self._late: deque[bool] = deque(maxlen=int(completions))
        self.cpu_utilisation = 0.0
        self.arrival_rate_per_s = 0.0

    def reset(self) -> None:
        """Forget all history."""
        self._late.clear()
        self.cpu_utilisation = 0.0
        self.arrival_rate_per_s = 0.0

    def update(self, outcome: StepOutcome) -> None:
        """Fold one executed step into the statistics."""
        duration = outcome.duration_ms
        if duration > 0:
            decay = math.exp(-duration / self.time_constant_ms)
            self.cpu_utilisation = decay * self.cpu_utilisation + (1.0 - decay) * (
                outcome.busy_ms / duration
            )
            self.arrival_rate_per_s *= decay
        self.arrival_rate_per_s += outcome.arrivals * 1000.0 / self.time_constant_ms
        late = set(outcome.late_completed)
        for task_id in outcome.completed:
            self._late.append(task_id in late)

    def snapshot(self) -> RecentStats:
        """Current values."""
        rate = float(np.mean(self._late)) if self._late else 0.0
        return RecentStats(self.cpu_utilisation, self.arrival_rate_per_s, rate)


@dataclasses.dataclass(frozen=True)
class ObsLayout:
    """Shape of the observation vector: ``G`` global features then ``K`` slots of ``F``."""

    global_dim: int
    num_slots: int
    slot_dim: int
    num_slices: int

    @property
    def obs_dim(self) -> int:
        """``G + K × F``."""
        return self.global_dim + self.num_slots * self.slot_dim

    @property
    def n_actions(self) -> int:
        """``K × J + 2 × K``."""
        return self.num_slots * self.num_slices + 2 * self.num_slots


@dataclasses.dataclass(frozen=True)
class _FeatureContext:
    view: SimView
    recent: RecentStats
    consecutive_adjusts: int
    max_adjusts: int
    aging: AgingConfig | None
    reveal_total: bool
    work_norm: float
    wait_norm: float
    slack_norm: float
    count_norm: float
    rate_norm: float
    slack_threshold: float
    priority_norm: float


def _slack(task: TaskView, ctx: _FeatureContext) -> float:
    """Deadline slack: deadline − now − remaining work the agent may know about."""
    work = task.remaining_total_cpu_ms if ctx.reveal_total else task.remaining_burst_ms
    return task.deadline_ms - ctx.view.now_ms - work


def _mean_wait(ctx: _FeatureContext) -> float:
    ready = ctx.view.ready
    return (sum(t.wait_ms for t in ready) / len(ready)) / ctx.wait_norm if ready else 0.0


def _max_wait(ctx: _FeatureContext) -> float:
    ready = ctx.view.ready
    return max(t.wait_ms for t in ready) / ctx.wait_norm if ready else 0.0


def _slo_pressure(ctx: _FeatureContext) -> float:
    ready = ctx.view.ready
    if not ready:
        return 0.0
    return sum(1 for t in ready if _slack(t, ctx) < ctx.slack_threshold) / len(ready)


GlobalFn = Callable[[_FeatureContext], float]
SlotFn = Callable[[TaskView, _FeatureContext], float]

GLOBAL_FEATURES: tuple[tuple[str, str, str, GlobalFn], ...] = (
    (
        "ready_queue_length",
        "number of READY tasks",
        "/ observation.count_norm",
        lambda c: len(c.view.ready) / c.count_norm,
    ),
    (
        "blocked_tasks",
        "number of tasks blocked on I/O",
        "/ observation.count_norm",
        lambda c: c.view.n_blocked / c.count_norm,
    ),
    (
        "free_memory_fraction",
        "1 − resident / capacity (negative when over-committed)",
        "clipped to [-1, 1]",
        lambda c: min(1.0, max(-1.0, 1.0 - c.view.resident_mb / c.view.memory_capacity_mb)),
    ),
    (
        "recent_cpu_utilisation",
        "exponentially decaying busy fraction",
        "none (already in [0, 1])",
        lambda c: c.recent.cpu_utilisation,
    ),
    (
        "ready_current_burst_work",
        "sum of the remaining current CPU bursts of READY tasks",
        "/ (observation.work_norm_ms × observation.count_norm)",
        lambda c: sum(t.remaining_burst_ms for t in c.view.ready) / (c.work_norm * c.count_norm),
    ),
    (
        "remaining_ready_work_total",
        "ORACLE (only with observation.reveal_total_remaining_cpu): sum of the total remaining "
        "CPU work (all future bursts) of READY tasks",
        "/ (observation.work_norm_ms × observation.count_norm)",
        lambda c: sum(t.remaining_total_cpu_ms for t in c.view.ready)
        / (c.work_norm * c.count_norm),
    ),
    (
        "mean_ready_wait",
        "mean continuous waiting time of READY tasks",
        "/ observation.wait_norm_ms",
        _mean_wait,
    ),
    (
        "max_ready_wait",
        "max continuous waiting time of READY tasks",
        "/ observation.wait_norm_ms",
        _max_wait,
    ),
    (
        "slo_pressure",
        "fraction of READY tasks with deadline slack below observation.slo_slack_threshold_ms",
        "none (fraction)",
        _slo_pressure,
    ),
    (
        "recent_arrival_rate",
        "exponentially decaying arrival rate (tasks/s)",
        "/ observation.arrival_rate_norm_per_s",
        lambda c: c.recent.arrival_rate_per_s / c.rate_norm,
    ),
    (
        "recent_slo_violation_rate",
        "late fraction of the last observation.recent_completions completions",
        "none (fraction)",
        lambda c: c.recent.slo_violation_rate,
    ),
    (
        "priority_adjust_budget",
        "remaining consecutive priority actions before a dispatch is forced",
        "/ actions.max_priority_adjusts_per_dispatch (0 if that is 0)",
        lambda c: (
            (c.max_adjusts - c.consecutive_adjusts) / c.max_adjusts if c.max_adjusts > 0 else 0.0
        ),
    ),
)
"""Global features: (name, description, normalisation, value function)."""

SLOT_FEATURES: tuple[tuple[str, str, str, SlotFn], ...] = (
    ("occupied", "1 if the slot holds a task", "none", lambda t, c: 1.0),
    (
        "remaining_total_cpu",
        "ORACLE (only with observation.reveal_total_remaining_cpu): remaining CPU work of the "
        "task over all future bursts",
        "/ observation.work_norm_ms",
        lambda t, c: t.remaining_total_cpu_ms / c.work_norm,
    ),
    (
        "current_burst_remaining",
        "remaining time of the current CPU burst",
        "/ observation.work_norm_ms",
        lambda t, c: t.remaining_burst_ms / c.work_norm,
    ),
    (
        "memory_fraction",
        "memory request / capacity",
        "/ machine.memory_capacity_mb",
        lambda t, c: t.memory_mb / c.view.memory_capacity_mb,
    ),
    (
        "started",
        "1 if the task already holds its memory",
        "none",
        lambda t, c: 1.0 if t.started else 0.0,
    ),
    (
        "current_wait",
        "continuous waiting time in the ready queue",
        "/ observation.wait_norm_ms",
        lambda t, c: t.wait_ms / c.wait_norm,
    ),
    (
        "time_in_system",
        "now − arrival",
        "/ observation.wait_norm_ms",
        lambda t, c: t.time_in_system_ms / c.wait_norm,
    ),
    (
        "effective_priority",
        "priority + agent offset + aging boost",
        "/ (levels − 1 + aging max_boost when aging is on)",
        lambda t, c: effective_priority(t, c.aging) / c.priority_norm,
    ),
    (
        "deadline_slack",
        "deadline − now − current burst remaining (− total remaining CPU with the oracle flag)",
        "/ observation.slack_norm_ms",
        lambda t, c: _slack(t, c) / c.slack_norm,
    ),
)
"""Per-slot features that every config has: (name, description, normalisation, value
function). The one-hot over the task classes of the config follows them (see
:func:`task_class_features`)."""


def task_class_features(names: tuple[str, ...]) -> tuple[tuple[str, str, str, SlotFn], ...]:
    """One one-hot slot feature per task class, in the order of ``names``."""
    return tuple(
        (
            f"type_{name}",
            f"1 if the task is {name.replace('_', '-')}",
            "none (one-hot)",
            (lambda t, c, _n=name: 1.0 if t.task_type == _n else 0.0),
        )
        for name in names
    )


@functools.lru_cache(maxsize=32)
def _slot_feature_rows(
    reveal: bool, names: tuple[str, ...]
) -> tuple[tuple[str, str, str, SlotFn], ...]:
    """Slot feature rows for one (oracle switch, task classes) combination, built once."""
    rows = tuple(f for f in SLOT_FEATURES if reveal or f[0] not in ORACLE_FEATURES)
    return rows + task_class_features(names)


ORACLE_FEATURES = frozenset({"remaining_ready_work_total", "remaining_total_cpu"})
"""Features that reveal future-burst information the baselines do not have. They are part
of the observation only when ``observation.reveal_total_remaining_cpu`` is true."""


def active_global_features(cfg: SchedulerConfig) -> tuple[tuple[str, str, str, GlobalFn], ...]:
    """Global feature rows used under ``cfg`` (oracle rows dropped unless revealed)."""
    reveal = cfg.observation.reveal_total_remaining_cpu
    return tuple(f for f in GLOBAL_FEATURES if reveal or f[0] not in ORACLE_FEATURES)


def active_slot_features(cfg: SchedulerConfig) -> tuple[tuple[str, str, str, SlotFn], ...]:
    """Per-slot feature rows used under ``cfg``: the common rows (oracle rows dropped unless
    revealed) followed by the one-hot over the task classes of ``cfg.workload``."""
    return _slot_feature_rows(
        cfg.observation.reveal_total_remaining_cpu, task_class_names(cfg.workload)
    )


def observation_fields(cfg: SchedulerConfig) -> list[tuple[str, str, str]]:
    """Ordered (name, description, normalisation) for every observation dimension."""
    fields = [(name, desc, norm) for name, desc, norm, _ in active_global_features(cfg)]
    for k in range(cfg.observation.num_slots):
        fields.extend(
            (f"slot{k}.{name}", desc + " (0 if the slot is empty)", norm)
            for name, desc, norm, _ in active_slot_features(cfg)
        )
    return fields


def obs_layout(cfg: SchedulerConfig) -> ObsLayout:
    """Observation and action dimensions for ``cfg``."""
    return ObsLayout(
        global_dim=len(active_global_features(cfg)),
        num_slots=cfg.observation.num_slots,
        slot_dim=len(active_slot_features(cfg)),
        num_slices=len(cfg.actions.time_slices_ms),
    )


def action_table(cfg: SchedulerConfig) -> list[dict[str, Any]]:
    """Index → meaning for every action (for documentation and logs)."""
    num_slots = cfg.observation.num_slots
    slices = cfg.actions.time_slices_ms
    table: list[dict[str, Any]] = []
    for k in range(num_slots):
        for j, slice_ms in enumerate(slices):
            table.append(
                {
                    "index": k * len(slices) + j,
                    "family": "DISPATCH",
                    "slot": k,
                    "argument": "to_burst_end" if slice_ms is None else slice_ms,
                    "meaning": f"run slot {k} "
                    + ("until its burst ends" if slice_ms is None else f"for {slice_ms} ms"),
                }
            )
    base = num_slots * len(slices)
    for k in range(num_slots):
        for d, delta in enumerate((1, -1)):
            table.append(
                {
                    "index": base + 2 * k + d,
                    "family": "PRIORITY",
                    "slot": k,
                    "argument": delta,
                    "meaning": f"{'raise' if delta > 0 else 'lower'} priority of slot {k}",
                }
            )
    return table


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "scheduler_ddqn.yaml"
"""Config used by the documentation-table builders when none is given."""

_YAML_KEY = re.compile(r"\b((?:observation|machine|actions|guardrails)\.[A-Za-z_][\w.]*)")


def _cfg_value(cfg: SchedulerConfig, dotted: str) -> Any:
    cursor: Any = cfg
    for part in dotted.split("."):
        cursor = getattr(cursor, part)
    return cursor


def _resolved_normalisation(norm: str, name: str, cfg: SchedulerConfig) -> str:
    """The normalisation text with the YAML values it refers to filled in."""
    parts = []
    for dotted in dict.fromkeys(_YAML_KEY.findall(norm)):
        if dotted == "machine.memory_capacity_mb":
            parts.append(f"`{dotted}` = {cfg.machine.memory_capacity_mb:g}")
            continue
        parts.append(f"`{dotted}` = {_cfg_value(cfg, dotted)!s}")
    if name == "effective_priority":
        aging = window_aging(cfg)
        divisor = max(1.0, cfg.machine.num_priority_levels - 1
                      + (aging.max_boost if aging is not None else 0))  # fmt: skip
        parts.append(
            f"divisor = {divisor:g} (`machine.num_priority_levels` = "
            f"{cfg.machine.num_priority_levels}, `guardrails.aging.max_boost` = "
            f"{cfg.guardrails.aging.max_boost} when aging is on)"
        )
    parts.append(f"then clipped to ±`observation.clip` = {cfg.observation.clip:g}")
    return "; ".join(parts)


def _load_default(config: SchedulerConfig | None) -> SchedulerConfig:
    if config is not None:
        return config
    from .config import load_scheduler_config

    return load_scheduler_config(DEFAULT_CONFIG_PATH)


def _md(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def observation_table_markdown(config: SchedulerConfig | None = None) -> str:
    """GitHub Markdown table of every observation dimension (one row per dimension).

    Built from :func:`active_global_features` / :func:`active_slot_features` via
    :func:`observation_fields`, i.e. the same rows that build the vector (oracle features
    appear only when ``observation.reveal_total_remaining_cpu`` is true). With
    ``config=None`` it loads ``configs/scheduler_ddqn.yaml``.
    """
    cfg = _load_default(config)
    lines = [
        "| Index | Name | Description | Normalisation | Constants (from YAML) |",
        "|---:|---|---|---|---|",
    ]
    for index, (name, desc, norm) in enumerate(observation_fields(cfg)):
        base_name = name.split(".", 1)[-1]
        lines.append(
            f"| {index} | `{_md(name)}` | {_md(desc)} | {_md(norm)} | "
            f"{_md(_resolved_normalisation(norm, base_name, cfg))} |"
        )
    return "\n".join(lines) + "\n"


def action_table_markdown(config: SchedulerConfig | None = None) -> str:
    """GitHub Markdown table of every action index, built from :func:`action_table`.

    With ``config=None`` it loads ``configs/scheduler_ddqn.yaml``.
    """
    cfg = _load_default(config)
    max_adj = cfg.actions.max_priority_adjusts_per_dispatch
    levels = cfg.machine.num_priority_levels
    lines = [
        "| Index | Family | Slot | Time slice (ms) / priority delta | Meaning | Masked when |",
        "|---:|---|---:|---|---|---|",
    ]
    for row in action_table(cfg):
        if row["family"] == "DISPATCH":
            arg = "until burst ends" if row["argument"] == "to_burst_end" else row["argument"]
            masked = f"slot {row['slot']} is empty"
        else:
            arg = f"{row['argument']:+d}"
            bound = f"{levels - 1}" if row["argument"] > 0 else "0"
            masked = (
                f"slot {row['slot']} is empty; or the task's priority + offset is already "
                f"{bound} (range 0..{levels - 1}, `machine.num_priority_levels`); or "
                f"{max_adj} consecutive priority actions were taken since the last dispatch "
                "(`actions.max_priority_adjusts_per_dispatch`)"
            )
        lines.append(
            f"| {row['index']} | {row['family']} | {row['slot']} | {_md(arg)} | "
            f"{_md(row['meaning'])} | {_md(masked)} |"
        )
    return "\n".join(lines) + "\n"


def window_aging(cfg: SchedulerConfig) -> AgingConfig | None:
    """Aging used in the observation encoding (window order, priority feature).

    Depends only on ``guardrails.aging.enabled``, never on the override master switch
    ``guardrails.enabled``, so switching the overrides off does not change what the agent sees.
    """
    if cfg.guardrails.aging.enabled:
        return cfg.guardrails.aging
    return None


def select_window(view: SimView, num_slots: int, aging: AgingConfig | None) -> tuple[TaskView, ...]:
    """Top ``num_slots`` READY tasks by (effective priority desc, ``ready_seq`` asc)."""
    ordered = sorted(view.ready, key=lambda t: (-effective_priority(t, aging), t.ready_seq))
    return tuple(ordered[:num_slots])


@dataclasses.dataclass(frozen=True)
class DecisionState:
    """Observation, action mask and slot → task mapping at one decision point."""

    observation: np.ndarray
    mask: np.ndarray
    window: tuple[TaskView, ...]


def build_decision_state(
    view: SimView,
    recent: RecentStats,
    consecutive_adjusts: int,
    cfg: SchedulerConfig,
) -> DecisionState:
    """Build observation, mask and window. Used by the env AND the plugin (one code path)."""
    obs_cfg = cfg.observation
    num_slots = obs_cfg.num_slots
    num_slices = len(cfg.actions.time_slices_ms)
    aging = window_aging(cfg)
    levels = view.num_priority_levels
    priority_norm = max(1.0, levels - 1 + (aging.max_boost if aging is not None else 0))
    max_adjusts = cfg.actions.max_priority_adjusts_per_dispatch
    ctx = _FeatureContext(
        view=view,
        recent=recent,
        consecutive_adjusts=consecutive_adjusts,
        max_adjusts=max_adjusts,
        aging=aging,
        reveal_total=obs_cfg.reveal_total_remaining_cpu,
        work_norm=obs_cfg.work_norm_ms,
        wait_norm=obs_cfg.wait_norm_ms,
        slack_norm=obs_cfg.slack_norm_ms,
        count_norm=obs_cfg.count_norm,
        rate_norm=obs_cfg.arrival_rate_norm_per_s,
        slack_threshold=obs_cfg.slo_slack_threshold_ms,
        priority_norm=priority_norm,
    )
    window = select_window(view, num_slots, aging)
    slot_features = active_slot_features(cfg)
    n_slot = len(slot_features)
    values = [fn(ctx) for _, _, _, fn in active_global_features(cfg)]
    for task in window:
        values.extend(fn(task, ctx) for _, _, _, fn in slot_features)
    values.extend([0.0] * (n_slot * (num_slots - len(window))))
    obs = np.clip(np.asarray(values, dtype=np.float32), -obs_cfg.clip, obs_cfg.clip)

    mask = np.zeros(num_slots * num_slices + 2 * num_slots, dtype=bool)
    base = num_slots * num_slices
    allow_priority = consecutive_adjusts < max_adjusts
    for k, task in enumerate(window):
        mask[k * num_slices : (k + 1) * num_slices] = True
        if allow_priority:
            level = task.priority + task.priority_adjust
            mask[base + 2 * k] = level + 1 <= levels - 1
            mask[base + 2 * k + 1] = level - 1 >= 0
    return DecisionState(observation=obs, mask=mask, window=window)


def action_to_decision(action: int, state: DecisionState, cfg: SchedulerConfig) -> Decision | None:
    """Decode a flat action index; ``None`` if it is invalid under ``state.mask``."""
    action = int(action)
    if not 0 <= action < state.mask.shape[0] or not state.mask[action]:
        return None
    num_slots = cfg.observation.num_slots
    slices = cfg.actions.time_slices_ms
    base = num_slots * len(slices)
    if action < base:
        slot, j = divmod(action, len(slices))
        return Decision.dispatch(state.window[slot].task_id, slices[j])
    slot, d = divmod(action - base, 2)
    return Decision.adjust_priority(state.window[slot].task_id, 1 if d == 0 else -1)


def first_valid_dispatch(state: DecisionState, cfg: SchedulerConfig) -> int:
    """Index of the first valid DISPATCH action (always exists at a decision point)."""
    base = cfg.observation.num_slots * len(cfg.actions.time_slices_ms)
    valid = np.flatnonzero(state.mask[:base])
    if valid.size == 0:
        raise RuntimeError("no valid dispatch action at a decision point")
    return int(valid[0])


class SchedulerEnv(gym.Env):
    """Gymnasium environment: one step = one decision (see module docstring)."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        config: SchedulerConfig,
        load_profile: str | None = None,
        workload: Sequence[Task] | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.layout = obs_layout(config)
        self.OBSERVATION_FIELDS = observation_fields(config)
        self.ACTION_TABLE = action_table(config)
        clip = config.observation.clip
        self.observation_space = gym.spaces.Box(
            low=-clip, high=clip, shape=(self.layout.obs_dim,), dtype=np.float32
        )
        self.action_space = gym.spaces.Discrete(self.layout.n_actions)
        self.guardrails = GuardrailEngine(config.guardrails)
        self.recent = RecentStatsTracker(
            config.observation.recent_time_constant_ms, config.observation.recent_completions
        )
        self._default_load = load_profile
        self._default_workload = list(workload) if workload is not None else None
        self.sim: SchedulerSim | None = None
        self._state: DecisionState | None = None
        self._consecutive_adjusts = 0
        self.steps = 0
        self.invalid_actions = 0
        self.episode_return = 0.0
        self.load_profile: str | None = None

    # ------------------------------------------------------------------ gym API
    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Start an episode on ``options["workload"]`` or a workload generated for
        ``options["load_profile"]`` (falling back to the constructor arguments) and ``seed``."""
        super().reset(seed=seed)
        options = options or {}
        workload = options.get("workload", self._default_workload)
        load = options.get("load_profile", self._default_load)
        if workload is None:
            if load is None or seed is None:
                raise ValueError("reset needs a workload, or a load_profile and a seed")
            workload = generate_workload(self.config.workload, load, int(seed))
        self.load_profile = load
        self.sim = SchedulerSim(workload, self.config.machine)
        self.recent.reset()
        self.guardrails.reset(clear_latch=True)
        self._consecutive_adjusts = 0
        self.steps = 0
        self.invalid_actions = 0
        self.episode_return = 0.0
        self._state = self._decision_state()
        info = self._base_info()
        return self._state.observation.copy(), info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute a flat action through the guardrails (see module docstring)."""
        state = self._require_state()
        assert self.sim is not None
        proposed = action_to_decision(action, state, self.config)
        invalid = proposed is None
        if invalid:
            self.invalid_actions += 1
            proposed = action_to_decision(
                first_valid_dispatch(state, self.config), state, self.config
            )
            assert proposed is not None
        result = self.guardrails.filter(self.sim.view(), proposed)
        penalty = self.config.reward.invalid_action_penalty if invalid else 0.0
        return self._execute(
            result.decision,
            proposed=proposed,
            rule=result.rule,
            rules_fired=result.rules_fired,
            overridden=result.overridden,
            invalid=invalid,
            penalty=penalty,
        )

    def step_decision(
        self, decision: Decision
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute a :class:`Decision` directly (no guardrails); same 5-tuple as :meth:`step`."""
        self._require_state()
        return self._execute(
            decision,
            proposed=decision,
            rule=None,
            rules_fired=(),
            overridden=False,
            invalid=False,
            penalty=0.0,
        )

    def action_masks(self) -> np.ndarray:
        """Boolean mask of valid actions at the current state."""
        return self._require_state().mask.copy()

    def report_q_values(self, q_values: np.ndarray) -> bool:
        """Hand the agent's Q-values to the guardrail engine before calling :meth:`step`
        (magnitude checked on the currently valid actions only)."""
        return self.guardrails.report_q_values(q_values, self._require_state().mask)

    # ------------------------------------------------------------------ helpers
    @property
    def decision_state(self) -> DecisionState:
        """Observation, mask and window at the current decision point."""
        return self._require_state()

    @property
    def consecutive_priority_adjusts(self) -> int:
        """Priority actions executed since the last dispatch."""
        return self._consecutive_adjusts

    def view(self) -> SimView:
        """Current simulator view."""
        assert self.sim is not None
        return self.sim.view()

    def _require_state(self) -> DecisionState:
        if self._state is None or self.sim is None:
            raise RuntimeError("call reset() first")
        return self._state

    def _decision_state(self) -> DecisionState:
        assert self.sim is not None
        return build_decision_state(
            self.sim.view(), self.recent.snapshot(), self._consecutive_adjusts, self.config
        )

    def _base_info(self) -> dict[str, Any]:
        state = self._require_state()
        return {
            "action_mask": state.mask.copy(),
            "sim_time_ms": self.sim.now if self.sim is not None else 0.0,
            "invalid_actions": self.invalid_actions,
            "guardrail": None,
            "rules_fired": (),
            "overridden": False,
            "guardrail_counts": dict(self.guardrails.counts),
            "q_latched": self.guardrails.latched,
        }

    def _execute(
        self,
        decision: Decision,
        *,
        proposed: Decision,
        rule: str | None,
        rules_fired: tuple[str, ...],
        overridden: bool,
        invalid: bool,
        penalty: float,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        assert self.sim is not None
        if self.sim.done:
            raise RuntimeError("episode is over; call reset()")
        outcome = self.sim.execute(decision)
        late = set(outcome.late_completed)
        self.guardrails.record_completions(
            self.sim.now, [task_id in late for task_id in outcome.completed]
        )
        self.recent.update(outcome)
        if decision.is_dispatch:
            self._consecutive_adjusts = 0
        else:
            self._consecutive_adjusts += 1
        reward = compute_reward(outcome, self.config.reward) - penalty
        self.steps += 1
        self.episode_return += reward
        terminated = self.sim.done
        truncated = (not terminated) and self.steps >= self.config.training.max_steps_per_episode
        self._state = self._decision_state()
        info = self._base_info()
        info.update(
            {
                "decision": decision,
                "proposed": proposed,
                "guardrail": rule,
                "rules_fired": rules_fired,
                "overridden": overridden,
                "invalid_action": invalid,
                "outcome": outcome,
            }
        )
        return self._state.observation.copy(), reward, terminated, truncated, info
