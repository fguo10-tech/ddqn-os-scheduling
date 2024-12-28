"""Plugin ⇄ env decision equality (no train / serve skew) and adapter sketches."""

from __future__ import annotations

import dataclasses

import pytest

from src.scheduler.adapters import (
    KubernetesStyleQueueAdapter,
    RayStyleQueueAdapter,
    parse_memory_mb,
)
from src.scheduler.agent import masked_argmax
from src.scheduler.baselines import SJF
from src.scheduler.config import load_scheduler_config
from src.scheduler.env import SchedulerEnv
from src.scheduler.guardrails import decided_by
from src.scheduler.plugin import (
    BaselineSchedulerPlugin,
    DDQNSchedulerPlugin,
    SchedulerPlugin,
    SchedulingDecision,
    SchedulingFeedback,
    snapshot_from_view,
)
from src.scheduler.training import train_agent


@pytest.fixture(scope="module")
def trained(configs_dir):
    cfg = load_scheduler_config(configs_dir / "scheduler_ddqn.yaml", smoke=True)
    # tight guardrails so that the starvation and SLO rules are exercised in the comparison
    guard = dataclasses.replace(
        cfg.guardrails,
        starvation=dataclasses.replace(cfg.guardrails.starvation, max_wait_ms=60.0),
        slo_fallback=dataclasses.replace(
            cfg.guardrails.slo_fallback, window_completions=3, violation_threshold=1,
            fallback_duration_ms=40.0,
        ),
    )  # fmt: skip
    cfg = dataclasses.replace(cfg, guardrails=guard)
    return cfg, train_agent(cfg, 100).agent


@pytest.mark.parametrize("load", ["medium", "heavy"])
def test_plugin_makes_same_decisions_as_agent_in_env(trained, load) -> None:
    cfg, agent = trained
    env = SchedulerEnv(cfg, load_profile=load)
    plugin = DDQNSchedulerPlugin(agent, cfg)
    assert isinstance(plugin, SchedulerPlugin)
    obs, info = env.reset(seed=105)
    plugin.reset(clear_latch=True)
    rules_seen = set()
    steps = 0
    while True:
        snapshot = snapshot_from_view(env.view(), env.recent.snapshot())
        plugin_decision = plugin.decide(snapshot)
        q = agent.q_values(obs)
        env.report_q_values(q)
        obs, _, term, trunc, info = env.step(masked_argmax(q, info["action_mask"]))
        executed = info["decision"]
        assert plugin_decision.to_decision() == executed, f"step {steps}"
        assert plugin_decision.decided_by == decided_by(info["guardrail"])
        rules_seen.add(info["guardrail"])
        outcome = info["outcome"]
        plugin.observe(SchedulingFeedback(env.sim.now, outcome.completed, outcome.late_completed))
        steps += 1
        if term or trunc:
            break
    assert steps > 20
    assert "starvation" in rules_seen or "slo_fallback" in rules_seen
    assert plugin.health().healthy


def test_plugin_falls_back_when_model_fails(trained) -> None:
    cfg, agent = trained

    class Broken:
        def q_values(self, obs):
            raise RuntimeError("model server down")

    env = SchedulerEnv(cfg, load_profile="light")
    env.reset(seed=106)
    plugin = DDQNSchedulerPlugin(Broken(), cfg)  # type: ignore[arg-type]
    decision = plugin.decide(snapshot_from_view(env.view(), env.recent.snapshot()))
    assert decision.decided_by == "fallback:q_divergence"
    health = plugin.health()
    assert not health.healthy and "model server down" in health.message
    plugin.reset()
    assert plugin.health().latched  # survives reset until an operator clears it
    plugin.reset(clear_latch=True)
    assert plugin.health().healthy


def test_baseline_plugin_matches_policy(trained) -> None:
    cfg, _ = trained
    env = SchedulerEnv(cfg, load_profile="heavy")
    env.reset(seed=107)
    plugin = BaselineSchedulerPlugin(SJF())
    for _ in range(25):
        decision = plugin.decide(snapshot_from_view(env.view(), env.recent.snapshot()))
        expected = SJF().decide(env.view())
        assert decision.to_decision() == expected and decision.decided_by == "baseline:sjf"
        _, _, term, trunc, _ = env.step_decision(expected)
        if term or trunc:
            break


