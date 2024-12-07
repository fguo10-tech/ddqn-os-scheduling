"""Discrete-event simulator of single-CPU operating-system scheduling.

This is a simulator, not a kernel modification. The machine model below is this
repository's ``[Assumption — not in paper]``.

Machine model
-------------
* One CPU. A **decision point** is any moment at which the CPU is free and at least one
  task is READY; exactly one :class:`Decision` is executed per decision point.
* ``Decision.dispatch(task_id, time_slice_ms)`` runs the task for wall time
  ``min(time_slice, remaining_burst * slowdown)`` (``time_slice=None`` = until the burst
  ends); progress is ``wall / slowdown``. On its first dispatch a task becomes *started* and
  its memory is added to resident memory until the task finishes.
* Thrashing (soft memory constraint): ``slowdown = 1 + thrash_penalty *
  max(0, resident_mb / memory_capacity_mb - 1)``, evaluated at dispatch time (including the
  dispatched task's own memory) and held for the slice.
* Context switch: if the dispatched task differs from the previously running one,
  ``context_switch_ms`` of wall time passes first with no progress. The very first dispatch
  of an episode (no previous task) is not charged.
* ``Decision.adjust_priority(task_id, ±1)`` changes the task's ``priority_adjust`` (clamped so
  that ``priority + priority_adjust`` stays in ``[0, num_priority_levels - 1]``), costs
  ``priority_adjust_overhead_ms`` and runs nothing.
* After a decision, if nothing is READY but tasks are FUTURE or BLOCKED, time jumps to the
  next event (idle) until a task is READY.
* Equal timestamps: arrivals (by ``task_id``), then I/O returns (by ``task_id``), then the
  just-preempted task. Every entry into the ready queue takes the next ``ready_seq``.

Accounting choices
------------------
* ``busy_ms`` is wall time a task spends on the CPU (including thrashing slowdown);
  context-switch and priority-adjust overheads are counted as ``overhead_ms``, not busy.
* A dispatched task stops being READY (waiting) at the decision instant, so a context
  switch is not waiting time. ``first_dispatch_ms`` is the instant it starts executing
  (after any context switch), so response time includes the switch; ``response_wait_ms``
  in a step outcome accrues on the same definition.
"""

from __future__ import annotations

import dataclasses
import heapq
import math
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from .config import AgingConfig, MachineConfig
from .tasks import Task, TaskState

if TYPE_CHECKING:
    from .baselines import Policy

_EPS = 1e-9


@dataclasses.dataclass(frozen=True)
class Decision:
    """One scheduling decision.

    ``kind`` is ``"dispatch"`` (run ``task_id`` for ``time_slice_ms``; ``None`` = until the
    current CPU burst ends) or ``"priority"`` (change ``priority_adjust`` by ``delta``).
    """

    kind: str
    task_id: int
    time_slice_ms: float | None = None
    delta: int = 0

    @staticmethod
    def dispatch(task_id: int, time_slice_ms: float | None = None) -> Decision:
        """Run ``task_id`` for ``time_slice_ms`` (``None``: until its burst ends)."""
        return Decision("dispatch", int(task_id), time_slice_ms, 0)

    @staticmethod
    def adjust_priority(task_id: int, delta: int) -> Decision:
        """Raise (``+1``) or lower (``-1``) the priority offset of ``task_id``."""
        if delta not in (1, -1):
            raise ValueError("priority delta must be +1 or -1")
        return Decision("priority", int(task_id), None, int(delta))

    @property
    def is_dispatch(self) -> bool:
        """True for a dispatch decision."""
        return self.kind == "dispatch"

    def describe(self) -> str:
        """Short human-readable form, e.g. ``dispatch(3, 20.0)``."""
        if self.is_dispatch:
            return f"dispatch({self.task_id}, {self.time_slice_ms})"
        return f"priority({self.task_id}, {self.delta:+d})"


@dataclasses.dataclass(frozen=True, slots=True)
class TaskView:
    """Read-only view of one READY task at a decision point (what a policy may look at)."""

    task_id: int
    task_type: str
    arrival_ms: float
    priority: int
    priority_adjust: int
    ready_seq: int
    wait_ms: float
    remaining_burst_ms: float
    remaining_total_cpu_ms: float
    memory_mb: float
    started: bool
    dispatched_before: bool
    deadline_ms: float
    time_in_system_ms: float

    @property
    def base_priority(self) -> int:
        """``priority + priority_adjust`` (no aging)."""
        return self.priority + self.priority_adjust


