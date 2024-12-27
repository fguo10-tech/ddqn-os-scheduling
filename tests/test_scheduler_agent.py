"""Double DQN agent: target, masked exploration, replay, networks, checkpoints."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from src.scheduler.agent import (
    DoubleDQNAgent,
    ReplayBuffer,
    SlotSharedQNetwork,
    double_dqn_targets,
    masked_argmax,
    vanilla_dqn_targets,
)
from src.scheduler.config import load_scheduler_config
from src.scheduler.env import SchedulerEnv, obs_layout


@pytest.fixture(scope="module")
def cfg(configs_dir):
    return load_scheduler_config(configs_dir / "scheduler_ddqn.yaml", smoke=True)


def test_double_dqn_target_differs_from_vanilla() -> None:
    """Hand-built case where the online and target networks disagree.

    Online prefers action 1 (Q 3), target values it at 4 but values action 0 at 10.
    Double DQN: y = 1 + 0.5 * Q_target(s', argmax Q_online) = 1 + 0.5 * 4 = 3.
    Vanilla DQN: y = 1 + 0.5 * max Q_target = 1 + 0.5 * 10 = 6.
    """
    rewards = torch.tensor([1.0])
    dones = torch.tensor([0.0])
    online = torch.tensor([[1.0, 3.0, 2.0]])
    target = torch.tensor([[10.0, 4.0, 7.0]])
    mask = torch.tensor([[True, True, True]])
    y = double_dqn_targets(rewards, dones, online, target, mask, gamma=0.5)
    y_vanilla = vanilla_dqn_targets(rewards, dones, target, mask, gamma=0.5)
    assert y.item() == pytest.approx(3.0)
    assert y_vanilla.item() == pytest.approx(6.0)
    assert y.item() != y_vanilla.item()


def test_double_dqn_target_respects_mask_and_done() -> None:
    rewards = torch.tensor([1.0, 1.0, 2.0])
    dones = torch.tensor([0.0, 1.0, 0.0])
    online = torch.tensor([[1.0, 3.0, 2.0]] * 3)
    target = torch.tensor([[10.0, 4.0, 7.0]] * 3)
    mask = torch.tensor([[True, False, True], [True, True, True], [False, False, False]])
    y = double_dqn_targets(rewards, dones, online, target, mask, gamma=0.5)
    # row 0: best valid online action is 2 -> 1 + 0.5 * 7; row 1 terminal; row 2 no valid action
    assert y.tolist() == pytest.approx([4.5, 1.0, 2.0])


def test_masked_epsilon_greedy_never_picks_invalid(cfg) -> None:
    agent = DoubleDQNAgent(obs_layout(cfg), cfg.agent, seed=100)
    rng = np.random.default_rng(0)
    n = obs_layout(cfg).n_actions
    for _ in range(300):
        mask = rng.random(n) < 0.2
        mask[int(rng.integers(n))] = True
        q = rng.normal(size=n)
        q[~mask] += 100.0  # invalid actions look best: greedy must still avoid them
        for eps in (0.0, 0.5, 1.0):
            action = agent.select_action(q, mask, eps, rng)
            assert mask[action]
    assert masked_argmax(np.array([5.0, 1.0, 2.0]), np.array([False, True, True])) == 2


def test_epsilon_schedule_is_linear(cfg) -> None:
    agent = DoubleDQNAgent(obs_layout(cfg), cfg.agent, seed=100)
    a = cfg.agent
    assert agent.epsilon(0) == pytest.approx(a.epsilon_start)
    mid = a.epsilon_start + 0.5 * (a.epsilon_end - a.epsilon_start)
    assert agent.epsilon(a.epsilon_decay_steps // 2) == pytest.approx(mid, abs=1e-2)
    assert agent.epsilon(10 * a.epsilon_decay_steps) == pytest.approx(a.epsilon_end)


def test_replay_buffer_wraps_and_samples() -> None:
    buf = ReplayBuffer(capacity=5, obs_dim=3, n_actions=4)
    for i in range(8):
        buf.add(np.full(3, i, np.float32), i % 4, float(i), np.full(3, i + 1, np.float32),
                i == 7, np.array([True, False, True, False]))  # fmt: skip
    assert len(buf) == 5
    assert sorted(buf.rewards.tolist()) == [3.0, 4.0, 5.0, 6.0, 7.0]
    batch = buf.sample(16, np.random.default_rng(1))
    assert batch["obs"].shape == (16, 3) and batch["next_masks"].shape == (16, 4)
    assert np.all(batch["next_obs"][:, 0] == batch["obs"][:, 0] + 1)


def test_slot_shared_network_is_slot_equivariant(cfg) -> None:
    layout = obs_layout(cfg)
    torch.manual_seed(0)
    net = SlotSharedQNetwork(layout, [16])
    obs = torch.randn(1, layout.obs_dim)
    obs[0, layout.global_dim :: layout.slot_dim] = 1.0  # all slots occupied
    slots = obs[0, layout.global_dim :].reshape(layout.num_slots, layout.slot_dim)
    swapped = obs.clone()
    perm = torch.arange(layout.num_slots)
    perm[0], perm[1] = 1, 0
    swapped[0, layout.global_dim :] = slots[perm].reshape(-1)
    q = net(obs)[0]
    q_swapped = net(swapped)[0]
    j = layout.num_slices
    assert torch.allclose(q[:j], q_swapped[j : 2 * j], atol=1e-6)
    base = layout.num_slots * j
    assert torch.allclose(q[base : base + 2], q_swapped[base + 2 : base + 4], atol=1e-6)


def test_update_and_checkpoint_round_trip(cfg, tmp_path) -> None:
    env = SchedulerEnv(cfg, load_profile="medium")
    agent = DoubleDQNAgent(env.layout, cfg.agent, seed=100)
    obs, info = env.reset(seed=100)
    for _ in range(80):
        q = agent.q_values(obs)
        action = agent.select_action(q, info["action_mask"], 0.5)
        nxt, r, term, trunc, info = env.step(action)
        agent.store(obs, action, r, nxt, term, info["action_mask"])
        obs = nxt
        if term or trunc:
            obs, info = env.reset(seed=101)
    stats = agent.update()
    assert np.isfinite(stats.loss) and agent.grad_steps == 1
    path = agent.save(tmp_path / "agent.pt")
    loaded = DoubleDQNAgent.load(path)
    assert np.allclose(agent.q_values(obs), loaded.q_values(obs))
    assert loaded.grad_steps == 1
