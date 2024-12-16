"""Double DQN agent: Q-networks, uniform replay buffer, masked ε-greedy, Double DQN target.

The architecture, the optimiser and every hyperparameter come from
``configs/scheduler_ddqn.yaml`` and are ``[Assumption — not in paper]``.

Double DQN target
-----------------
The target is the standard Double DQN target (van Hasselt et al., 2016)::

    a* = argmax_{a valid in s'} Q_online(s', a)
    y  = r + γ · (1 − done) · Q_target(s', a*)

The online network selects the next action among the actions valid in ``s'``; the target
network evaluates it. Double DQN uses two networks because taking the maximum of the same
noisy estimates that are used to choose the action overestimates Q-values; separating
selection from evaluation reduces that bias. ``done`` is true only for termination (all
tasks finished); truncated steps bootstrap normally.

Exploration
-----------
ε decays **linearly** from ``epsilon_start`` to ``epsilon_end`` over the first
``epsilon_decay_steps`` environment steps and stays at ``epsilon_end`` afterwards; random
actions are drawn uniformly from the *valid* actions only.
"""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from src.common.config import from_dict, to_dict
from src.common.seeding import derive_seed

from .config import AgentConfig, NetworkConfig
from .env import ObsLayout


def _mlp(in_dim: int, hidden: list[int], out_dim: int) -> nn.Sequential:
    layers: list[nn.Module] = []
    width = in_dim
    for size in hidden:
        layers.extend([nn.Linear(width, size), nn.ReLU()])
        width = size
    layers.append(nn.Linear(width, out_dim))
    return nn.Sequential(*layers)


class MLPQNetwork(nn.Module):
    """Plain MLP from the flat observation to one Q-value per action."""

    def __init__(self, layout: ObsLayout, hidden_sizes: list[int]) -> None:
        super().__init__()
        self.layout = layout
        self.net = _mlp(layout.obs_dim, hidden_sizes, layout.n_actions)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """``(B, obs_dim) -> (B, n_actions)``."""
        return self.net(obs)


class SlotSharedQNetwork(nn.Module):
    """One small network scores every slot from (global features, that slot's features,
    mean of the occupied slots' features).

    It outputs ``J + 2`` values per slot (one per time slice, then raise / lower priority)
    and rearranges them into the flat action layout of
    :class:`~src.scheduler.env.SchedulerEnv`. Because the weights are shared across slots,
    a rule such as "prefer the shortest burst" is learned once, not once per slot.
    """

    def __init__(self, layout: ObsLayout, hidden_sizes: list[int]) -> None:
        super().__init__()
        self.layout = layout
        in_dim = layout.global_dim + 2 * layout.slot_dim
        self.net = _mlp(in_dim, hidden_sizes, layout.num_slices + 2)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """``(B, obs_dim) -> (B, n_actions)``."""
        lay = self.layout
        batch = obs.shape[0]
        glob = obs[:, : lay.global_dim]
        slots = obs[:, lay.global_dim :].reshape(batch, lay.num_slots, lay.slot_dim)
        occupied = slots[:, :, :1]
        pooled = (slots * occupied).sum(dim=1) / occupied.sum(dim=1).clamp(min=1.0)
        features = torch.cat(
            [
                glob.unsqueeze(1).expand(batch, lay.num_slots, lay.global_dim),
                slots,
                pooled.unsqueeze(1).expand(batch, lay.num_slots, lay.slot_dim),
            ],
            dim=-1,
        )
        out = self.net(features)
        dispatch = out[:, :, : lay.num_slices].reshape(batch, lay.num_slots * lay.num_slices)
        priority = out[:, :, lay.num_slices :].reshape(batch, lay.num_slots * 2)
        return torch.cat([dispatch, priority], dim=1)


def build_q_network(cfg: NetworkConfig, layout: ObsLayout) -> nn.Module:
    """Q-network of type ``cfg.type`` (``mlp`` or ``slot_shared``)."""
    if cfg.type == "mlp":
        return MLPQNetwork(layout, list(cfg.hidden_sizes))
    if cfg.type == "slot_shared":
        return SlotSharedQNetwork(layout, list(cfg.hidden_sizes))
    raise ValueError(f"unknown network type {cfg.type!r}")


