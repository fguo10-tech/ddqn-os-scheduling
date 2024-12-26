"""Simulator semantics: invariants, thrashing, context switches, event order, workloads."""

from __future__ import annotations

import numpy as np
import pytest

from src.scheduler.baselines import FCFS, SJF, PriorityPolicy, RoundRobin
from src.scheduler.config import MachineConfig, load_scheduler_config
from src.scheduler.metrics import episode_metrics
from src.scheduler.simulator import Decision, SchedulerSim, aging_boost
from src.scheduler.tasks import Task, TaskState, generate_workload

DEV_SEEDS = (100, 101, 102, 103, 104)


def machine(cs: float = 0.0, capacity: float = 1e6, penalty: float = 1.0, overhead: float = 0.0):
    return MachineConfig(
        memory_capacity_mb=capacity,
        thrash_penalty=penalty,
        context_switch_ms=cs,
        priority_adjust_overhead_ms=overhead,
        num_priority_levels=4,
    )


def one(task_id, arrival, bursts, waits=(), mem=1.0, prio=0, deadline=1e6):
    return Task(task_id, float(arrival), "cpu_bound", tuple(map(float, bursts)),
                tuple(map(float, waits)), float(mem), prio, float(deadline))  # fmt: skip


@pytest.fixture(scope="module")
def cfg(configs_dir):
    return load_scheduler_config(configs_dir / "scheduler_ddqn.yaml")


