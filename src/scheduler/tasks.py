"""Tasks and the synthetic workload generator.

A task has a CPU time, a memory usage, a priority and an inter-arrival time, and belongs to
one task class. The benchmark config defines three classes (the execution patterns
CPU-bound, memory-bound and I/O-bound); a workload profile may define its own classes, for
example the inference requests and fine-tuning jobs of
``configs/scheduler_llm_workload.yaml``. Every distribution below is
``[Assumption — not in paper]`` and is parameterised entirely from the ``workload:`` block
of the config in use (``configs/scheduler_ddqn.yaml`` unless a profile is given).

Time unit: milliseconds (float). Memory unit: MB.
"""

from __future__ import annotations

import dataclasses
import enum
import math

import numpy as np

from src.common.seeding import rng_from_seed

from .config import WorkloadConfig, priority_weights_for, task_class_names


class TaskState(enum.Enum):
    """Life-cycle state of a task in the simulator."""

    FUTURE = "future"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE = "done"


@dataclasses.dataclass
class Task:
    """One task: static description plus the simulator's dynamic bookkeeping.

    The static fields describe the workload; the dynamic fields (everything after
    ``deadline_ms``) are owned and mutated by :class:`~src.scheduler.simulator.SchedulerSim`.
    Use :meth:`fresh` to get an unstarted copy, so one workload can be replayed by
    several schedulers.
    """

    task_id: int
    arrival_ms: float
    task_type: str
    cpu_bursts_ms: tuple[float, ...]
    io_waits_ms: tuple[float, ...]
    memory_mb: float
    priority: int
    deadline_ms: float
    # --- dynamic state (owned by the simulator) ---
    state: TaskState = TaskState.FUTURE
    burst_index: int = 0
    remaining_burst_ms: float = 0.0
    ready_since_ms: float | None = None
    ready_seq: int = -1
    first_dispatch_ms: float | None = None
    finish_ms: float | None = None
    total_wait_ms: float = 0.0
    longest_wait_ms: float = 0.0
    started: bool = False
    priority_adjust: int = 0
    dispatch_count: int = 0
    preemption_count: int = 0
    deadline_missed: bool = False
    executed_ms: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.task_type, str) or not self.task_type:
            raise ValueError(f"task_type must be a non-empty class name, got {self.task_type!r}")
        if len(self.cpu_bursts_ms) < 1:
            raise ValueError("a task needs at least one CPU burst")
        if len(self.io_waits_ms) != len(self.cpu_bursts_ms) - 1:
            raise ValueError("io_waits_ms must have one entry fewer than cpu_bursts_ms")
        if any(b <= 0 for b in self.cpu_bursts_ms):
            raise ValueError("CPU bursts must be positive")
        if any(w < 0 for w in self.io_waits_ms):
            raise ValueError("I/O waits must be non-negative")
        if self.state is TaskState.FUTURE and self.burst_index == 0:
            self.remaining_burst_ms = float(self.cpu_bursts_ms[0])

    @property
    def n_bursts(self) -> int:
        """Number of CPU bursts."""
        return len(self.cpu_bursts_ms)

    @property
    def total_cpu_ms(self) -> float:
        """Total CPU demand (sum of bursts), excluding any thrashing slowdown."""
        return float(sum(self.cpu_bursts_ms))

    @property
    def total_io_ms(self) -> float:
        """Total I/O wait."""
        return float(sum(self.io_waits_ms))

    @property
    def remaining_total_cpu_ms(self) -> float:
        """CPU work still to do: rest of the current burst plus all later bursts."""
        if self.state is TaskState.DONE:
            return 0.0
        later = sum(self.cpu_bursts_ms[self.burst_index + 1 :])
        return float(self.remaining_burst_ms + later)

    def fresh(self) -> Task:
        """An unstarted copy with the same static fields."""
        return Task(
            task_id=self.task_id,
            arrival_ms=self.arrival_ms,
            task_type=self.task_type,
            cpu_bursts_ms=tuple(self.cpu_bursts_ms),
            io_waits_ms=tuple(self.io_waits_ms),
            memory_mb=self.memory_mb,
            priority=self.priority,
            deadline_ms=self.deadline_ms,
        )

    def static_dict(self) -> dict[str, object]:
        """Static fields as a flat dict (bursts and waits joined with ``;``) for CSV export."""
        return {
            "task_id": self.task_id,
            "arrival_ms": self.arrival_ms,
            "task_type": self.task_type,
            "n_bursts": self.n_bursts,
            "cpu_bursts_ms": ";".join(f"{b:.3f}" for b in self.cpu_bursts_ms),
            "io_waits_ms": ";".join(f"{w:.3f}" for w in self.io_waits_ms),
            "total_cpu_ms": round(self.total_cpu_ms, 3),
            "total_io_ms": round(self.total_io_ms, 3),
            "memory_mb": self.memory_mb,
            "priority": self.priority,
            "deadline_ms": self.deadline_ms,
        }


