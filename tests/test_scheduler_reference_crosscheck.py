"""Cross-check of the simulator against an independent textbook reference.

The reference below is a deliberately separate, 40-line implementation of FCFS, SJF,
Round Robin, Priority and the preemptive SRTF reference for the simplest setting (one CPU burst per task, no I/O, no memory
pressure, no context-switch cost). It shares no code with ``src.scheduler``. On hundreds of
random integer workloads the simulator must produce exactly the same finish time and first
dispatch time for every task. A disagreement means one of the two is wrong.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.scheduler.baselines import FCFS, SJF, SRTF, PriorityPolicy, RoundRobin
from src.scheduler.config import MachineConfig
from src.scheduler.metrics import episode_metrics
from src.scheduler.simulator import SchedulerSim
from src.scheduler.tasks import Task

Spec = tuple[int, int, int, int]  # task_id, arrival, burst, priority


def reference_schedule(specs: list[Spec], policy: str, quantum: int | None = None):
    """Textbook single-CPU schedule. Returns ``{task_id: (finish, first_start)}``.

    Conventions (the ones the simulator documents): the ready queue is FIFO in order of
    entry; tasks that arrive at the same instant enter in ``task_id`` order; a task that
    arrives while a slice is running, or exactly when it ends, enters before the preempted
    task; ties in SJF and Priority go to the task that entered the queue first.
    """
    pending = sorted(specs, key=lambda spec: (spec[1], spec[0]))
    remaining = {task_id: burst for task_id, _, burst, _ in specs}
    priority = {task_id: prio for task_id, _, _, prio in specs}
    queue: list[int] = []
    result: dict[int, list[int]] = {}
    time = pending[0][1]

    def admit(now: int) -> None:
        while pending and pending[0][1] <= now:
            queue.append(pending.pop(0)[0])

    while pending or queue:
        admit(time)
        if not queue:
            time = pending[0][1]
            continue
        if policy in ("fcfs", "round_robin"):
            chosen = queue[0]
        elif policy in ("sjf", "srtf"):
            chosen = min(queue, key=lambda task_id: (remaining[task_id], queue.index(task_id)))
        elif policy == "priority":
            chosen = min(queue, key=lambda task_id: (-priority[task_id], queue.index(task_id)))
        else:
            raise ValueError(policy)
        sliced = policy in ("round_robin", "srtf")
        run = min(quantum, remaining[chosen]) if sliced else remaining[chosen]
        result.setdefault(chosen, [0, time])
        queue.remove(chosen)
        time += run
        remaining[chosen] -= run
        admit(time)
        if remaining[chosen] > 0:
            queue.append(chosen)
        else:
            result[chosen][0] = time
    return {task_id: (finish, first) for task_id, (finish, first) in result.items()}


def _machine() -> MachineConfig:
    return MachineConfig(
        memory_capacity_mb=1_000_000.0,
        thrash_penalty=1.0,
        context_switch_ms=0.0,
        priority_adjust_overhead_ms=0.0,
        num_priority_levels=5,
    )


def _tasks(specs: list[Spec]) -> list[Task]:
    return [
        Task(
            task_id=task_id,
            arrival_ms=float(arrival),
            task_type="cpu_bound",
            cpu_bursts_ms=(float(burst),),
            io_waits_ms=(),
            memory_mb=1.0,
            priority=prio,
            deadline_ms=1.0e9,
        )
        for task_id, arrival, burst, prio in specs
    ]


def _random_specs(rng: np.random.Generator) -> list[Spec]:
    count = int(rng.integers(2, 13))
    arrivals = np.sort(rng.integers(0, 30, size=count))
    return [
        (index + 1, int(arrivals[index]), int(rng.integers(1, 12)), int(rng.integers(0, 5)))
        for index in range(count)
    ]


@pytest.mark.parametrize("policy", ["fcfs", "sjf", "round_robin", "priority", "srtf"])
def test_simulator_matches_independent_reference_on_random_workloads(policy: str) -> None:
    rng = np.random.default_rng(20251119)
    for case in range(300):
        specs = _random_specs(rng)
        quantum = int(rng.integers(1, 7))
        expected = reference_schedule(specs, policy, quantum)
        simulated_policy = {
            "fcfs": FCFS(),
            "sjf": SJF(),
            "round_robin": RoundRobin(float(quantum)),
            "priority": PriorityPolicy(None),
            "srtf": SRTF(float(quantum)),
        }[policy]
        sim = SchedulerSim(_tasks(specs), _machine())
        sim.run(simulated_policy)
        assert sim.done
        for task_id, (finish, first_start) in expected.items():
            task = sim.tasks[task_id]
            context = f"{policy} case {case} quantum {quantum} specs {specs} task {task_id}"
            assert task.finish_ms == pytest.approx(float(finish), abs=1e-9), context
            assert task.first_dispatch_ms == pytest.approx(float(first_start), abs=1e-9), context
        metrics = episode_metrics(sim, starvation_threshold_ms=1.0e9)
        turnaround = np.mean([expected[t][0] - arrival for t, arrival, _, _ in specs])
        response = np.mean([expected[t][1] - arrival for t, arrival, _, _ in specs])
        waiting = np.mean([expected[t][0] - arrival - burst for t, arrival, burst, _ in specs])
        assert metrics["avg_turnaround_ms"] == pytest.approx(turnaround, abs=1e-9)
        assert metrics["avg_response_ms"] == pytest.approx(response, abs=1e-9)
        assert metrics["avg_waiting_ms"] == pytest.approx(waiting, abs=1e-9)


def test_sjf_never_has_worse_mean_turnaround_than_fcfs_when_all_tasks_arrive_together() -> None:
    """Textbook fact used in the topic guide: with simultaneous arrivals SJF is optimal."""
    rng = np.random.default_rng(7)
    for _ in range(100):
        count = int(rng.integers(2, 10))
        specs = [(i + 1, 0, int(rng.integers(1, 20)), 0) for i in range(count)]
        means = {}
        for name, policy in (("fcfs", FCFS()), ("sjf", SJF())):
            sim = SchedulerSim(_tasks(specs), _machine())
            sim.run(policy)
            means[name] = episode_metrics(sim, starvation_threshold_ms=1.0e9)["avg_turnaround_ms"]
        assert means["sjf"] <= means["fcfs"] + 1e-9
