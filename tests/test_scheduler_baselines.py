"""Hand-computed textbook cases for the four baselines (context switch 0, tiny memory).

Every expected number below was re-derived by hand:

Tasks (arrival, burst, priority): P1 (0, 8, 2), P2 (1, 4, 1), P3 (2, 9, 3), P4 (3, 5, 4).

* FCFS: P1 0-8, P2 8-12, P3 12-21, P4 21-26. Turnarounds 8, 11, 19, 23 (mean 15.25);
  waits 0, 7, 10, 18 (mean 8.75); response = wait (non-preemptive).
* SJF: at t=8 the queue is P2(4), P3(9), P4(5): P2 8-12, P4 12-17, P3 17-26.
  Turnarounds 8, 11, 24, 14 (14.25); waits 0, 7, 15, 9 (7.75).
* RR q=4: P1 0-4 (P2, P3, P4 arrive during it and queue before the preempted P1),
  P2 4-8 done, P3 8-12, P4 12-16, P1 16-20 done, P3 20-24, P4 24-25 done, P3 25-26 done.
  Finish 20, 8, 26, 25; turnarounds 20, 7, 24, 22 (18.25); waits 12, 3, 15, 17 (11.75);
  first dispatch 0, 4, 8, 12 -> response 0, 3, 6, 9 (4.5).
* Priority: P1 0-8; then P4(4) 8-13, P3(3) 13-22, P2(1) 22-26. Turnarounds 8, 25, 20, 10
  (15.75); waits 0, 21, 11, 5 (9.25).

I/O + idle case under FCFS: A (0, bursts [3, 2], I/O [4]), B (1, [5]), C (20, [2]).
A 0-3 then blocked until 7; B 3-8; A 8-10 (it waited 7-8); idle 10-20; C 20-22.
Turnarounds A 10, B 7, C 2; waits A 1, B 2, C 0; busy 12 of makespan 22.
"""

from __future__ import annotations

import pytest

from src.scheduler.baselines import FCFS, SJF, SRTF, PriorityPolicy, RoundRobin, make_policy
from src.scheduler.config import MachineConfig, load_baselines_config, load_scheduler_config
from src.scheduler.metrics import episode_metrics
from src.scheduler.simulator import SchedulerSim
from src.scheduler.tasks import Task


def machine(context_switch_ms: float = 0.0, levels: int = 5) -> MachineConfig:
    return MachineConfig(
        memory_capacity_mb=1_000_000.0,
        thrash_penalty=1.0,
        context_switch_ms=context_switch_ms,
        priority_adjust_overhead_ms=0.0,
        num_priority_levels=levels,
    )


def classic_tasks() -> list[Task]:
    spec = [(1, 0, 8, 2), (2, 1, 4, 1), (3, 2, 9, 3), (4, 3, 5, 4)]
    return [
        Task(
            task_id=tid,
            arrival_ms=float(arr),
            task_type="cpu_bound",
            cpu_bursts_ms=(float(burst),),
            io_waits_ms=(),
            memory_mb=1.0,
            priority=prio,
            deadline_ms=1000.0,
        )
        for tid, arr, burst, prio in spec
    ]


CASES = [
    (FCFS(), [8, 12, 21, 26], 15.25, 8.75, 8.75),
    (SJF(), [8, 12, 26, 17], 14.25, 7.75, 7.75),
    (RoundRobin(4.0), [20, 8, 26, 25], 18.25, 11.75, 4.5),
    (PriorityPolicy(None), [8, 26, 22, 13], 15.75, 9.25, 9.25),
]


@pytest.mark.parametrize(("policy", "finish", "tat", "wait", "resp"), CASES, ids=lambda c: "")
def test_hand_computed_baselines(policy, finish, tat, wait, resp) -> None:
    sim = SchedulerSim(classic_tasks(), machine())
    sim.run(policy)
    assert sim.done
    assert [sim.tasks[i].finish_ms for i in (1, 2, 3, 4)] == [float(f) for f in finish]
    m = episode_metrics(sim, starvation_threshold_ms=1000.0)
    assert m["avg_turnaround_ms"] == pytest.approx(tat, abs=1e-12)
    assert m["avg_waiting_ms"] == pytest.approx(wait, abs=1e-12)
    assert m["avg_response_ms"] == pytest.approx(resp, abs=1e-12)
    assert m["makespan_ms"] == pytest.approx(26.0)
    assert m["cpu_utilisation"] == pytest.approx(1.0)
    assert m["throughput_tasks_per_s"] == pytest.approx(4 / 0.026)
    assert m["n_completed"] == 4 and m["truncated"] is False


