"""Each guardrail is forced to fire; the override and the return to normal are asserted."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from src.scheduler.config import load_scheduler_config
from src.scheduler.env import SchedulerEnv
from src.scheduler.guardrails import GuardrailEngine
from src.scheduler.simulator import Decision, SimView, TaskView
from src.scheduler.tasks import Task


@pytest.fixture(scope="module")
def cfg(configs_dir):
    return load_scheduler_config(configs_dir / "scheduler_ddqn.yaml")


def tv(task_id: int, wait: float, seq: int, burst: float = 10.0) -> TaskView:
    return TaskView(task_id, "cpu_bound", 0.0, 1, 0, seq, wait, burst, burst, 10.0, False,
                    False, 1e9, wait)  # fmt: skip


def view(now: float, *tasks: TaskView) -> SimView:
    return SimView(now, tuple(tasks), 0, 0, 0, 0.0, 4096.0, 4, None)


def test_starvation_override_fires_and_returns_to_normal(cfg) -> None:
    engine = GuardrailEngine(cfg.guardrails)
    limit = cfg.guardrails.starvation.max_wait_ms
    proposed = Decision.dispatch(1, 10.0)
    starving = view(5000.0, tv(0, limit + 1.0, 0), tv(1, 5.0, 1), tv(2, limit + 50.0, 2))
    result = engine.filter(starving, proposed)
    assert result.overridden and result.rule == "starvation"
    assert result.decision == Decision.dispatch(2, cfg.guardrails.starvation.forced_time_slice_ms)
    assert engine.counts["guardrail_starvation_triggers"] == 1
    calm = view(5001.0, tv(0, 10.0, 0), tv(1, 5.0, 1))
    result = engine.filter(calm, proposed)
    assert not result.overridden and result.rule is None and result.decision == proposed


def test_starvation_override_inside_env(cfg) -> None:
    """Crafted wait: a long task hogs the CPU while a second task waits past max_wait."""
    tight = dataclasses.replace(
        cfg,
        guardrails=dataclasses.replace(
            cfg.guardrails,
            starvation=dataclasses.replace(cfg.guardrails.starvation, max_wait_ms=30.0),
        ),
    )
    tasks = [Task(0, 0.0, "cpu_bound", (100.0,), (), 1.0, 3, 1e6),
             Task(1, 0.0, "cpu_bound", (5.0,), (), 1.0, 0, 1e6)]  # fmt: skip
    env = SchedulerEnv(tight, workload=tasks)
    env.reset(seed=0)
    slot0_slice40 = 1  # DISPATCH(slot 0 = task 0 by priority, 40 ms)
    _, _, _, _, info = env.step(slot0_slice40)
    assert info["guardrail"] is None and env.view().get(1).wait_ms >= 30.0
    _, _, _, _, info = env.step(slot0_slice40)  # would run task 0 again
    assert info["guardrail"] == "starvation" and info["overridden"]
    assert info["decision"].task_id == 1
    assert info["guardrail_counts"]["guardrail_starvation_triggers"] == 1


def test_slo_fallback_switches_to_round_robin_and_back(cfg) -> None:
    slo = dataclasses.replace(
        cfg.guardrails.slo_fallback, window_completions=4, violation_threshold=3,
        fallback_duration_ms=100.0, fallback_quantum_ms=7.0,
    )  # fmt: skip
    gcfg = dataclasses.replace(
        cfg.guardrails,
        slo_fallback=slo,
        starvation=dataclasses.replace(cfg.guardrails.starvation, enabled=False),
    )
    engine = GuardrailEngine(gcfg)
    proposed = Decision.dispatch(1, None)
    v = view(10.0, tv(0, 1.0, 0), tv(1, 1.0, 1))
    engine.record_completions(10.0, [True, False, True])  # 2 late: not yet
    assert not engine.filter(v, proposed).overridden
    engine.record_completions(10.0, [True])  # stream of late completions -> 3 of last 4
    assert engine.counts["guardrail_slo_fallback_activations"] == 1
    result = engine.filter(view(50.0, tv(0, 1.0, 0), tv(1, 1.0, 1)), proposed)
    assert result.rule == "slo_fallback" and result.overridden
    assert result.decision == Decision.dispatch(0, 7.0)  # Round Robin: oldest, quantum 7
    # after fallback_duration_ms control returns and the window is clear
    result = engine.filter(view(110.0, tv(0, 1.0, 0), tv(1, 1.0, 1)), proposed)
    assert result.rule is None and result.decision == proposed
    engine.record_completions(110.0, [True])  # one late completion cannot re-trigger
    assert engine.counts["guardrail_slo_fallback_activations"] == 1
    assert engine.filter(view(111.0, tv(0, 1.0, 0)), Decision.dispatch(0, None)).rule is None


@pytest.mark.parametrize("bad", [np.nan, np.inf, 1e9])
def test_q_divergence_latch(cfg, bad) -> None:
    engine = GuardrailEngine(cfg.guardrails)
    v = view(1.0, tv(0, 1.0, 0, burst=50.0), tv(1, 1.0, 1, burst=5.0))
    proposed = Decision.dispatch(1, None)
    assert not engine.report_q_values(np.array([1.0, -2.0]))
    assert engine.filter(v, proposed).rule is None
    assert engine.report_q_values(np.array([0.0, bad]))
    result = engine.filter(v, proposed)
    assert result.rule == "q_divergence" and result.overridden
    quantum = cfg.guardrails.q_divergence.fallback_quantum_ms
    assert result.decision == Decision.dispatch(0, quantum)  # round_robin fallback
    engine.report_q_values(np.array([0.0, 0.0]))  # healthy values do not unlatch
    assert engine.filter(v, proposed).rule == "q_divergence"
    engine.reset(clear_latch=False)
    assert engine.latched and engine.filter(v, proposed).rule == "q_divergence"
    engine.reset(clear_latch=True)
    assert not engine.latched and engine.filter(v, proposed).rule is None
    assert engine.counts["guardrail_q_divergence_latches"] == 0  # counters reset per episode


def test_q_divergence_inside_env_lasts_for_the_episode(cfg) -> None:
    env = SchedulerEnv(cfg, load_profile="medium")
    obs, info = env.reset(seed=100)
    n = env.action_space.n
    env.report_q_values(np.full(n, np.nan))
    _, _, _, _, info = env.step(0)
    assert info["q_latched"] and "q_divergence" in info["rules_fired"]
    for _ in range(5):
        env.report_q_values(np.zeros(n))
        _, _, term, _, info = env.step(0)
        assert "q_divergence" in info["rules_fired"]
        if term:
            break
    env.reset(seed=101)
    assert not env.guardrails.latched


def test_master_switch_disables_everything(cfg) -> None:
    off = dataclasses.replace(cfg.guardrails, enabled=False)
    engine = GuardrailEngine(off)
    engine.report_q_values(np.array([np.nan]))
    engine.record_completions(0.0, [True] * 20)
    proposed = Decision.dispatch(1, None)
    result = engine.filter(view(9999.0, tv(0, 9999.0, 0), tv(1, 1.0, 1)), proposed)
    assert result.decision == proposed and not result.overridden


def test_completion_right_after_fallback_expiry_is_kept(cfg) -> None:
    slo = dataclasses.replace(
        cfg.guardrails.slo_fallback, window_completions=4, violation_threshold=3,
        fallback_duration_ms=100.0,
    )  # fmt: skip
    gcfg = dataclasses.replace(
        cfg.guardrails,
        slo_fallback=slo,
        starvation=dataclasses.replace(cfg.guardrails.starvation, enabled=False),
    )
    engine = GuardrailEngine(gcfg)
    engine.record_completions(10.0, [True, True, True])  # fallback until t=110
    assert engine.counts["guardrail_slo_fallback_activations"] == 1
    engine.record_completions(120.0, [True])  # after expiry: must be kept
    v = view(121.0, tv(0, 1.0, 0))
    assert engine.filter(v, Decision.dispatch(0, None)).rule is None
    engine.record_completions(122.0, [True, True])  # 3 late in the window -> fires again
    assert engine.counts["guardrail_slo_fallback_activations"] == 2


def test_precedence_when_several_rules_apply(cfg) -> None:
    """Latch, then SLO fallback, then starvation: each later rule replaces the earlier decision."""
    slo = dataclasses.replace(
        cfg.guardrails.slo_fallback, window_completions=4, violation_threshold=3,
        fallback_duration_ms=100.0, fallback_quantum_ms=7.0,
    )  # fmt: skip
    latch = dataclasses.replace(
        cfg.guardrails.q_divergence, fallback_policy="round_robin", fallback_quantum_ms=13.0
    )
    gcfg = dataclasses.replace(cfg.guardrails, slo_fallback=slo, q_divergence=latch)
    limit = gcfg.starvation.max_wait_ms
    engine = GuardrailEngine(gcfg)
    proposed = Decision.dispatch(1, None)
    calm = view(20.0, tv(0, 1.0, 0), tv(1, 1.0, 1))
    starving = view(20.0, tv(0, 1.0, 0), tv(1, 1.0, 1), tv(2, limit + 1.0, 2))

    assert engine.report_q_values(np.array([np.nan, 0.0]))  # the latch alone
    result = engine.filter(calm, proposed)
    assert result.rule == "q_divergence" and result.rules_fired == ("q_divergence",)
    assert result.decision == Decision.dispatch(0, 13.0)  # the latch's fallback baseline

    engine.record_completions(10.0, [True, True, True])  # SLO fallback active until t = 110
    result = engine.filter(calm, proposed)
    assert result.rule == "slo_fallback"
    assert result.rules_fired == ("q_divergence", "slo_fallback")
    assert result.decision == Decision.dispatch(0, 7.0)  # the SLO rule's quantum, not the latch's

    result = engine.filter(starving, proposed)  # all three apply: starvation wins
    assert result.rule == "starvation"
    assert result.rules_fired == ("q_divergence", "slo_fallback", "starvation")
    assert result.decision == Decision.dispatch(2, gcfg.starvation.forced_time_slice_ms)
    assert engine.counts["guardrail_overrides"] == 3


def test_q_magnitude_limit_applies_to_valid_actions_only(cfg) -> None:
    limit = cfg.guardrails.q_divergence.q_abs_limit
    mask = np.array([True, False, True])
    engine = GuardrailEngine(cfg.guardrails)
    assert not engine.report_q_values(np.array([1.0, 10 * limit, 2.0]), mask)  # masked: ignored
    assert not engine.latched
    assert engine.report_q_values(np.array([1.0, 0.0, 10 * limit]), mask)  # valid: latch
    engine.reset(clear_latch=True)
    assert engine.report_q_values(np.array([1.0, np.nan, 2.0]), mask)  # NaN anywhere: latch