class ReplayBuffer:
    """Uniform replay of (obs, action, reward, next obs, done, next-state mask)."""

    def __init__(self, capacity: int, obs_dim: int, n_actions: int) -> None:
        self.capacity = int(capacity)
        self.obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.actions = np.zeros(capacity, dtype=np.int64)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=np.float32)
        self.next_masks = np.zeros((capacity, n_actions), dtype=bool)
        self.size = 0
        self._pos = 0

    def __len__(self) -> int:
        return self.size

    def add(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        done: bool,
        next_mask: np.ndarray,
    ) -> None:
        """Store one transition (oldest is overwritten when full)."""
        i = self._pos
        self.obs[i] = obs
        self.actions[i] = int(action)
        self.rewards[i] = float(reward)
        self.next_obs[i] = next_obs
        self.dones[i] = 1.0 if done else 0.0
        self.next_masks[i] = next_mask
        self._pos = (self._pos + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
        """Uniform sample with replacement."""
        if self.size == 0:
            raise ValueError("cannot sample from an empty buffer")
        idx = rng.integers(0, self.size, size=batch_size)
        return {
            "obs": self.obs[idx],
            "actions": self.actions[idx],
            "rewards": self.rewards[idx],
            "next_obs": self.next_obs[idx],
            "dones": self.dones[idx],
            "next_masks": self.next_masks[idx],
        }


def double_dqn_targets(
    rewards: torch.Tensor,
    dones: torch.Tensor,
    q_online_next: torch.Tensor,
    q_target_next: torch.Tensor,
    next_masks: torch.Tensor,
    gamma: float,
) -> torch.Tensor:
    """``y = r + γ (1 − done) Q_target(s', argmax_{valid a} Q_online(s', a))``.

    A next state with no valid action (terminal) contributes 0.
    """
    masked = q_online_next.masked_fill(~next_masks, float("-inf"))
    best = masked.argmax(dim=1, keepdim=True)
    evaluated = q_target_next.gather(1, best).squeeze(1)
    evaluated = torch.where(next_masks.any(dim=1), evaluated, torch.zeros_like(evaluated))
    return rewards + gamma * (1.0 - dones) * evaluated


def vanilla_dqn_targets(
    rewards: torch.Tensor,
    dones: torch.Tensor,
    q_target_next: torch.Tensor,
    next_masks: torch.Tensor,
    gamma: float,
) -> torch.Tensor:
    """Vanilla DQN target ``r + γ (1 − done) max_{valid a} Q_target(s', a)`` (for comparison)."""
    masked = q_target_next.masked_fill(~next_masks, float("-inf"))
    best = masked.max(dim=1).values
    best = torch.where(next_masks.any(dim=1), best, torch.zeros_like(best))
    return rewards + gamma * (1.0 - dones) * best


def masked_argmax(q_values: np.ndarray, mask: np.ndarray) -> int:
    """Index of the largest Q-value among valid actions (first one on ties)."""
    if not np.any(mask):
        raise ValueError("no valid action")
    masked = np.where(mask, q_values, -np.inf)
    return int(np.argmax(masked))


@dataclasses.dataclass
class UpdateStats:
    """Result of one gradient step."""

    loss: float
    mean_abs_q: float


class DoubleDQNAgent:
    """Double DQN with hard target updates, masked ε-greedy and gradient-norm clipping."""

    def __init__(self, layout: ObsLayout, cfg: AgentConfig, seed: int) -> None:
        self.layout = layout
        self.cfg = cfg
        self.seed = int(seed)
        torch.manual_seed(derive_seed(seed, "agent_init"))
        self.online = build_q_network(cfg.network, layout)
        self.target = copy.deepcopy(self.online)
        self.target.eval()
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=cfg.learning_rate)
        self.replay = ReplayBuffer(cfg.replay_capacity, layout.obs_dim, layout.n_actions)
        self.explore_rng = np.random.default_rng(derive_seed(seed, "explore"))
        self.sample_rng = np.random.default_rng(derive_seed(seed, "replay"))
        self.env_steps = 0
        self.grad_steps = 0

    # ------------------------------------------------------------------ acting
    def q_values(self, obs: np.ndarray) -> np.ndarray:
        """Online-network Q-values for one observation."""
        with torch.no_grad():
            tensor = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            return self.online(tensor).squeeze(0).numpy().astype(np.float64)

    def epsilon(self, step: int | None = None) -> float:
        """Linear schedule (see module docstring)."""
        step = self.env_steps if step is None else step
        cfg = self.cfg
        if cfg.epsilon_decay_steps <= 0:
            return cfg.epsilon_end
        frac = min(1.0, step / cfg.epsilon_decay_steps)
        return cfg.epsilon_start + frac * (cfg.epsilon_end - cfg.epsilon_start)

    def select_action(
        self,
        q_values: np.ndarray,
        mask: np.ndarray,
        epsilon: float,
        rng: np.random.Generator | None = None,
    ) -> int:
        """ε-greedy over valid actions only."""
        rng = self.explore_rng if rng is None else rng
        if epsilon > 0 and rng.random() < epsilon:
            return int(rng.choice(np.flatnonzero(mask)))
        return masked_argmax(q_values, mask)

    # ------------------------------------------------------------------ learning
    def store(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        done: bool,
        next_mask: np.ndarray,
    ) -> None:
        """Add a transition to the replay buffer."""
        self.replay.add(obs, action, reward, next_obs, done, next_mask)

    def update(self) -> UpdateStats:
        """One gradient step on a uniform minibatch; hard target sync every
        ``target_update_interval`` gradient steps."""
        batch = self.replay.sample(self.cfg.batch_size, self.sample_rng)
        obs = torch.as_tensor(batch["obs"])
        actions = torch.as_tensor(batch["actions"])
        rewards = torch.as_tensor(batch["rewards"])
        next_obs = torch.as_tensor(batch["next_obs"])
        dones = torch.as_tensor(batch["dones"])
        next_masks = torch.as_tensor(batch["next_masks"])
        q_all = self.online(obs)
        q_taken = q_all.gather(1, actions.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            targets = double_dqn_targets(
                rewards, dones, self.online(next_obs), self.target(next_obs), next_masks,
                self.cfg.gamma,
            )  # fmt: skip
        if self.cfg.loss == "huber":
            loss = nn.functional.smooth_l1_loss(q_taken, targets)
        else:
            loss = nn.functional.mse_loss(q_taken, targets)
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), self.cfg.grad_clip_norm)
        self.optimizer.step()
        self.grad_steps += 1
        if self.grad_steps % self.cfg.target_update_interval == 0:
            self.sync_target()
        return UpdateStats(float(loss.item()), float(q_taken.detach().abs().mean().item()))

    def sync_target(self) -> None:
        """Copy online weights into the target network."""
        self.target.load_state_dict(self.online.state_dict())

    # ------------------------------------------------------------------ persistence
    def weights(self) -> dict[str, torch.Tensor]:
        """Deep copy of the online weights."""
        return {k: v.detach().clone() for k, v in self.online.state_dict().items()}

    def load_weights(self, weights: dict[str, torch.Tensor]) -> None:
        """Load weights into both networks."""
        self.online.load_state_dict(weights)
        self.target.load_state_dict(weights)

    def save(self, path: str | Path) -> Path:
        """Write a checkpoint (weights, layout, agent config, counters)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "online": self.online.state_dict(),
                "target": self.target.state_dict(),
                "layout": dataclasses.asdict(self.layout),
                "agent_config": to_dict(self.cfg),
                "seed": self.seed,
                "env_steps": self.env_steps,
                "grad_steps": self.grad_steps,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> DoubleDQNAgent:
        """Rebuild an agent from :meth:`save` output (replay buffer is not saved)."""
        payload: dict[str, Any] = torch.load(Path(path), map_location="cpu", weights_only=True)
        layout = ObsLayout(**payload["layout"])
        cfg = from_dict(AgentConfig, payload["agent_config"])
        agent = cls(layout, cfg, int(payload["seed"]))
        agent.online.load_state_dict(payload["online"])
        agent.target.load_state_dict(payload["target"])
        agent.env_steps = int(payload["env_steps"])
        agent.grad_steps = int(payload["grad_steps"])
        return agent