def test_round_robin_response_and_switch_count() -> None:
    sim = SchedulerSim(classic_tasks(), machine())
    sim.run(RoundRobin(4.0))
    assert [sim.tasks[i].first_dispatch_ms for i in (1, 2, 3, 4)] == [0.0, 4.0, 8.0, 12.0]
    # Order: P1 P2 P3 P4 P1 P3 P4 P3 -> 8 dispatches, every one a different task from the last.
    assert sim.n_dispatches == 8
    assert sim.n_context_switches == 7
    assert sim.n_preemptions == 4


def test_io_and_idle_case_fcfs() -> None:
    tasks = [
        Task(0, 0.0, "io_bound", (3.0, 2.0), (4.0,), 1.0, 0, 1000.0),
        Task(1, 1.0, "cpu_bound", (5.0,), (), 1.0, 0, 1000.0),
        Task(2, 20.0, "cpu_bound", (2.0,), (), 1.0, 0, 1000.0),
    ]
    sim = SchedulerSim(tasks, machine())
    outcomes = sim.run(FCFS())
    assert [sim.tasks[i].finish_ms for i in (0, 1, 2)] == [10.0, 8.0, 22.0]
    assert [o.decision.task_id for o in outcomes] == [0, 1, 0, 2]
    assert [o.start_ms for o in outcomes] == [0.0, 3.0, 8.0, 20.0]
    m = episode_metrics(sim, starvation_threshold_ms=1000.0)
    assert m["avg_turnaround_ms"] == pytest.approx((10 + 7 + 2) / 3)
    assert m["avg_waiting_ms"] == pytest.approx((1 + 2 + 0) / 3)
    assert m["makespan_ms"] == pytest.approx(22.0)
    assert m["cpu_utilisation"] == pytest.approx(12.0 / 22.0)
    assert sim.total_busy_ms == pytest.approx(12.0)
    assert sim.total_idle_ms == pytest.approx(10.0)
    # The A 8-10 step ends at 10 and then idles to 20: the idle is part of that step.
    assert outcomes[2].idle_ms == pytest.approx(10.0)
    assert outcomes[2].end_ms == pytest.approx(20.0)
    # Windowed throughput: tasks done by the last arrival (t=20) = A, B over a 20 ms span.
    assert m["windowed_throughput_tasks_per_s"] == pytest.approx(2 / 0.020)


def test_srtf_reference_hand_computed() -> None:
    """Preemptive SRTF, quantum 1 (re-derived by hand).

    P1 0-1; at t=1 P2 (4) beats P1 (7 left) and runs 1-5 (P3 and P4 arrive meanwhile but
    are longer than P2's remainder); at 5 the queue is P1 7, P3 9, P4 5: P4 5-10, P1 10-17,
    P3 17-26. Finish 17, 5, 26, 10; turnarounds 17, 4, 24, 7 (13.0); waits 9, 0, 15, 2
    (6.5); first dispatch 0, 1, 17, 5 -> response 0, 0, 15, 2 (4.25).
    """
    sim = SchedulerSim(classic_tasks(), machine())
    sim.run(SRTF(1.0))
    assert [sim.tasks[i].finish_ms for i in (1, 2, 3, 4)] == [17.0, 5.0, 26.0, 10.0]
    assert [sim.tasks[i].first_dispatch_ms for i in (1, 2, 3, 4)] == [0.0, 1.0, 17.0, 5.0]
    m = episode_metrics(sim, starvation_threshold_ms=1000.0)
    assert m["avg_turnaround_ms"] == pytest.approx(13.0, abs=1e-12)
    assert m["avg_waiting_ms"] == pytest.approx(6.5, abs=1e-12)
    assert m["avg_response_ms"] == pytest.approx(4.25, abs=1e-12)
    assert m["makespan_ms"] == pytest.approx(26.0)


def test_srtf_with_huge_quantum_equals_sjf() -> None:
    a = SchedulerSim(classic_tasks(), machine())
    a.run(SRTF(1e9))
    b = SchedulerSim(classic_tasks(), machine())
    b.run(SJF())
    assert [a.tasks[i].finish_ms for i in (1, 2, 3, 4)] == [
        b.tasks[i].finish_ms for i in (1, 2, 3, 4)
    ]


def test_make_policy_builds_srtf(configs_dir) -> None:
    cfg = load_baselines_config(configs_dir / "scheduler_baselines.yaml")
    policy = make_policy("srtf", cfg)
    assert isinstance(policy, SRTF) and policy.quantum_ms == cfg.srtf.quantum_ms
    assert cfg.reference_methods == ["srtf"] and "srtf" not in cfg.methods
    ddqn = load_scheduler_config(configs_dir / "scheduler_ddqn.yaml")
    shortest = min(s for s in ddqn.actions.time_slices_ms if s is not None)
    assert cfg.srtf.quantum_ms == shortest  # same preemption granularity as the agent
