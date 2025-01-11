"""Full cross-check of the simulator against a second, independent reference simulator.

``test_scheduler_reference_crosscheck.py`` covers the textbook setting (one burst, no I/O).
This file covers everything else the machine model does: I/O blocking, the soft memory
constraint with thrashing, context-switch cost, priority-adjust overhead, preemption with
arbitrary time slices, and the per-step accrual integrals that the reward is built from.

The reference below was written during an independent code review. It shares no code with
``src.scheduler.simulator``: it keeps its own task table, its own event loop and its own
ready-queue order, and it records the intervals each task spent in the ready queue so that
waiting, response and in-system time can be integrated independently per step.

Both simulators are driven by the *same sequence of decisions* (from FCFS, SJF, Round Robin,
Priority, the SRTF reference and a random policy that also issues priority changes) on
generated workloads at light, medium and heavy load and on three machine configurations.
After every step and at the end of every episode they must agree on time, ready-queue order,
resident memory, per-task finish / first-dispatch / waiting times, the accrual integrals,
deadline misses, context switches and the episode metrics. Development seeds (>= 100) only.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.scheduler.baselines import FCFS, SJF, SRTF, PriorityPolicy, RoundRobin
from src.scheduler.config import MachineConfig, load_scheduler_config
from src.scheduler.metrics import episode_metrics
from src.scheduler.simulator import Decision, SchedulerSim
from src.scheduler.tasks import generate_workload

TOLERANCE = 1e-6


class ReferenceSimulator:
    """Independent single-CPU reference with I/O, thrashing and overheads."""

    def __init__(self, tasks, machine: MachineConfig) -> None:
        self.machine = machine
        self.table = {
            task.task_id: {
                "arrival": task.arrival_ms,
                "bursts": list(task.cpu_bursts_ms),
                "io_waits": list(task.io_waits_ms),
                "memory": task.memory_mb,
                "priority": task.priority,
                "deadline": task.deadline_ms,
                "adjust": 0,
                "burst_index": 0,
                "remaining": task.cpu_bursts_ms[0],
                "state": "future",
                "ready_since": None,
                "first_dispatch": None,
                "finish": None,
                "started": False,
                "returns_at": None,
                "ready_intervals": [],
                "sequence": None,
            }
            for task in tasks
        }
        self.now = min(task.arrival_ms for task in tasks)
        self.sequence = 0
        self.ready: list[int] = []
        self.last_dispatched: int | None = None
        self.resident = 0.0
        self.work = 0.0
        self.busy = 0.0
        self.idle = 0.0
        self.overhead = 0.0
        self._admit(self.now)

    def _enter_ready(self, task_id: int) -> None:
        record = self.table[task_id]
        record["state"] = "ready"
        record["ready_since"] = self.now
        record["sequence"] = self.sequence
        self.sequence += 1
        self.ready.append(task_id)

    def _admit(self, at: float) -> None:
        """Arrivals first (by id), then I/O returns (by id), all with timestamps <= ``at``."""
        arrivals = [
            i for i, r in self.table.items() if r["state"] == "future" and r["arrival"] <= at
        ]
        for task_id in sorted(arrivals):
            self._enter_ready(task_id)
        returns = [
            i for i, r in self.table.items() if r["state"] == "blocked" and r["returns_at"] <= at
        ]
        for task_id in sorted(returns):
            record = self.table[task_id]
            record["remaining"] = record["bursts"][record["burst_index"]]
            self._enter_ready(task_id)

    def _next_event(self) -> float:
        times = [r["arrival"] for r in self.table.values() if r["state"] == "future"]
        times += [r["returns_at"] for r in self.table.values() if r["state"] == "blocked"]
        return min(times) if times else math.inf

    def _advance(self, until: float) -> None:
        while True:
            event = self._next_event()
            if event > until:
                break
            self.now = max(self.now, event)
            self._admit(event)
        self.now = until

    def execute(self, decision: Decision) -> tuple[float, float]:
        """Apply one decision; return the (start, end) time of the step."""
        start = self.now
        record = self.table[decision.task_id]
        assert record["state"] == "ready"
        machine = self.machine
        if decision.kind == "priority":
            low, high = -record["priority"], machine.num_priority_levels - 1 - record["priority"]
            record["adjust"] = max(low, min(high, record["adjust"] + decision.delta))
            self._advance(self.now + machine.priority_adjust_overhead_ms)
            self.overhead += machine.priority_adjust_overhead_ms
        else:
            record["ready_intervals"].append((record["ready_since"], self.now))
            record["ready_since"] = None
            self.ready.remove(decision.task_id)
            record["state"] = "running"
            switching = (
                self.last_dispatched is not None and self.last_dispatched != decision.task_id
            )
            if switching and machine.context_switch_ms > 0:
                self._advance(self.now + machine.context_switch_ms)
                self.overhead += machine.context_switch_ms
            if record["first_dispatch"] is None:
                record["first_dispatch"] = self.now
            if not record["started"]:
                record["started"] = True
                self.resident += record["memory"]
            overcommit = max(0.0, self.resident / machine.memory_capacity_mb - 1.0)
            slowdown = 1.0 + machine.thrash_penalty * overcommit
            needed = record["remaining"] * slowdown
            if decision.time_slice_ms is None or decision.time_slice_ms >= needed - 1e-9:
                wall, progress, burst_done = needed, record["remaining"], True
            else:
                wall, progress, burst_done = (
                    decision.time_slice_ms,
                    decision.time_slice_ms / slowdown,
                    False,
                )
            self._advance(self.now + wall)
            self.busy += wall
            self.last_dispatched = decision.task_id
            record["remaining"] -= progress
            self.work += progress
            if not burst_done:
                self._enter_ready(decision.task_id)
            elif record["burst_index"] + 1 < len(record["bursts"]):
                record["returns_at"] = self.now + record["io_waits"][record["burst_index"]]
                record["burst_index"] += 1
                record["state"] = "blocked"
            else:
                record["state"] = "done"
                record["finish"] = self.now
                self.resident -= record["memory"]
        self._admit(self.now)
        while not self.ready and self._next_event() < math.inf:
            event = self._next_event()
            self.idle += event - self.now
            self._advance(event)
        return start, self.now


class RandomPolicy:
    """Random valid decisions: any ready task, any of four slices, 25% priority changes."""

    def __init__(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def reset(self) -> None:
        """Nothing to reset."""

    def decide(self, view) -> Decision:
        chosen = view.ready[int(self.rng.integers(len(view.ready)))]
        if self.rng.random() < 0.25:
            return Decision.adjust_priority(chosen.task_id, int(self.rng.choice([1, -1])))
        slices = [None, 10.0, 40.0, 3.3]
        return Decision.dispatch(chosen.task_id, slices[int(self.rng.integers(len(slices)))])


def _overlap(a: float, b: float, start: float, end: float) -> float:
    return max(0.0, min(b, end) - max(a, start))


def _replay_and_compare(
    tasks, machine: MachineConfig, policy, starvation_threshold_ms: float
) -> int:
    """Drive both simulators with ``policy``; assert agreement; return the number of steps."""
    sim = SchedulerSim(tasks, machine)
    reference = ReferenceSimulator(tasks, machine)
    outcomes = []
    previous_end = sim.now
    while sim.at_decision_point:
        decision = policy.decide(sim.view())
        expected_order = sorted(reference.ready, key=lambda i: reference.table[i]["sequence"])
        assert list(sim.ready_ids) == expected_order, "ready queue membership or FIFO order differs"
        outcome = sim.execute(decision)
        start, end = reference.execute(decision)
        assert outcome.start_ms == pytest.approx(start, abs=TOLERANCE)
        assert outcome.end_ms == pytest.approx(end, abs=TOLERANCE)
        assert outcome.end_ms >= previous_end - 1e-12, "time went backwards"
        previous_end = outcome.end_ms
        assert sim.resident_mb >= -TOLERANCE
        assert sim.resident_mb == pytest.approx(reference.resident, abs=TOLERANCE)
        outcomes.append(outcome)

    records = reference.table
    assert not reference.ready and all(r["state"] == "done" for r in records.values())
    for task_id, record in records.items():
        task = sim.tasks[task_id]
        waits = [b - a for a, b in record["ready_intervals"]]
        assert task.finish_ms == pytest.approx(record["finish"], abs=TOLERANCE)
        assert task.first_dispatch_ms == pytest.approx(record["first_dispatch"], abs=TOLERANCE)
        assert task.total_wait_ms == pytest.approx(sum(waits), abs=TOLERANCE)
        assert task.longest_wait_ms == pytest.approx(max(waits, default=0.0), abs=TOLERANCE)

    last_dispatched = None
    switches = 0
    for outcome in outcomes:
        window = (outcome.start_ms, outcome.end_ms)
        in_system = sum(_overlap(r["arrival"], r["finish"], *window) for r in records.values())
        response = sum(
            _overlap(r["arrival"], r["first_dispatch"], *window) for r in records.values()
        )
        waiting = sum(
            _overlap(a, b, *window) for r in records.values() for a, b in r["ready_intervals"]
        )
        assert outcome.in_system_ms == pytest.approx(in_system, abs=1e-5)
        assert outcome.response_wait_ms == pytest.approx(response, abs=1e-5)
        assert outcome.wait_ms == pytest.approx(waiting, abs=1e-5)
        parts = outcome.busy_ms + outcome.idle_ms + outcome.overhead_ms
        assert parts == pytest.approx(outcome.duration_ms, abs=TOLERANCE)
        late_in_step = sorted(
            i
            for i, r in records.items()
            if r["finish"] > r["deadline"] and outcome.start_ms < r["deadline"] <= outcome.end_ms
        )
        assert sorted(outcome.deadline_misses) == late_in_step
        if outcome.decision.is_dispatch:
            switched = last_dispatched is not None and last_dispatched != outcome.decision.task_id
            assert outcome.context_switch == switched
            switches += switched
            last_dispatched = outcome.decision.task_id
        else:
            assert not outcome.context_switch
    assert switches == sim.n_context_switches

    metrics = episode_metrics(sim, starvation_threshold_ms)
    count = len(records)
    turnarounds = [r["finish"] - r["arrival"] for r in records.values()]
    responses = [r["first_dispatch"] - r["arrival"] for r in records.values()]
    makespan = max(r["finish"] for r in records.values()) - min(
        r["arrival"] for r in records.values()
    )
    assert sum(o.in_system_ms for o in outcomes) == pytest.approx(sum(turnarounds), abs=1e-4)
    assert metrics["avg_turnaround_ms"] == pytest.approx(np.mean(turnarounds), abs=TOLERANCE)
    assert metrics["avg_response_ms"] == pytest.approx(np.mean(responses), abs=TOLERANCE)
    assert sum(o.response_wait_ms for o in outcomes) / count == pytest.approx(
        metrics["avg_response_ms"], abs=TOLERANCE
    )
    assert sum(o.wait_ms for o in outcomes) / count == pytest.approx(
        metrics["avg_waiting_ms"], abs=TOLERANCE
    )
    assert metrics["makespan_ms"] == pytest.approx(makespan, abs=TOLERANCE)
    total = sim.total_busy_ms + sim.total_idle_ms + sim.total_overhead_ms
    assert total == pytest.approx(makespan, abs=TOLERANCE)
    assert metrics["cpu_utilisation"] == pytest.approx(reference.busy / makespan, abs=1e-9)
    all_work = sum(sum(r["bursts"]) for r in records.values())
    assert sim.total_work_ms == pytest.approx(all_work, abs=TOLERANCE)
    misses = sum(len(o.deadline_misses) for o in outcomes)
    late = sum(len(o.late_completed) for o in outcomes)
    assert misses == late == round(metrics["slo_violation_rate"] * count)
    assert sim.resident_mb == 0.0
    return len(outcomes)


@pytest.mark.slow
@pytest.mark.parametrize("load", ["light", "medium", "heavy"])
def test_simulator_matches_full_reference(configs_dir: Path, load: str) -> None:
    config = load_scheduler_config(configs_dir / "scheduler_ddqn.yaml")
    machines = [
        config.machine,
        MachineConfig(
            memory_capacity_mb=2500.0,
            thrash_penalty=2.0,
            context_switch_ms=1.7,
            priority_adjust_overhead_ms=0.3,
            num_priority_levels=4,
        ),
        MachineConfig(
            memory_capacity_mb=4096.0,
            thrash_penalty=1.0,
            context_switch_ms=0.0,
            priority_adjust_overhead_ms=0.0,
            num_priority_levels=4,
        ),
    ]
    episodes = 0
    steps = 0
    for seed in range(100, 106):
        tasks = generate_workload(config.workload, load, seed)
        for index, machine in enumerate(machines):
            policies = [
                FCFS(),
                SJF(),
                RoundRobin(20.0),
                PriorityPolicy(None),
                SRTF(10.0),
                RandomPolicy(seed * 7 + index),
            ]
            for policy in policies:
                fresh = generate_workload(config.workload, load, seed)
                steps += _replay_and_compare(
                    fresh, machine, policy, config.metrics.starvation_threshold_ms
                )
                episodes += 1
        assert tasks, "workload generator returned no tasks"
    assert episodes == 6 * 3 * 6
    assert steps > 1000
