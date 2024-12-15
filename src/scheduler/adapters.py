"""Job-queue adapter sketches: Kubernetes-style pending Pods and Ray-style job submissions.

Adapter sketch — not a production integration.

Both adapters are pure-Python translators between plain dicts *shaped like* the objects of
those systems and the plugin types (:class:`~src.scheduler.plugin.QueueSnapshot`,
:class:`~src.scheduler.plugin.SchedulingDecision`). They import neither ``kubernetes`` nor
``ray``, call no API and have never been run against a real cluster. The annotation and
metadata keys they read (``scheduler.example/...``) are invented for this sketch; a real
integration would need a runtime estimate source, a feedback path for completions, and the
platform's own notion of preemption, none of which exists here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .plugin import JobView, QueueSnapshot, ResourceState, SchedulingDecision

ANNOTATION_PREFIX = "scheduler.example/"
"""Annotation / metadata key prefix used by the sketches (invented, not a real convention)."""

_MEMORY_UNITS = {
    "": 1.0 / (1024 * 1024),
    "Ki": 1.0 / 1024,
    "Mi": 1.0,
    "Gi": 1024.0,
    "Ti": 1024.0 * 1024,
    "K": 1000.0 / (1024 * 1024),
    "M": 1000.0**2 / (1024 * 1024),
    "G": 1000.0**3 / (1024 * 1024),
}


def parse_memory_mb(quantity: str | int | float) -> float:
    """Kubernetes-style memory quantity (``"512Mi"``, ``"2Gi"``, bytes) to MB (MiB).

    Adapter sketch — not a production integration.
    """
    if isinstance(quantity, (int, float)):
        return float(quantity) / (1024 * 1024)
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]*)\s*", str(quantity))
    if not match or match.group(2) not in _MEMORY_UNITS:
        raise ValueError(f"cannot parse memory quantity {quantity!r}")
    return float(match.group(1)) * _MEMORY_UNITS[match.group(2)]


def _resources(
    resources: Mapping[str, Any],
    blocked: int,
    num_priority_levels: int,
    last_job_id: int | None,
) -> ResourceState:
    return ResourceState(
        memory_capacity_mb=float(resources["memory_capacity_mb"]),
        resident_memory_mb=float(resources.get("resident_memory_mb", 0.0)),
        blocked_jobs=int(blocked),
        num_priority_levels=int(num_priority_levels),
        recent_cpu_utilisation=float(resources.get("recent_cpu_utilisation", 0.0)),
        recent_arrival_rate_per_s=float(resources.get("recent_arrival_rate_per_s", 0.0)),
        recent_slo_violation_rate=float(resources.get("recent_slo_violation_rate", 0.0)),
        last_job_id=last_job_id,
    )


class KubernetesStyleQueueAdapter:
    """Pending-Pod dicts ⇄ plugin types.

    Adapter sketch — not a production integration.

    Expected Pod shape (only these keys are read)::

        {"metadata": {"name": "train-7", "creationTimestampMs": 1200.0,
                      "annotations": {"scheduler.example/expected-runtime-ms": "35",
                                      "scheduler.example/deadline-ms": "4000",
                                      "scheduler.example/job-class": "cpu_bound"}},
         "spec": {"priority": 2,
                  "containers": [{"resources": {"requests": {"memory": "512Mi"}}}]},
         "status": {"phase": "Pending"}}

    Only Pods in phase ``Pending`` become jobs. Pod names are mapped to stable integer job
    ids in first-seen order.
    """

    def __init__(self, num_priority_levels: int) -> None:
        self.num_priority_levels = int(num_priority_levels)
        self._ids: dict[str, int] = {}
        self._names: dict[int, str] = {}

    def job_id(self, name: str) -> int:
        """Stable integer id for a Pod name."""
        if name not in self._ids:
            new_id = len(self._ids)
            self._ids[name] = new_id
            self._names[new_id] = name
        return self._ids[name]

    def pod_name(self, job_id: int) -> str:
        """Pod name of an integer job id."""
        return self._names[job_id]

    def to_snapshot(
        self,
        pods: Sequence[Mapping[str, Any]],
        now_ms: float,
        resources: Mapping[str, Any],
    ) -> QueueSnapshot:
        """Translate pending Pod dicts into a :class:`QueueSnapshot`.

        Adapter sketch — not a production integration.
        """
        jobs: list[JobView] = []
        pending = [p for p in pods if p.get("status", {}).get("phase", "Pending") == "Pending"]
        ordered = sorted(
            pending,
            key=lambda p: (float(p["metadata"].get("creationTimestampMs", 0.0)),
                           p["metadata"]["name"]),
        )  # fmt: skip
        for seq, pod in enumerate(ordered):
            meta = pod["metadata"]
            notes = meta.get("annotations", {})
            created = float(meta.get("creationTimestampMs", now_ms))
            runtime = float(notes.get(ANNOTATION_PREFIX + "expected-runtime-ms", 0.0))
            deadline = float(notes.get(ANNOTATION_PREFIX + "deadline-ms", now_ms))
            memory = sum(
                parse_memory_mb(c.get("resources", {}).get("requests", {}).get("memory", 0))
                for c in pod.get("spec", {}).get("containers", [])
            )
            priority = int(pod.get("spec", {}).get("priority", 0))
            priority = max(0, min(self.num_priority_levels - 1, priority))
            jobs.append(
                JobView(
                    job_id=self.job_id(meta["name"]),
                    queue_wait_ms=max(0.0, now_ms - created),
                    expected_remaining_work_ms=runtime,
                    expected_next_burst_ms=runtime,
                    memory_request_mb=memory,
                    priority=priority,
                    priority_offset=0,
                    deadline_slack_ms=deadline - now_ms,
                    started=False,
                    job_class=str(notes.get(ANNOTATION_PREFIX + "job-class", "cpu_bound")),
                    queue_seq=seq,
                    time_in_system_ms=max(0.0, now_ms - created),
                    dispatched_before=False,
                )
            )
        return QueueSnapshot(
            now_ms=float(now_ms),
            jobs=tuple(jobs),
            resources=_resources(
                resources, int(resources.get("blocked_jobs", 0)), self.num_priority_levels, None
            ),
        )

    def to_action(self, decision: SchedulingDecision) -> dict[str, Any]:
        """Describe the intended action as a plain dict (nothing is sent anywhere).

        Adapter sketch — not a production integration.
        """
        name = self.pod_name(decision.job_id)
        if decision.priority_change is not None:
            return {
                "action": "patch_priority",
                "pod": name,
                "priority_delta": int(decision.priority_change),
                "decided_by": decision.decided_by,
            }
        return {
            "action": "bind",
            "pod": name,
            "time_slice_ms": decision.time_slice_ms,
            "run_to_completion": decision.time_slice_ms is None,
            "decided_by": decision.decided_by,
        }


class RayStyleQueueAdapter:
    """Ray-style job-submission dicts ⇄ plugin types.

    Adapter sketch — not a production integration.

    Expected submission shape (only these keys are read)::

        {"submission_id": "raysubmit_42", "status": "PENDING", "submitted_at_ms": 50.0,
         "entrypoint_memory": 1073741824,              # bytes
         "metadata": {"expected_runtime_ms": "120", "deadline_ms": "900",
                      "priority": "1", "job_class": "memory_bound"}}

    Only submissions with status ``PENDING`` become jobs.
    """

    def __init__(self, num_priority_levels: int) -> None:
        self.num_priority_levels = int(num_priority_levels)
        self._ids: dict[str, int] = {}
        self._subs: dict[int, str] = {}

    def job_id(self, submission_id: str) -> int:
        """Stable integer id for a submission id."""
        if submission_id not in self._ids:
            new_id = len(self._ids)
            self._ids[submission_id] = new_id
            self._subs[new_id] = submission_id
        return self._ids[submission_id]

    def submission_id(self, job_id: int) -> str:
        """Submission id of an integer job id."""
        return self._subs[job_id]

    def to_snapshot(
        self,
        submissions: Sequence[Mapping[str, Any]],
        now_ms: float,
        resources: Mapping[str, Any],
    ) -> QueueSnapshot:
        """Translate pending submissions into a :class:`QueueSnapshot`.

        Adapter sketch — not a production integration.
        """
        pending = [s for s in submissions if s.get("status", "PENDING") == "PENDING"]
        ordered = sorted(
            pending, key=lambda s: (float(s.get("submitted_at_ms", 0.0)), s["submission_id"])
        )
        jobs: list[JobView] = []
        for seq, sub in enumerate(ordered):
            meta = sub.get("metadata", {})
            submitted = float(sub.get("submitted_at_ms", now_ms))
            runtime = float(meta.get("expected_runtime_ms", 0.0))
            priority = max(0, min(self.num_priority_levels - 1, int(meta.get("priority", 0))))
            jobs.append(
                JobView(
                    job_id=self.job_id(sub["submission_id"]),
                    queue_wait_ms=max(0.0, now_ms - submitted),
                    expected_remaining_work_ms=runtime,
                    expected_next_burst_ms=runtime,
                    memory_request_mb=parse_memory_mb(int(sub.get("entrypoint_memory", 0))),
                    priority=priority,
                    priority_offset=0,
                    deadline_slack_ms=float(meta.get("deadline_ms", now_ms)) - now_ms,
                    started=False,
                    job_class=str(meta.get("job_class", "cpu_bound")),
                    queue_seq=seq,
                    time_in_system_ms=max(0.0, now_ms - submitted),
                    dispatched_before=False,
                )
            )
        return QueueSnapshot(
            now_ms=float(now_ms),
            jobs=tuple(jobs),
            resources=_resources(
                resources, int(resources.get("blocked_jobs", 0)), self.num_priority_levels, None
            ),
        )

    def to_action(self, decision: SchedulingDecision) -> dict[str, Any]:
        """Describe the intended action as a plain dict (nothing is sent anywhere).

        Adapter sketch — not a production integration.
        """
        sub = self.submission_id(decision.job_id)
        if decision.priority_change is not None:
            return {
                "action": "reprioritise",
                "submission_id": sub,
                "priority_delta": int(decision.priority_change),
                "decided_by": decision.decided_by,
            }
        return {
            "action": "start_job",
            "submission_id": sub,
            "time_slice_ms": decision.time_slice_ms,
            "run_to_completion": decision.time_slice_ms is None,
            "decided_by": decision.decided_by,
        }