WORKLOAD_CSV_FIELDS = (
    "task_id",
    "arrival_ms",
    "task_type",
    "n_bursts",
    "cpu_bursts_ms",
    "io_waits_ms",
    "total_cpu_ms",
    "total_io_ms",
    "memory_mb",
    "priority",
    "deadline_ms",
)
"""Column order of a workload CSV (see ``data/synthetic/generate_scheduler_workload.py``)."""


def _round(value: float) -> float:
    return float(round(float(value), 3))


def generate_workload(workload_cfg: WorkloadConfig, load_profile: str, seed: int) -> list[Task]:
    """Generate one deterministic workload.

    Task attributes come from the random stream ``(seed, "tasks")`` and inter-arrival times
    from ``(seed, "arrivals")``. Inter-arrival times are exponential with mean
    ``mean_cpu_demand_of_this_workload / rho`` where ``rho`` is the target CPU utilisation
    of ``load_profile``; the first task arrives at time 0. Each task's deadline is
    ``arrival + slo_factor * (total CPU + total I/O wait) + slo_slack_ms``.

    The task classes are the keys of ``workload.task_types`` in the order the config lists
    them. A task's priority level is drawn from ``workload.priority_level_weights``: one
    list for every class, or one list per class.
    """
    if load_profile not in workload_cfg.load_profiles:
        raise KeyError(f"unknown load profile {load_profile!r}")
    rho = float(workload_cfg.load_profiles[load_profile])
    rng = rng_from_seed(seed, "tasks")
    arrival_rng = rng_from_seed(seed, "arrivals")

    n_tasks = int(rng.integers(workload_cfg.n_tasks_min, workload_cfg.n_tasks_max + 1))
    classes = task_class_names(workload_cfg)
    type_weights = np.array([workload_cfg.task_types[t].weight for t in classes], dtype=float)
    type_weights = type_weights / type_weights.sum()
    prio_weights_by_class: dict[str, np.ndarray] = {}
    for name in classes:
        weights = np.asarray(priority_weights_for(workload_cfg, name), dtype=float)
        prio_weights_by_class[name] = weights / weights.sum()

    drafts: list[dict[str, object]] = []
    for _ in range(n_tasks):
        task_type = classes[int(rng.choice(len(classes), p=type_weights))]
        tcfg = workload_cfg.task_types[task_type]
        prio_weights = prio_weights_by_class[task_type]
        demand = float(rng.lognormal(mean=math.log(tcfg.cpu_median_ms), sigma=tcfg.cpu_sigma))
        demand = min(max(demand, tcfg.cpu_min_ms), tcfg.cpu_max_ms)
        n_io = int(rng.integers(tcfg.io_ops_min, tcfg.io_ops_max + 1))
        shares = rng.uniform(0.5, 1.5, size=n_io + 1)
        bursts = np.maximum(demand * shares / shares.sum(), workload_cfg.min_burst_ms)
        waits = rng.uniform(tcfg.io_wait_min_ms, tcfg.io_wait_max_ms, size=n_io)
        memory = float(rng.uniform(tcfg.memory_min_mb, tcfg.memory_max_mb))
        priority = int(rng.choice(len(prio_weights), p=prio_weights))
        drafts.append(
            {
                "task_type": task_type,
                "bursts": tuple(_round(b) for b in bursts),
                "waits": tuple(_round(w) for w in waits),
                "memory": _round(memory),
                "priority": priority,
                "slo_factor": tcfg.slo_factor,
            }
        )

    mean_cpu = float(np.mean([sum(d["bursts"]) for d in drafts]))  # type: ignore[arg-type]
    gaps = arrival_rng.exponential(mean_cpu / rho, size=max(n_tasks - 1, 0))
    arrivals = np.concatenate([[0.0], np.cumsum(gaps)])

    tasks: list[Task] = []
    for task_id, (draft, arrival) in enumerate(zip(drafts, arrivals, strict=True)):
        bursts = draft["bursts"]
        waits = draft["waits"]
        arrival_ms = _round(arrival)
        budget = float(draft["slo_factor"]) * (sum(bursts) + sum(waits))  # type: ignore[arg-type]
        tasks.append(
            Task(
                task_id=task_id,
                arrival_ms=arrival_ms,
                task_type=str(draft["task_type"]),
                cpu_bursts_ms=bursts,  # type: ignore[arg-type]
                io_waits_ms=waits,  # type: ignore[arg-type]
                memory_mb=float(draft["memory"]),  # type: ignore[arg-type]
                priority=int(draft["priority"]),  # type: ignore[arg-type]
                deadline_ms=_round(arrival_ms + budget + workload_cfg.slo_slack_ms),
            )
        )
    return tasks


def workload_rows(tasks: list[Task]) -> list[dict[str, object]]:
    """Rows for a workload CSV (column order :data:`WORKLOAD_CSV_FIELDS`)."""
    return [task.static_dict() for task in tasks]