class RandomPolicy:
    """Random dispatches with random slices, plus random priority changes."""

    name = "random"

    def __init__(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def reset(self) -> None:
        pass

    def decide(self, view):
        task = view.ready[int(self.rng.integers(len(view.ready)))]
        if self.rng.random() < 0.2:
            return Decision.adjust_priority(task.task_id, int(self.rng.choice([1, -1])))
        slices = [None, 3.0, 17.0]
        return Decision.dispatch(task.task_id, slices[int(self.rng.integers(3))])


@pytest.mark.parametrize("seed", DEV_SEEDS)
def test_invariants_on_generated_workloads(cfg, seed) -> None:
    policies = [FCFS(), SJF(), RoundRobin(20.0), PriorityPolicy(None), RandomPolicy(seed)]
    for load in ("light", "heavy"):
        tasks = generate_workload(cfg.workload, load, seed)
        for policy in policies:
            sim = SchedulerSim(tasks, cfg.machine)
            outcomes = sim.run(policy)
            assert sim.done
            # total executed CPU work equals the sum of all bursts
            assert sim.total_work_ms == pytest.approx(sum(t.total_cpu_ms for t in tasks))
            for task in sim.tasks.values():
                assert task.state is TaskState.DONE and task.finish_ms is not None
                assert task.first_dispatch_ms >= task.arrival_ms  # never runs before arrival
                assert task.executed_ms == pytest.approx(task.total_cpu_ms)
            assert sim.resident_mb == 0.0
            # time never goes backwards; steps tile the timeline
            for prev, nxt in zip(outcomes, outcomes[1:], strict=False):
                assert nxt.start_ms == pytest.approx(prev.end_ms)
            assert all(o.end_ms >= o.start_ms for o in outcomes)
            # every task finishes exactly once
            completed = [tid for o in outcomes for tid in o.completed]
            assert sorted(completed) == sorted(sim.tasks)
            # busy + idle + overhead covers the timeline
            total = sim.total_busy_ms + sim.total_idle_ms + sim.total_overhead_ms
            assert total == pytest.approx(sim.now - sim.first_arrival_ms)


def test_thrashing_slowdown_arithmetic() -> None:
    # One task needing 150 MB of a 100 MB machine: slowdown = 1 + 2 * (1.5 - 1) = 2.
    sim = SchedulerSim([one(0, 0, [10], mem=150)], machine(capacity=100, penalty=2.0))
    assert sim.slowdown() == 1.0
    out = sim.execute(Decision.dispatch(0, None))
    assert sim.tasks[0].finish_ms == pytest.approx(20.0)
    assert out.busy_ms == pytest.approx(20.0)
    assert sim.total_work_ms == pytest.approx(10.0)


def test_thrashing_from_two_started_tasks() -> None:
    tasks = [one(0, 0, [10], mem=60), one(1, 0, [10], mem=60)]
    sim = SchedulerSim(tasks, machine(capacity=100, penalty=2.0))
    sim.execute(Decision.dispatch(0, 5.0))  # resident 60: no slowdown, progress 5
    assert sim.tasks[0].remaining_burst_ms == pytest.approx(5.0)
    sim.execute(Decision.dispatch(1, 5.0))  # resident 120: slowdown 1.4
    assert sim.slowdown() == pytest.approx(1.4)
    assert sim.tasks[1].remaining_burst_ms == pytest.approx(10.0 - 5.0 / 1.4)
    sim.run(FCFS())
    assert sim.total_work_ms == pytest.approx(20.0)
    assert sim.resident_mb == 0.0


def test_context_switch_accounting() -> None:
    spec = [(1, 0, 8), (2, 1, 4), (3, 2, 9), (4, 3, 5)]
    sim = SchedulerSim([one(i, a, [b]) for i, a, b in spec], machine(cs=1.0))
    sim.run(FCFS())
    # P1 0-8 (cold CPU, not charged); P2 switch 8-9 run 9-13; P3 13-14, 14-23; P4 23-24, 24-29
    assert [sim.tasks[i].finish_ms for i in (1, 2, 3, 4)] == [8.0, 13.0, 23.0, 29.0]
    assert sim.n_context_switches == 3
    assert sim.total_overhead_ms == pytest.approx(3.0)
    assert sim.total_busy_ms == pytest.approx(26.0)
    assert [sim.tasks[i].first_dispatch_ms for i in (2, 3, 4)] == [9.0, 14.0, 24.0]


def test_same_task_redispatch_costs_no_switch() -> None:
    sim = SchedulerSim([one(0, 0, [10])], machine(cs=1.0))
    sim.run(RoundRobin(4.0))
    assert sim.tasks[0].finish_ms == 10.0
    assert sim.n_context_switches == 0


def test_event_order_at_equal_timestamps() -> None:
    # A runs 0-2, blocks until 6; B runs 2-6 (quantum 4) and is preempted at 6, the instant
    # C arrives and A returns. Order must be: arrival C, then I/O return A, then preempted B.
    tasks = [one(0, 0, [2, 5], [4]), one(1, 0, [10]), one(2, 6, [1])]
    sim = SchedulerSim(tasks, machine())
    sim.execute(Decision.dispatch(0, 4.0))
    sim.execute(Decision.dispatch(1, 4.0))
    assert sim.now == 6.0
    assert sim.ready_ids == (2, 0, 1)
    seqs = [sim.tasks[i].ready_seq for i in (2, 0, 1)]
    assert seqs == sorted(seqs)


def test_priority_adjustment_clamps_and_costs_time() -> None:
    sim = SchedulerSim([one(0, 0, [5], prio=3), one(1, 0, [5])], machine(overhead=0.5))
    out = sim.execute(Decision.adjust_priority(0, +1))  # already at the top: clamped
    assert sim.tasks[0].priority_adjust == 0
    assert out.duration_ms == pytest.approx(0.5) and out.busy_ms == 0.0
    sim.execute(Decision.adjust_priority(0, -1))
    assert sim.tasks[0].priority_adjust == -1
    assert sim.total_work_ms == 0.0 and sim.n_priority_adjusts == 2


def test_aging_boost_is_pure() -> None:
    assert aging_boost(0.0, 100.0, 3) == 0
    assert aging_boost(250.0, 100.0, 3) == 2
    assert aging_boost(10_000.0, 100.0, 3) == 3


def test_accrual_matches_metrics(cfg) -> None:
    tasks = generate_workload(cfg.workload, "medium", 100)
    sim = SchedulerSim(tasks, cfg.machine)
    outcomes = sim.run(SJF())
    m = episode_metrics(sim, cfg.metrics.starvation_threshold_ms)
    # summed in-system time over steps == sum of turnaround times
    assert sum(o.in_system_ms for o in outcomes) == pytest.approx(
        m["avg_turnaround_ms"] * len(tasks)
    )
    assert sum(o.wait_ms for o in outcomes) == pytest.approx(m["avg_waiting_ms"] * len(tasks))
    assert sum(o.response_wait_ms for o in outcomes) == pytest.approx(
        m["avg_response_ms"] * len(tasks)
    )
    assert sum(len(o.deadline_misses) for o in outcomes) == pytest.approx(
        m["slo_violation_rate"] * len(tasks)
    )


def test_truncated_metrics_charge_unfinished_tasks(cfg) -> None:
    tasks = generate_workload(cfg.workload, "heavy", 101)
    sim = SchedulerSim(tasks, cfg.machine)
    sim.run(FCFS(), max_decisions=10)
    m = episode_metrics(sim, cfg.metrics.starvation_threshold_ms)
    assert m["truncated"] is True and m["n_completed"] < m["n_tasks"]
    expected = np.mean(
        [
            (t.finish_ms if t.finish_ms is not None else max(sim.now, t.arrival_ms)) - t.arrival_ms
            for t in sim.tasks.values()
        ]
    )
    assert m["avg_turnaround_ms"] == pytest.approx(expected)


def test_workload_determinism_and_constraints(cfg) -> None:
    a = generate_workload(cfg.workload, "medium", 123)
    b = generate_workload(cfg.workload, "medium", 123)
    c = generate_workload(cfg.workload, "medium", 124)
    assert [t.static_dict() for t in a] == [t.static_dict() for t in b]
    assert [t.static_dict() for t in a] != [t.static_dict() for t in c]
    assert cfg.workload.n_tasks_min <= len(a) <= cfg.workload.n_tasks_max
    for task in a:
        assert task.memory_mb <= cfg.machine.memory_capacity_mb
        assert task.deadline_ms > task.arrival_ms
        assert len(task.io_waits_ms) == task.n_bursts - 1
    io = [t for t in a if t.task_type == "io_bound"]
    assert io and all(3 <= t.n_bursts <= 8 for t in io)


def test_heavy_load_has_higher_utilisation_than_light(cfg) -> None:
    util = {}
    for load in ("light", "medium", "heavy"):
        values = []
        for seed in DEV_SEEDS:
            sim = SchedulerSim(generate_workload(cfg.workload, load, seed), cfg.machine)
            sim.run(FCFS())
            values.append(episode_metrics(sim, 1e9)["cpu_utilisation"])
        util[load] = float(np.mean(values))
    assert util["light"] < util["medium"] < util["heavy"]


def test_zero_length_io_wait_is_visible_at_next_decision() -> None:
    """A bursts [2, 1] with I/O wait [0], B burst [5], both at 0, SJF.

    A 0-2 then returns from a 0 ms I/O at t=2 with a 1 ms burst, shorter than B's 5:
    A 2-3 (finish 3), B 3-8 (finish 8).
    """
    tasks = [one(0, 0, [2, 1], [0]), one(1, 0, [5])]
    sim = SchedulerSim(tasks, machine())
    sim.run(SJF())
    assert sim.tasks[0].finish_ms == 3.0
    assert sim.tasks[1].finish_ms == 8.0