@dataclasses.dataclass(frozen=True)
class SimView:
    """Read-only snapshot of the simulator at a decision point.

    ``ready`` is ordered by ``ready_seq`` (FIFO order).
    """

    now_ms: float
    ready: tuple[TaskView, ...]
    n_blocked: int
    n_future: int
    n_done: int
    resident_mb: float
    memory_capacity_mb: float
    num_priority_levels: int
    last_task_id: int | None

    def get(self, task_id: int) -> TaskView | None:
        """The READY task with ``task_id``, or ``None``."""
        for view in self.ready:
            if view.task_id == task_id:
                return view
        return None


@dataclasses.dataclass(frozen=True)
class StepOutcome:
    """Everything that happened while one decision was executed (plus any idle time after it)."""

    decision: Decision
    start_ms: float
    end_ms: float
    duration_ms: float
    wait_ms: float
    in_system_ms: float
    response_wait_ms: float
    busy_ms: float
    idle_ms: float
    overhead_ms: float
    arrivals: int
    completed: tuple[int, ...]
    late_completed: tuple[int, ...]
    deadline_misses: tuple[int, ...]
    context_switch: bool
    done: bool


def aging_boost(wait_ms: float, interval_ms: float, max_boost: int) -> int:
    """``min(max_boost, floor(wait_ms / interval_ms))`` (0 for non-positive waits)."""
    if wait_ms <= 0 or interval_ms <= 0:
        return 0
    return int(min(max_boost, math.floor(wait_ms / interval_ms)))


def effective_priority(task: TaskView, aging: AgingConfig | None) -> int:
    """Pure function: ``priority + priority_adjust + aging_boost`` (boost 0 if aging is off)."""
    boost = 0
    if aging is not None and aging.enabled:
        boost = aging_boost(task.wait_ms, aging.interval_ms, aging.max_boost)
    return task.priority + task.priority_adjust + boost


class _Accrual:
    __slots__ = ("wait", "in_system", "response", "busy", "idle", "overhead", "arrivals")

    def __init__(self) -> None:
        self.wait = 0.0
        self.in_system = 0.0
        self.response = 0.0
        self.busy = 0.0
        self.idle = 0.0
        self.overhead = 0.0
        self.arrivals = 0