RESOURCES = {"memory_capacity_mb": 4096.0, "resident_memory_mb": 512.0}


def test_kubernetes_adapter_sketch() -> None:
    pods = [
        {
            "metadata": {
                "name": "etl-2",
                "creationTimestampMs": 300.0,
                "annotations": {
                    "scheduler.example/expected-runtime-ms": "35",
                    "scheduler.example/deadline-ms": "900",
                    "scheduler.example/job-class": "io_bound",
                },
            },
            "spec": {"priority": 7, "containers": [
                {"resources": {"requests": {"memory": "512Mi"}}},
                {"resources": {"requests": {"memory": "1Gi"}}},
            ]},
            "status": {"phase": "Pending"},
        },
        {"metadata": {"name": "train-1", "creationTimestampMs": 100.0}, "spec": {"priority": 1},
         "status": {"phase": "Pending"}},
        {"metadata": {"name": "done-0"}, "status": {"phase": "Running"}},
    ]  # fmt: skip
    adapter = KubernetesStyleQueueAdapter(num_priority_levels=4)
    snap = adapter.to_snapshot(pods, now_ms=500.0, resources=RESOURCES)
    assert [j.job_id for j in snap.jobs] == [adapter.job_id("train-1"), adapter.job_id("etl-2")]
    etl = snap.jobs[1]
    assert etl.memory_request_mb == pytest.approx(1536.0)
    assert etl.priority == 3  # clamped to the top level
    assert etl.queue_wait_ms == 200.0 and etl.deadline_slack_ms == 400.0
    assert etl.job_class == "io_bound" and etl.expected_next_burst_ms == 35.0
    assert snap.resources.resident_memory_mb == 512.0
    action = adapter.to_action(SchedulingDecision(etl.job_id, None, None, "agent"))
    assert action == {"action": "bind", "pod": "etl-2", "time_slice_ms": None,
                      "run_to_completion": True, "decided_by": "agent"}  # fmt: skip
    action = adapter.to_action(SchedulingDecision(etl.job_id, None, -1, "agent"))
    assert action["action"] == "patch_priority" and action["priority_delta"] == -1
    plugin = BaselineSchedulerPlugin(SJF())
    # train-1 has no runtime annotation (expected 0 ms), so SJF picks it first
    assert plugin.decide(snap).job_id == adapter.job_id("train-1")


def test_ray_adapter_sketch() -> None:
    subs = [
        {"submission_id": "raysubmit_b", "status": "PENDING", "submitted_at_ms": 20.0,
         "entrypoint_memory": 2 * 1024**3,
         "metadata": {"expected_runtime_ms": "120", "deadline_ms": "900", "priority": "1",
                      "job_class": "memory_bound"}},
        {"submission_id": "raysubmit_a", "status": "PENDING", "submitted_at_ms": 10.0,
         "metadata": {"expected_runtime_ms": "15"}},
        {"submission_id": "raysubmit_c", "status": "RUNNING"},
    ]  # fmt: skip
    adapter = RayStyleQueueAdapter(num_priority_levels=4)
    snap = adapter.to_snapshot(subs, now_ms=100.0, resources=RESOURCES)
    assert [adapter.submission_id(j.job_id) for j in snap.jobs] == ["raysubmit_a", "raysubmit_b"]
    big = snap.jobs[1]
    assert big.memory_request_mb == pytest.approx(2048.0) and big.priority == 1
    assert big.queue_wait_ms == 80.0 and big.deadline_slack_ms == 800.0
    decision = BaselineSchedulerPlugin(SJF()).decide(snap)
    assert adapter.submission_id(decision.job_id) == "raysubmit_a"
    action = adapter.to_action(SchedulingDecision(decision.job_id, 20.0, None, "agent"))
    assert action == {"action": "start_job", "submission_id": "raysubmit_a",
                      "time_slice_ms": 20.0, "run_to_completion": False,
                      "decided_by": "agent"}  # fmt: skip


def test_parse_memory() -> None:
    assert parse_memory_mb("512Mi") == 512.0
    assert parse_memory_mb("2Gi") == 2048.0
    assert parse_memory_mb(1024 * 1024) == 1.0
    with pytest.raises(ValueError):
        parse_memory_mb("lots")
