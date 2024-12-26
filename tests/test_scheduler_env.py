"""Gymnasium environment: observation layout, action masks, invalid actions, determinism."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from src.scheduler.baselines import SJF
from src.scheduler.config import load_scheduler_config
from src.scheduler.env import SchedulerEnv
from src.scheduler.simulator import Decision
from src.scheduler.tasks import Task
from src.scheduler.training import (
    evaluate_agent,
    evaluate_policy,
    make_eval_workloads,
    train_agent,
)


@pytest.fixture(scope="module")
def cfg(configs_dir):
    return load_scheduler_config(configs_dir / "scheduler_ddqn.yaml")


@pytest.fixture(scope="module")
def smoke_cfg(configs_dir):
    return load_scheduler_config(configs_dir / "scheduler_ddqn.yaml", smoke=True)


def test_observation_fields_match_vector(cfg) -> None:
    env = SchedulerEnv(cfg, load_profile="medium")
    obs, info = env.reset(seed=100)
    assert len(env.OBSERVATION_FIELDS) == obs.shape[0] == env.observation_space.shape[0]
    assert len({name for name, _, _ in env.OBSERVATION_FIELDS}) == obs.shape[0]
    assert all(desc and norm for _, desc, norm in env.OBSERVATION_FIELDS)
    assert len(env.ACTION_TABLE) == env.action_space.n
    assert [row["index"] for row in env.ACTION_TABLE] == list(range(env.action_space.n))
    assert info["action_mask"].shape == (env.action_space.n,)


def test_observations_stay_inside_space_and_masks_hold(cfg) -> None:
    env = SchedulerEnv(cfg)
    rng = np.random.default_rng(7)
    num_slots = cfg.observation.num_slots
    num_slices = len(cfg.actions.time_slices_ms)
    levels = cfg.machine.num_priority_levels
    for load in ("light", "heavy"):
        obs, info = env.reset(seed=101, options={"load_profile": load})
        done = False
        while not done:
            assert env.observation_space.contains(obs)
            mask = info["action_mask"]
            state = env.decision_state
            assert mask.any() and mask[: num_slots * num_slices].any()
            for k in range(num_slots):
                block = mask[k * num_slices : (k + 1) * num_slices]
                prio = mask[num_slots * num_slices + 2 * k : num_slots * num_slices + 2 * k + 2]
                if k >= len(state.window):
                    assert not block.any() and not prio.any()  # empty slot invalid
                    continue
                assert block.all()
                task = state.window[k]
                level = task.priority + task.priority_adjust
                if (
                    env.consecutive_priority_adjusts
                    >= cfg.actions.max_priority_adjusts_per_dispatch
                ):
                    assert not prio.any()
                else:
                    assert prio[0] == (level < levels - 1)
                    assert prio[1] == (level > 0)
            action = int(rng.choice(np.flatnonzero(mask)))
            obs, _, terminated, truncated, info = env.step(action)
            assert not info["invalid_action"]
            done = terminated or truncated


def test_window_order_is_priority_then_fifo(cfg) -> None:
    env = SchedulerEnv(cfg, load_profile="heavy")
    env.reset(seed=102)
    for _ in range(30):
        window = env.decision_state.window
        keys = [(-(t.priority + t.priority_adjust), t.ready_seq) for t in window]
        # aging is on in the shipped config; with no waits above one interval the order is
        # (base priority desc, ready_seq asc). Check the weaker invariant that always holds:
        assert len(window) == min(cfg.observation.num_slots, len(env.view().ready))
        if all(t.wait_ms < cfg.guardrails.aging.interval_ms for t in window):
            assert keys == sorted(keys)
        _, _, term, trunc, _ = env.step(0)
        if term or trunc:
            break


def test_priority_budget_forces_dispatch(cfg) -> None:
    tasks = [Task(i, 0.0, "cpu_bound", (5.0,), (), 1.0, 1, 1e6) for i in range(3)]
    env = SchedulerEnv(cfg, workload=tasks)
    _, info = env.reset(seed=0)
    base = cfg.observation.num_slots * len(cfg.actions.time_slices_ms)
    for _ in range(cfg.actions.max_priority_adjusts_per_dispatch):
        assert info["action_mask"][base:].any()
        _, _, _, _, info = env.step(base)  # raise slot 0
    assert not info["action_mask"][base:].any()
    _, _, _, _, info = env.step(0)
    assert info["action_mask"][base:].any()


def test_invalid_action_is_replaced_and_penalised(cfg) -> None:
    tasks = [Task(0, 0.0, "cpu_bound", (5.0,), (), 1.0, 0, 1e6),
             Task(1, 0.0, "cpu_bound", (7.0,), (), 1.0, 0, 1e6)]  # fmt: skip
    plain = dataclasses.replace(cfg, guardrails=dataclasses.replace(cfg.guardrails, enabled=False))
    env_a = SchedulerEnv(plain, workload=tasks)
    env_b = SchedulerEnv(plain, workload=tasks)
    env_a.reset(seed=0)
    env_b.reset(seed=0)
    last_slot = cfg.observation.num_slots - 1
    bad = last_slot * len(cfg.actions.time_slices_ms)  # slot 9 is empty
    assert not env_a.action_masks()[bad]
    _, r_bad, _, _, info = env_a.step(bad)
    _, r_good, _, _, _ = env_b.step(0)  # first valid dispatch
    assert info["invalid_action"] and info["invalid_actions"] == 1
    first_task = info["decision"].task_id
    assert info["decision"] == Decision.dispatch(first_task, cfg.actions.time_slices_ms[0])
    assert first_task == env_b.sim.tasks[first_task].task_id
    assert env_a.sim.tasks[first_task].dispatch_count == 1
    assert r_bad == pytest.approx(r_good - cfg.reward.invalid_action_penalty)
    _, _, _, _, info = env_a.step(10**6)  # out of range is invalid too
    assert info["invalid_actions"] == 2


def test_step_decision_matches_baseline_simulation(cfg) -> None:
    env = SchedulerEnv(cfg, load_profile="medium")
    env.reset(seed=103)
    policy = SJF()
    done = False
    while not done:
        _, _, term, trunc, info = env.step_decision(policy.decide(env.view()))
        assert info["overridden"] is False and info["guardrail"] is None
        done = term or trunc
    assert env.sim is not None and env.sim.done


def test_truncation_at_max_steps(cfg) -> None:
    short = dataclasses.replace(
        cfg, training=dataclasses.replace(cfg.training, max_steps_per_episode=5)
    )
    env = SchedulerEnv(short, load_profile="heavy")
    env.reset(seed=104)
    for _ in range(5):
        _, _, term, trunc, _ = env.step(0)
    assert trunc and not term


def test_same_seed_gives_identical_evaluation_rows(smoke_cfg) -> None:
    workloads = make_eval_workloads(smoke_cfg, 100)
    assert workloads == make_eval_workloads(smoke_cfg, 100)
    rows_a = evaluate_policy(smoke_cfg, SJF(), workloads, 100)
    rows_b = evaluate_policy(smoke_cfg, SJF(), workloads, 100)
    assert rows_a == rows_b
    agent_a = train_agent(smoke_cfg, 100).agent
    agent_b = train_agent(smoke_cfg, 100).agent
    eval_a = evaluate_agent(smoke_cfg, agent_a, workloads, 100, "ddqn", True)
    eval_b = evaluate_agent(smoke_cfg, agent_b, workloads, 100, "ddqn", True)
    assert eval_a == eval_b


def test_documentation_tables_cover_every_dimension_and_action(cfg) -> None:
    from src.scheduler.env import action_table_markdown, observation_table_markdown

    env = SchedulerEnv(cfg, load_profile="light")
    obs, _ = env.reset(seed=100)
    obs_rows = [ln for ln in observation_table_markdown().splitlines() if ln.startswith("| ")]
    act_rows = [ln for ln in action_table_markdown().splitlines() if ln.startswith("| ")]
    assert len(obs_rows) - 1 == obs.shape[0]  # minus the header row
    assert len(act_rows) - 1 == env.action_space.n
    assert observation_table_markdown(cfg) == observation_table_markdown()
    assert all(row.count("|") == 6 for row in obs_rows)  # no unescaped pipes
    assert all(row.count("|") == 7 for row in act_rows)


def test_encoding_is_identical_with_overrides_on_and_off(cfg) -> None:
    """ddqn_unguarded must see exactly what ddqn sees: only the override rules differ."""
    from src.scheduler.config import with_guardrails

    on = with_guardrails(cfg, True)
    off = with_guardrails(cfg, False)
    env_on = SchedulerEnv(on, load_profile="heavy")
    env_off = SchedulerEnv(off, load_profile="heavy")
    assert env_on.layout == env_off.layout
    env_on.reset(seed=108)
    env_off.reset(seed=108)
    policy = SJF()
    steps = 0
    while True:
        a, b = env_on.decision_state, env_off.decision_state
        assert np.array_equal(a.observation, b.observation)
        assert np.array_equal(a.mask, b.mask)
        assert [t.task_id for t in a.window] == [t.task_id for t in b.window]
        decision = policy.decide(env_on.view())
        _, _, term, trunc, _ = env_on.step_decision(decision)
        env_off.step_decision(decision)
        steps += 1
        if term or trunc:
            break
    assert steps > 50


def test_default_observation_has_no_future_burst_information(cfg) -> None:
    """Information parity: two states that differ only in FUTURE bursts look identical."""
    names = [name for name, _, _ in SchedulerEnv(cfg).OBSERVATION_FIELDS]
    assert not any("total" in name for name in names)

    def tasks(later: float) -> list[Task]:
        return [Task(0, 0.0, "cpu_bound", (5.0, later), (3.0,), 1.0, 1, 500.0),
                Task(1, 0.0, "cpu_bound", (7.0,), (), 1.0, 1, 500.0)]  # fmt: skip

    obs_a, _ = SchedulerEnv(cfg, workload=tasks(1.0)).reset(seed=0)
    obs_b, _ = SchedulerEnv(cfg, workload=tasks(300.0)).reset(seed=0)
    assert np.array_equal(obs_a, obs_b)
    oracle = dataclasses.replace(
        cfg, observation=dataclasses.replace(cfg.observation, reveal_total_remaining_cpu=True)
    )
    env_o = SchedulerEnv(oracle, workload=tasks(1.0))
    oa, _ = env_o.reset(seed=0)
    ob, _ = SchedulerEnv(oracle, workload=tasks(300.0)).reset(seed=0)
    assert not np.array_equal(oa, ob)
    assert len(env_o.OBSERVATION_FIELDS) == oa.shape[0] > obs_a.shape[0]