class SchedulerSim:
    """Single-CPU discrete-event simulator (see module docstring for the semantics).

    The simulator works on private copies of the given tasks (:meth:`Task.fresh`), so the
    same workload list can be replayed by several schedulers.
    """

    def __init__(self, tasks: Iterable[Task], machine: MachineConfig) -> None:
        self.machine = machine
        copies = [task.fresh() for task in tasks]
        if not copies:
            raise ValueError("a workload needs at least one task")
        self.tasks: dict[int, Task] = {}
        for task in copies:
            if task.task_id in self.tasks:
                raise ValueError(f"duplicate task_id {task.task_id}")
            if not 0 <= task.priority < machine.num_priority_levels:
                raise ValueError(f"task {task.task_id}: priority out of range")
            self.tasks[task.task_id] = task
        self._future: list[int] = [
            t.task_id for t in sorted(copies, key=lambda t: (t.arrival_ms, t.task_id))
        ]
        self._future_pos = 0
        self._blocked: list[tuple[float, int]] = []
        self._ready: list[int] = []
        self._deadlines: list[tuple[float, int]] = sorted(
            (t.deadline_ms, t.task_id) for t in copies
        )
        self._deadline_pos = 0
        self._ready_seq = 0
        self._n_ready = 0
        self._n_never = 0
        self._n_in_system = 0
        self._n_done = 0
        self.resident_mb = 0.0
        self.last_task_id: int | None = None
        self.first_arrival_ms = min(t.arrival_ms for t in copies)
        self.last_arrival_ms = max(t.arrival_ms for t in copies)
        self.now = self.first_arrival_ms
        self.total_busy_ms = 0.0
        self.total_idle_ms = 0.0
        self.total_overhead_ms = 0.0
        self.total_work_ms = 0.0
        self.n_decisions = 0
        self.n_dispatches = 0
        self.n_context_switches = 0
        self.n_priority_adjusts = 0
        self.n_preemptions = 0
        self._acc = _Accrual()
        self._admit_until(self.now)
        self._acc = _Accrual()

    # ------------------------------------------------------------------ queries
    @property
    def done(self) -> bool:
        """True when every task is DONE."""
        return self._n_done == len(self.tasks)

    @property
    def at_decision_point(self) -> bool:
        """True when the CPU is free and at least one task is READY."""
        return bool(self._ready) and not self.done

    @property
    def ready_ids(self) -> tuple[int, ...]:
        """READY task ids in FIFO (``ready_seq``) order."""
        return tuple(self._ready)

    def slowdown(self) -> float:
        """Current thrashing slowdown factor (>= 1)."""
        ratio = self.resident_mb / self.machine.memory_capacity_mb
        return 1.0 + self.machine.thrash_penalty * max(0.0, ratio - 1.0)

    def task_view(self, task: Task) -> TaskView:
        """Build the :class:`TaskView` of a READY task."""
        return TaskView(
            task_id=task.task_id,
            task_type=task.task_type,
            arrival_ms=task.arrival_ms,
            priority=task.priority,
            priority_adjust=task.priority_adjust,
            ready_seq=task.ready_seq,
            wait_ms=self.now - (task.ready_since_ms if task.ready_since_ms is not None else 0.0),
            remaining_burst_ms=task.remaining_burst_ms,
            remaining_total_cpu_ms=task.remaining_total_cpu_ms,
            memory_mb=task.memory_mb,
            started=task.started,
            dispatched_before=task.first_dispatch_ms is not None,
            deadline_ms=task.deadline_ms,
            time_in_system_ms=self.now - task.arrival_ms,
        )

    def view(self) -> SimView:
        """Snapshot for policies and the environment."""
        tasks = self.tasks
        return SimView(
            now_ms=self.now,
            ready=tuple(self.task_view(tasks[i]) for i in self._ready),
            n_blocked=len(self._blocked),
            n_future=len(self._future) - self._future_pos,
            n_done=self._n_done,
            resident_mb=self.resident_mb,
            memory_capacity_mb=self.machine.memory_capacity_mb,
            num_priority_levels=self.machine.num_priority_levels,
            last_task_id=self.last_task_id,
        )

    # ------------------------------------------------------------------ events
    def _next_arrival_time(self) -> float:
        if self._future_pos < len(self._future):
            return self.tasks[self._future[self._future_pos]].arrival_ms
        return math.inf

    def _enter_ready(self, task: Task) -> None:
        task.state = TaskState.READY
        task.ready_since_ms = self.now
        task.ready_seq = self._ready_seq
        self._ready_seq += 1
        self._ready.append(task.task_id)
        self._n_ready += 1

    def _admit_until(self, t: float) -> None:
        """Process arrivals and I/O returns with timestamp exactly ``t`` (== now)."""
        while self._future_pos < len(self._future):
            task = self.tasks[self._future[self._future_pos]]
            if task.arrival_ms > t:
                break
            self._future_pos += 1
            self._n_in_system += 1
            self._n_never += 1
            self._acc.arrivals += 1
            self._enter_ready(task)
        while self._blocked and self._blocked[0][0] <= t:
            _, task_id = heapq.heappop(self._blocked)
            task = self.tasks[task_id]
            task.remaining_burst_ms = float(task.cpu_bursts_ms[task.burst_index])
            self._enter_ready(task)

    def _accrue(self, dt: float, mode: str) -> None:
        if dt <= 0:
            return
        acc = self._acc
        acc.wait += self._n_ready * dt
        acc.in_system += self._n_in_system * dt
        acc.response += self._n_never * dt
        if mode == "busy":
            acc.busy += dt
        elif mode == "idle":
            acc.idle += dt
        else:
            acc.overhead += dt

    def _advance(self, t_end: float, mode: str) -> None:
        """Move time to ``t_end``, processing every event with timestamp <= ``t_end``."""
        while True:
            next_arrival = self._next_arrival_time()
            next_io = self._blocked[0][0] if self._blocked else math.inf
            t_event = min(next_arrival, next_io)
            if t_event > t_end:
                break
            self._accrue(t_event - self.now, mode)
            self.now = max(self.now, t_event)
            self._admit_until(self.now)
        self._accrue(t_end - self.now, mode)
        self.now = max(self.now, t_end)

    def _process_deadlines(self) -> list[int]:
        missed: list[int] = []
        while self._deadline_pos < len(self._deadlines):
            deadline, task_id = self._deadlines[self._deadline_pos]
            if deadline > self.now:
                break
            self._deadline_pos += 1
            task = self.tasks[task_id]
            if task.finish_ms is None or task.finish_ms > deadline:
                task.deadline_missed = True
                missed.append(task_id)
        return missed

    # ------------------------------------------------------------------ step
    def execute(self, decision: Decision) -> StepOutcome:
        """Execute one decision at the current decision point and return what happened."""
        if not self.at_decision_point:
            raise RuntimeError("execute() called when the simulator is not at a decision point")
        task = self.tasks.get(decision.task_id)
        if task is None or task.state is not TaskState.READY:
            raise ValueError(f"task {decision.task_id} is not READY")
        self._acc = _Accrual()
        start = self.now
        completed: list[int] = []
        context_switch = False
        self.n_decisions += 1

        if decision.kind == "priority":
            if decision.delta not in (1, -1):
                raise ValueError("priority delta must be +1 or -1")
            low = -task.priority
            high = self.machine.num_priority_levels - 1 - task.priority
            task.priority_adjust = int(min(high, max(low, task.priority_adjust + decision.delta)))
            self.n_priority_adjusts += 1
            self._advance(self.now + self.machine.priority_adjust_overhead_ms, "overhead")
        elif decision.kind == "dispatch":
            if decision.time_slice_ms is not None and decision.time_slice_ms <= 0:
                raise ValueError("time slice must be positive or None")
            self._ready.remove(task.task_id)
            self._n_ready -= 1
            waited = self.now - (task.ready_since_ms if task.ready_since_ms is not None else 0.0)
            task.total_wait_ms += waited
            task.longest_wait_ms = max(task.longest_wait_ms, waited)
            task.ready_since_ms = None
            task.state = TaskState.RUNNING
            task.dispatch_count += 1
            self.n_dispatches += 1
            if self.last_task_id is not None and self.last_task_id != task.task_id:
                context_switch = True
                self.n_context_switches += 1
                if self.machine.context_switch_ms > 0:
                    self._advance(self.now + self.machine.context_switch_ms, "overhead")
            if task.first_dispatch_ms is None:
                task.first_dispatch_ms = self.now
                self._n_never -= 1
            if not task.started:
                task.started = True
                self.resident_mb += task.memory_mb
            slowdown = self.slowdown()
            needed = task.remaining_burst_ms * slowdown
            finishes = decision.time_slice_ms is None or decision.time_slice_ms >= needed - _EPS
            wall = needed if finishes else float(decision.time_slice_ms)  # type: ignore[arg-type]
            self._advance(self.now + wall, "busy")
            self.last_task_id = task.task_id
            if finishes:
                progress = task.remaining_burst_ms
                task.remaining_burst_ms = 0.0
            else:
                progress = wall / slowdown
                task.remaining_burst_ms -= progress
            task.executed_ms += progress
            self.total_work_ms += progress
            if finishes:
                if task.burst_index + 1 < task.n_bursts:
                    io_wait = task.io_waits_ms[task.burst_index]
                    task.burst_index += 1
                    task.state = TaskState.BLOCKED
                    heapq.heappush(self._blocked, (self.now + io_wait, task.task_id))
                else:
                    task.state = TaskState.DONE
                    task.finish_ms = self.now
                    self.resident_mb -= task.memory_mb
                    if abs(self.resident_mb) < 1e-6:
                        self.resident_mb = 0.0
                    self._n_in_system -= 1
                    self._n_done += 1
                    completed.append(task.task_id)
            else:
                task.preemption_count += 1
                self.n_preemptions += 1
                self._enter_ready(task)
        else:
            raise ValueError(f"unknown decision kind {decision.kind!r}")

        # Admit anything due exactly now that the dispatch branch created after its last
        # event pass (e.g. an I/O wait of 0 ms): it must be visible at the next decision.
        self._admit_until(self.now)
        # Idle until some task is READY (or nothing is left).
        while not self._ready and (self._blocked or self._future_pos < len(self._future)):
            next_event = min(
                self._next_arrival_time(), self._blocked[0][0] if self._blocked else math.inf
            )
            self._advance(next_event, "idle")
        missed = self._process_deadlines()
        acc = self._acc
        self.total_busy_ms += acc.busy
        self.total_idle_ms += acc.idle
        self.total_overhead_ms += acc.overhead
        late = tuple(
            tid
            for tid in completed
            if self.tasks[tid].finish_ms is not None
            and self.tasks[tid].finish_ms > self.tasks[tid].deadline_ms  # type: ignore[operator]
        )
        return StepOutcome(
            decision=decision,
            start_ms=start,
            end_ms=self.now,
            duration_ms=self.now - start,
            wait_ms=acc.wait,
            in_system_ms=acc.in_system,
            response_wait_ms=acc.response,
            busy_ms=acc.busy,
            idle_ms=acc.idle,
            overhead_ms=acc.overhead,
            arrivals=acc.arrivals,
            completed=tuple(completed),
            late_completed=late,
            deadline_misses=tuple(missed),
            context_switch=context_switch,
            done=self.done,
        )

    def run(self, policy: Policy, max_decisions: int | None = None) -> list[StepOutcome]:
        """Drive the simulator with ``policy.decide(view)`` until done (or ``max_decisions``)."""
        outcomes: list[StepOutcome] = []
        while self.at_decision_point:
            if max_decisions is not None and len(outcomes) >= max_decisions:
                break
            outcomes.append(self.execute(policy.decide(self.view())))
        return outcomes


def total_cpu_demand(tasks: Sequence[Task]) -> float:
    """Sum of all CPU bursts of a workload."""
    return float(sum(task.total_cpu_ms for task in tasks))
