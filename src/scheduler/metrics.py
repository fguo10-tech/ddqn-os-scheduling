"""Episode metrics computed from a finished (or truncated) simulation.

``avg_turnaround_ms`` (finish − arrival) is the task completion time. Two throughput
definitions are reported because in a stable queue every work-conserving scheduler
completes tasks at the arrival rate, so plain throughput (completed / makespan) barely
depends on the scheduler. ``windowed_throughput_tasks_per_s`` counts only tasks finished at
or before the last arrival, divided by the arrival span, which does depend on the order
in which work is served.

Truncated episodes: unfinished tasks are charged up to the truncation time (their
turnaround, response and waiting run until ``sim.now``; a task that has not arrived yet is
charged 0), and ``n_completed`` / ``truncated`` say how many were left. Averages are always
over all tasks, never only over finished ones.

:func:`class_metrics` reports the same per-task quantities separately for each task class
(for example inference requests and fine-tuning jobs of an LLM-style workload profile). Both
functions read the per-task values from one helper, so the two views cannot disagree.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np

from .simulator import SchedulerSim
from .tasks import TaskState

EPISODE_METRIC_FIELDS = (
    "avg_turnaround_ms",
    "p95_turnaround_ms",
    "avg_response_ms",
    "avg_waiting_ms",
    "throughput_tasks_per_s",
    "windowed_throughput_tasks_per_s",
    "cpu_utilisation",
    "makespan_ms",
    "starvation_count",
    "max_wait_ms",
    "slo_violation_rate",
    "decisions",
    "context_switches",
    "priority_adjustments",
    "preemptions",
)
"""Metric columns produced by :func:`episode_metrics` (besides ``n_tasks``, ``n_completed``,
``truncated``)."""


CLASS_METRIC_FIELDS = (
    "n_tasks",
    "n_completed",
    "avg_turnaround_ms",
    "avg_response_ms",
    "avg_waiting_ms",
    "slo_violation_rate",
    "starvation_count",
    "max_wait_ms",
)
"""Metric columns produced by :func:`class_metrics` for one task class of one episode."""


@dataclasses.dataclass(frozen=True)
class TaskRecord:
    """Per-task values at the simulator's current time (the charging rules of the module
    docstring applied to one task)."""

    task_class: str
    turnaround_ms: float
    response_ms: float
    waiting_ms: float
    longest_wait_ms: float
    violated: bool
    finish_ms: float | None


def task_records(sim: SchedulerSim) -> list[TaskRecord]:
    """One :class:`TaskRecord` per task, in the simulator's task order."""
    now = sim.now
    records: list[TaskRecord] = []
    for task in sim.tasks.values():
        current_wait = 0.0
        if task.state is TaskState.READY and task.ready_since_ms is not None:
            current_wait = now - task.ready_since_ms
        if task.finish_ms is not None:
            turnaround = task.finish_ms - task.arrival_ms
            violated = task.finish_ms > task.deadline_ms
        else:
            turnaround = max(0.0, now - task.arrival_ms)
            violated = task.deadline_ms < now
        if task.first_dispatch_ms is not None:
            response = task.first_dispatch_ms - task.arrival_ms
        else:
            response = max(0.0, now - task.arrival_ms)
        records.append(
            TaskRecord(
                task_class=task.task_type,
                turnaround_ms=turnaround,
                response_ms=response,
                waiting_ms=task.total_wait_ms + current_wait,
                longest_wait_ms=max(task.longest_wait_ms, current_wait),
                violated=violated,
                finish_ms=task.finish_ms,
            )
        )
    return records


def class_metrics(
    sim: SchedulerSim, starvation_threshold_ms: float
) -> dict[str, dict[str, float | int]]:
    """Metrics of :data:`CLASS_METRIC_FIELDS` per task class, in order of first appearance.

    Only classes that have at least one task in this workload appear. The values follow the
    same charging rules as :func:`episode_metrics`, so the task-count-weighted mean of a
    per-class average equals the episode average.
    """
    by_class: dict[str, list[TaskRecord]] = {}
    for record in task_records(sim):
        by_class.setdefault(record.task_class, []).append(record)
    result: dict[str, dict[str, float | int]] = {}
    for name, records in by_class.items():
        longest = [r.longest_wait_ms for r in records]
        result[name] = {
            "n_tasks": len(records),
            "n_completed": sum(1 for r in records if r.finish_ms is not None),
            "avg_turnaround_ms": float(np.mean([r.turnaround_ms for r in records])),
            "avg_response_ms": float(np.mean([r.response_ms for r in records])),
            "avg_waiting_ms": float(np.mean([r.waiting_ms for r in records])),
            "slo_violation_rate": sum(1 for r in records if r.violated) / len(records),
            "starvation_count": int(sum(1 for w in longest if w > starvation_threshold_ms)),
            "max_wait_ms": float(max(longest)),
        }
    return result


def episode_metrics(sim: SchedulerSim, starvation_threshold_ms: float) -> dict[str, float | int]:
    """Compute every metric in :data:`EPISODE_METRIC_FIELDS` for ``sim`` at its current time."""
    now = sim.now
    records = task_records(sim)
    n_tasks = len(records)
    turnaround = [r.turnaround_ms for r in records]
    response = [r.response_ms for r in records]
    waiting = [r.waiting_ms for r in records]
    longest = [r.longest_wait_ms for r in records]
    violations = sum(1 for r in records if r.violated)
    finishes = [r.finish_ms for r in records if r.finish_ms is not None]
    completed_by_last_arrival = sum(1 for finish in finishes if finish <= sim.last_arrival_ms)

    n_completed = len(finishes)
    truncated = n_completed < n_tasks
    end = max(finishes) if not truncated else now
    makespan = max(0.0, end - sim.first_arrival_ms)
    span = sim.last_arrival_ms - sim.first_arrival_ms
    return {
        "n_tasks": n_tasks,
        "n_completed": n_completed,
        "truncated": bool(truncated),
        "avg_turnaround_ms": float(np.mean(turnaround)),
        "p95_turnaround_ms": float(np.percentile(turnaround, 95)),
        "avg_response_ms": float(np.mean(response)),
        "avg_waiting_ms": float(np.mean(waiting)),
        "throughput_tasks_per_s": (n_completed / (makespan / 1000.0)) if makespan > 0 else math.nan,
        "windowed_throughput_tasks_per_s": (
            completed_by_last_arrival / (span / 1000.0) if span > 0 else math.nan
        ),
        "cpu_utilisation": (sim.total_busy_ms / makespan) if makespan > 0 else math.nan,
        "makespan_ms": makespan,
        "starvation_count": int(sum(1 for w in longest if w > starvation_threshold_ms)),
        "max_wait_ms": float(max(longest)) if longest else 0.0,
        "slo_violation_rate": violations / n_tasks,
        "decisions": sim.n_decisions,
        "context_switches": sim.n_context_switches,
        "priority_adjustments": sim.n_priority_adjusts,
        "preemptions": sim.n_preemptions,
    }
