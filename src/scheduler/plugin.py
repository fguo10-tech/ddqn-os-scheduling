"""Plugin interface for platform engineers.

A platform (a batch queue, a job scheduler, a simulator) hands the plugin a
:class:`QueueSnapshot` at each decision point and receives a :class:`SchedulingDecision`;
after acting it reports what finished through :meth:`SchedulerPlugin.observe`.

:class:`DDQNSchedulerPlugin` converts the snapshot into the simulator's
:class:`~src.scheduler.simulator.SimView` and then calls exactly the functions the
environment uses (:func:`~src.scheduler.env.build_decision_state`,
:func:`~src.scheduler.env.action_to_decision`, the
:class:`~src.scheduler.guardrails.GuardrailEngine`), so the observation it feeds the agent is
built by one code path and there is no train / serve skew. ``tests/test_scheduler_plugin.py``
proves that a plugin driven by simulator snapshots makes the same decisions as the agent
inside the environment.

``decided_by`` is one of ``"agent"``, ``"guardrail:starvation"``,
``"guardrail:slo_fallback"``, ``"fallback:q_divergence"``; a :class:`BaselineSchedulerPlugin`
reports ``"baseline:<name>"``.

This is research code: it has not been deployed on any real platform.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .agent import DoubleDQNAgent, masked_argmax
from .baselines import Policy
from .config import SchedulerConfig, with_guardrails
from .env import (
    RecentStats,
    action_to_decision,
    build_decision_state,
)
from .guardrails import GuardrailEngine, decided_by
from .simulator import Decision, SimView, TaskView


@dataclasses.dataclass(frozen=True)
class JobView:
    """One waiting job as the platform sees it.

    ``job_class`` should be one of the task classes of the config the agent was trained with
    (the keys of ``workload.task_types``, e.g. ``cpu_bound`` for the benchmark config or
    ``inference_request`` for the LLM-style workload profile). The observation has one one-hot
    column per class, so a job of an unknown class is encoded with all of them at zero.
    """

    job_id: int
    queue_wait_ms: float
    expected_remaining_work_ms: float
    expected_next_burst_ms: float
    memory_request_mb: float
    priority: int
    priority_offset: int
    deadline_slack_ms: float
    started: bool
    job_class: str
    queue_seq: int
    time_in_system_ms: float
    dispatched_before: bool


@dataclasses.dataclass(frozen=True)
class ResourceState:
    """Machine state and recent-history signals measured by the platform."""

    memory_capacity_mb: float
    resident_memory_mb: float
    blocked_jobs: int
    num_priority_levels: int
    recent_cpu_utilisation: float
    recent_arrival_rate_per_s: float
    recent_slo_violation_rate: float
    last_job_id: int | None


@dataclasses.dataclass(frozen=True)
class QueueSnapshot:
    """Everything the plugin may look at when deciding: time, waiting jobs, resources."""

    now_ms: float
    jobs: tuple[JobView, ...]
    resources: ResourceState


@dataclasses.dataclass(frozen=True)
class SchedulingDecision:
    """Run ``job_id`` for ``time_slice_ms`` (``None`` = until its burst ends), or, if
    ``priority_change`` is set, change its priority offset by that amount and run nothing."""

    job_id: int
    time_slice_ms: float | None
    priority_change: int | None
    decided_by: str

    def to_decision(self) -> Decision:
        """The simulator :class:`Decision` with the same meaning."""
        if self.priority_change is not None:
            return Decision.adjust_priority(self.job_id, self.priority_change)
        return Decision.dispatch(self.job_id, self.time_slice_ms)


@dataclasses.dataclass(frozen=True)
class SchedulingFeedback:
    """What happened after a decision: the time and the jobs that completed (and were late)."""

    now_ms: float
    completed_job_ids: tuple[int, ...]
    late_job_ids: tuple[int, ...]


@dataclasses.dataclass(frozen=True)
class PluginHealth:
    """Plugin status for monitoring."""

    healthy: bool
    latched: bool
    decisions: int
    guardrail_counts: dict[str, int]
    message: str


@runtime_checkable
class SchedulerPlugin(Protocol):
    """What a platform needs from a scheduling plugin."""

    name: str

    def reset(self) -> None:
        """Start over (new episode / new queue)."""

    def decide(self, snapshot: QueueSnapshot) -> SchedulingDecision:
        """Choose one decision for the current snapshot."""

    def observe(self, feedback: SchedulingFeedback) -> None:
        """Receive feedback after the decision was carried out."""

    def health(self) -> PluginHealth:
        """Report health."""


def snapshot_from_view(view: SimView, recent: RecentStats) -> QueueSnapshot:
    """Build the snapshot a platform would send, from a simulator view and recent stats."""
    jobs = tuple(
        JobView(
            job_id=t.task_id,
            queue_wait_ms=t.wait_ms,
            expected_remaining_work_ms=t.remaining_total_cpu_ms,
            expected_next_burst_ms=t.remaining_burst_ms,
            memory_request_mb=t.memory_mb,
            priority=t.priority,
            priority_offset=t.priority_adjust,
            deadline_slack_ms=t.deadline_ms - view.now_ms,
            started=t.started,
            job_class=t.task_type,
            queue_seq=t.ready_seq,
            time_in_system_ms=t.time_in_system_ms,
            dispatched_before=t.dispatched_before,
        )
        for t in view.ready
    )
    resources = ResourceState(
        memory_capacity_mb=view.memory_capacity_mb,
        resident_memory_mb=view.resident_mb,
        blocked_jobs=view.n_blocked,
        num_priority_levels=view.num_priority_levels,
        recent_cpu_utilisation=recent.cpu_utilisation,
        recent_arrival_rate_per_s=recent.arrival_rate_per_s,
        recent_slo_violation_rate=recent.slo_violation_rate,
        last_job_id=view.last_task_id,
    )
    return QueueSnapshot(now_ms=view.now_ms, jobs=jobs, resources=resources)


def view_from_snapshot(snapshot: QueueSnapshot) -> SimView:
    """Inverse of :func:`snapshot_from_view` (FIFO order by ``queue_seq``)."""
    now = snapshot.now_ms
    ready = tuple(
        TaskView(
            task_id=j.job_id,
            task_type=j.job_class,
            arrival_ms=now - j.time_in_system_ms,
            priority=j.priority,
            priority_adjust=j.priority_offset,
            ready_seq=j.queue_seq,
            wait_ms=j.queue_wait_ms,
            remaining_burst_ms=j.expected_next_burst_ms,
            remaining_total_cpu_ms=j.expected_remaining_work_ms,
            memory_mb=j.memory_request_mb,
            started=j.started,
            dispatched_before=j.dispatched_before,
            deadline_ms=now + j.deadline_slack_ms,
            time_in_system_ms=j.time_in_system_ms,
        )
        for j in sorted(snapshot.jobs, key=lambda j: j.queue_seq)
    )
    res = snapshot.resources
    return SimView(
        now_ms=now,
        ready=ready,
        n_blocked=res.blocked_jobs,
        n_future=0,
        n_done=0,
        resident_mb=res.resident_memory_mb,
        memory_capacity_mb=res.memory_capacity_mb,
        num_priority_levels=res.num_priority_levels,
        last_task_id=res.last_job_id,
    )


def _recent(snapshot: QueueSnapshot) -> RecentStats:
    res = snapshot.resources
    return RecentStats(
        cpu_utilisation=res.recent_cpu_utilisation,
        arrival_rate_per_s=res.recent_arrival_rate_per_s,
        slo_violation_rate=res.recent_slo_violation_rate,
    )


class DDQNSchedulerPlugin:
    """Trained Double DQN agent + guardrail engine (with its fallback baseline) as a plugin.

    The agent acts greedily over valid actions. If the agent raises an exception while
    computing Q-values, the engine is latched exactly as for NaN Q-values and the fallback
    baseline decides. The Q-divergence latch survives :meth:`reset` unless
    ``clear_latch=True`` is passed (an operator decision).
    """

    name = "ddqn"

    def __init__(self, agent: DoubleDQNAgent, config: SchedulerConfig, guardrails: bool = True):
        self.agent = agent
        self.config = with_guardrails(config, guardrails and config.guardrails.enabled)
        self.engine = GuardrailEngine(self.config.guardrails)
        self._consecutive_adjusts = 0
        self._decisions = 0
        self._last_error: str | None = None

    def reset(self, clear_latch: bool = False) -> None:
        """Clear per-episode state; keep the Q-divergence latch unless ``clear_latch``."""
        self.engine.reset(clear_latch=clear_latch)
        self._consecutive_adjusts = 0
        self._decisions = 0

    def decide(self, snapshot: QueueSnapshot) -> SchedulingDecision:
        """Observation → Q-values → masked greedy action → guardrails → decision."""
        if not snapshot.jobs:
            raise ValueError("decide() needs at least one waiting job")
        view = view_from_snapshot(snapshot)
        state = build_decision_state(
            view, _recent(snapshot), self._consecutive_adjusts, self.config
        )
        try:
            q_values = self.agent.q_values(state.observation)
        except Exception as exc:  # noqa: BLE001 - any model failure must fall back safely
            self._last_error = f"{type(exc).__name__}: {exc}"
            q_values = [float("nan")] * int(state.mask.shape[0])
        self.engine.report_q_values(q_values, state.mask)
        try:
            action = masked_argmax(q_values, state.mask)  # type: ignore[arg-type]
        except ValueError:
            action = 0
        proposed = action_to_decision(action, state, self.config)
        if proposed is None:  # only possible with non-finite Q-values; the engine is latched
            first = state.window[0]
            proposed = Decision.dispatch(first.task_id, self.config.actions.time_slices_ms[0])
        result = self.engine.filter(view, proposed)
        decision = result.decision
        self._consecutive_adjusts = 0 if decision.is_dispatch else self._consecutive_adjusts + 1
        self._decisions += 1
        return SchedulingDecision(
            job_id=decision.task_id,
            time_slice_ms=decision.time_slice_ms if decision.is_dispatch else None,
            priority_change=None if decision.is_dispatch else decision.delta,
            decided_by=decided_by(result.rule),
        )

    def observe(self, feedback: SchedulingFeedback) -> None:
        """Feed completions (and which were late) to the SLO fallback rule."""
        late = set(feedback.late_job_ids)
        self.engine.record_completions(
            feedback.now_ms, [job_id in late for job_id in feedback.completed_job_ids]
        )

    def health(self) -> PluginHealth:
        """Healthy unless the Q-divergence latch is engaged."""
        latched = self.engine.latched
        message = "ok"
        if latched:
            message = f"latched: {self.engine.last_q_problem}"
            if self._last_error:
                message += f" ({self._last_error})"
        return PluginHealth(
            healthy=not latched,
            latched=latched,
            decisions=self._decisions,
            guardrail_counts=dict(self.engine.counts),
            message=message,
        )


class BaselineSchedulerPlugin:
    """Any baseline :class:`~src.scheduler.baselines.Policy` as a plugin."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.name = f"baseline:{policy.name}"
        self._decisions = 0

    def reset(self) -> None:
        """Reset the wrapped policy."""
        self.policy.reset()
        self._decisions = 0

    def decide(self, snapshot: QueueSnapshot) -> SchedulingDecision:
        """Ask the wrapped policy."""
        if not snapshot.jobs:
            raise ValueError("decide() needs at least one waiting job")
        decision = self.policy.decide(view_from_snapshot(snapshot))
        self._decisions += 1
        return SchedulingDecision(
            job_id=decision.task_id,
            time_slice_ms=decision.time_slice_ms if decision.is_dispatch else None,
            priority_change=None if decision.is_dispatch else decision.delta,
            decided_by=self.name,
        )

    def observe(self, feedback: SchedulingFeedback) -> None:
        """Baselines ignore feedback."""

    def health(self) -> PluginHealth:
        """Always healthy."""
        return PluginHealth(True, False, self._decisions, {}, "ok")


def feedback_from_outcome(
    now_ms: float, completed: Sequence[int], late: Sequence[int]
) -> SchedulingFeedback:
    """Convenience constructor for :class:`SchedulingFeedback`."""
    return SchedulingFeedback(now_ms, tuple(completed), tuple(late))
