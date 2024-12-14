"""Textbook baseline schedulers.

Every baseline sees the whole ready queue (not only the agent's window) and the same
burst-length information the agent sees (the exact remaining time of the current CPU
burst). They are the plain textbook algorithms with no extra cleverness:

* :class:`FCFS` — READY task with the smallest ``ready_seq``; run until its burst ends.
* :class:`SJF` — non-preemptive shortest next CPU burst; ties by ``ready_seq``.
* :class:`RoundRobin` — smallest ``ready_seq`` for one quantum.
* :class:`PriorityPolicy` — non-preemptive, highest effective priority first.

* :class:`SRTF` — preemptive shortest remaining burst first, one quantum at a time. A
  **reference**, not a textbook baseline (see its docstring).

FCFS, SJF, RR and Priority are the four baselines of the Before / After comparison; SRTF
is a reference policy only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .config import AgingConfig, BaselinesConfig
from .simulator import Decision, SimView, effective_priority


@runtime_checkable
class Policy(Protocol):
    """A scheduling policy: picks one :class:`Decision` per decision point."""

    name: str

    def reset(self) -> None:
        """Forget any per-episode state."""

    def decide(self, view: SimView) -> Decision:
        """Return the decision for the current decision point."""


class FCFS:
    """First-Come-First-Serve: oldest ready-queue entry, run to the end of its burst."""

    name = "fcfs"

    def reset(self) -> None:
        """FCFS keeps no state."""

    def decide(self, view: SimView) -> Decision:
        """Dispatch the READY task with the smallest ``ready_seq``."""
        task = min(view.ready, key=lambda t: t.ready_seq)
        return Decision.dispatch(task.task_id, None)


class SJF:
    """Non-preemptive Shortest Job First (shortest remaining current CPU burst)."""

    name = "sjf"

    def reset(self) -> None:
        """SJF keeps no state."""

    def decide(self, view: SimView) -> Decision:
        """Dispatch the READY task with the shortest current burst (ties by ``ready_seq``)."""
        task = min(view.ready, key=lambda t: (t.remaining_burst_ms, t.ready_seq))
        return Decision.dispatch(task.task_id, None)


class RoundRobin:
    """Round Robin with a fixed quantum."""

    name = "round_robin"

    def __init__(self, quantum_ms: float) -> None:
        if quantum_ms <= 0:
            raise ValueError("quantum_ms must be positive")
        self.quantum_ms = float(quantum_ms)

    def reset(self) -> None:
        """Round Robin keeps no state beyond the ready-queue order."""

    def decide(self, view: SimView) -> Decision:
        """Dispatch the oldest ready-queue entry for one quantum."""
        task = min(view.ready, key=lambda t: t.ready_seq)
        return Decision.dispatch(task.task_id, self.quantum_ms)


class PriorityPolicy:
    """Non-preemptive Priority scheduling (higher number = higher priority).

    Added by this repository. Aging is used only when
    ``aging`` is given and enabled (the shipped config keeps static priorities).
    """

    name = "priority"

    def __init__(self, aging: AgingConfig | None = None) -> None:
        self.aging = aging

    def reset(self) -> None:
        """Priority scheduling keeps no state."""

    def decide(self, view: SimView) -> Decision:
        """Dispatch the highest effective priority (ties by ``ready_seq``) to burst end."""
        task = min(view.ready, key=lambda t: (-effective_priority(t, self.aging), t.ready_seq))
        return Decision.dispatch(task.task_id, None)


class SRTF:
    """Preemptive Shortest Remaining (burst) Time First: a **reference** policy.

    At each decision point it runs the READY task with the smallest remaining current CPU
    burst (ties by ``ready_seq``) for ``quantum_ms``, so a newly arrived shorter burst
    takes over at the next quantum boundary.

    Why it exists: the Double DQN agent may preempt with short time slices, while textbook
    (non-preemptive) SJF may not. SRTF is the simple heuristic with the same information
    (exact remaining burst) and the same freedom (preemption at the agent's shortest slice),
    so it shows how much of the agent's gain over SJF is just preemption. It is not one of
    the four textbook baselines of the Before / After comparison;
    ``[Assumption — not in paper]``.
    """

    name = "srtf"

    def __init__(self, quantum_ms: float) -> None:
        if quantum_ms <= 0:
            raise ValueError("quantum_ms must be positive")
        self.quantum_ms = float(quantum_ms)

    def reset(self) -> None:
        """SRTF keeps no state."""

    def decide(self, view: SimView) -> Decision:
        """Dispatch the shortest remaining current burst (ties by ``ready_seq``) for a quantum."""
        task = min(view.ready, key=lambda t: (t.remaining_burst_ms, t.ready_seq))
        return Decision.dispatch(task.task_id, self.quantum_ms)


def make_policy(name: str, cfg: BaselinesConfig) -> Policy:
    """Build baseline ``name`` (``fcfs``, ``sjf``, ``round_robin``, ``priority``) or the
    ``srtf`` reference."""
    if name == "fcfs":
        return FCFS()
    if name == "sjf":
        return SJF()
    if name == "round_robin":
        return RoundRobin(cfg.round_robin.quantum_ms)
    if name == "priority":
        prio = cfg.priority
        aging = AgingConfig(
            enabled=prio.use_aging,
            interval_ms=prio.aging_interval_ms,
            max_boost=prio.aging_max_boost,
        )
        return PriorityPolicy(aging if prio.use_aging else None)
    if name == "srtf":
        return SRTF(cfg.srtf.quantum_ms)
    raise ValueError(f"unknown baseline {name!r}")


def make_fallback_policy(name: str, quantum_ms: float) -> Policy:
    """Baseline used by the Q-divergence guardrail (static priorities, no aging)."""
    if name == "fcfs":
        return FCFS()
    if name == "sjf":
        return SJF()
    if name == "round_robin":
        return RoundRobin(quantum_ms)
    if name == "priority":
        return PriorityPolicy(None)
    raise ValueError(f"unknown fallback policy {name!r}")
