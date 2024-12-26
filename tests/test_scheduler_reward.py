"""Reward signs: every time term is a penalty; the alternative sign convention is an ablation."""

from __future__ import annotations

import dataclasses

import pytest

from src.scheduler.config import load_scheduler_config
from src.scheduler.reward import compute_reward
from src.scheduler.simulator import Decision, StepOutcome


@pytest.fixture(scope="module")
def reward_cfg(configs_dir):
    cfg = load_scheduler_config(configs_dir / "scheduler_ddqn.yaml").reward
    # make every weight strictly positive so each sign test is meaningful
    return dataclasses.replace(
        cfg, w_wait=0.5, w_turnaround=1.0, w_response=0.25, w_slo_violation=0.5,
        w_completion=0.1, w_utilisation=0.05, paper_sign_as_printed=False,
    )  # fmt: skip


def outcome(**changes) -> StepOutcome:
    base = dict(
        decision=Decision.dispatch(0, None),
        start_ms=0.0,
        end_ms=20.0,
        duration_ms=20.0,
        wait_ms=40.0,
        in_system_ms=80.0,
        response_wait_ms=10.0,
        busy_ms=18.0,
        idle_ms=0.0,
        overhead_ms=2.0,
        arrivals=1,
        completed=(),
        late_completed=(),
        deadline_misses=(),
        context_switch=True,
        done=False,
    )
    base.update(changes)
    return StepOutcome(**base)


def test_more_waiting_lowers_reward(reward_cfg) -> None:
    assert compute_reward(outcome(wait_ms=60.0), reward_cfg) < compute_reward(outcome(), reward_cfg)


def test_more_response_wait_lowers_reward(reward_cfg) -> None:
    worse = compute_reward(outcome(response_wait_ms=30.0), reward_cfg)
    assert worse < compute_reward(outcome(), reward_cfg)


def test_more_time_in_system_lowers_reward(reward_cfg) -> None:
    worse = compute_reward(outcome(in_system_ms=120.0), reward_cfg)
    assert worse < compute_reward(outcome(), reward_cfg)


def test_deadline_misses_lower_reward(reward_cfg) -> None:
    worse = compute_reward(outcome(deadline_misses=(3, 4)), reward_cfg)
    assert worse < compute_reward(outcome(deadline_misses=(3,)), reward_cfg)
    assert compute_reward(outcome(deadline_misses=(3,)), reward_cfg) < compute_reward(
        outcome(), reward_cfg
    )


def test_completion_raises_reward(reward_cfg) -> None:
    assert compute_reward(outcome(completed=(1,)), reward_cfg) > compute_reward(
        outcome(), reward_cfg
    )


def test_exact_reward_formula(reward_cfg) -> None:
    o = outcome(completed=(1,), deadline_misses=(2,))
    tau = reward_cfg.time_scale_ms
    expected = (
        -0.5 * 40 / tau - 1.0 * 80 / tau - 0.25 * 10 / tau - 0.5 * 1 + 0.1 * 1 + 0.05 * 18 / 20
    )
    assert compute_reward(o, reward_cfg) == pytest.approx(expected)


def test_alternative_sign_ablation_rewards_slow_response(reward_cfg) -> None:
    """The ablation r = a1*U - a2*T + a3*R: with a3 > 0, slower response earns MORE reward."""
    printed = dataclasses.replace(reward_cfg, paper_sign_as_printed=True)
    slow = compute_reward(outcome(response_wait_ms=30.0), printed)
    fast = compute_reward(outcome(response_wait_ms=10.0), printed)
    assert slow > fast
    tau = printed.time_scale_ms
    assert fast == pytest.approx(0.05 * 18 / 20 - 1.0 * 80 / tau + 0.25 * 10 / tau)
