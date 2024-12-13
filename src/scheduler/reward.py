"""Per-step reward: time penalties, a completion bonus and a utilisation bonus.

With ``τ = reward.time_scale_ms`` the reward of one executed step is::

    r = − w_wait · wait_ms/τ − w_turnaround · in_system_ms/τ − w_response · response_wait_ms/τ
        − w_slo_violation · (#deadline misses) + w_completion · (#completions)
        + w_utilisation · busy_ms/duration_ms

* ``w_wait`` penalises the summed READY waiting time of the step;
* ``w_turnaround`` penalises the summed time in system of the step;
* ``w_response`` penalises the waiting of tasks that have never been dispatched;
* ``w_slo_violation`` penalises each task whose deadline passes unfinished during the step;
* ``w_completion`` rewards each task completed during the step;
* ``w_utilisation`` rewards the busy fraction of the step.

Every time term is a **penalty**. The step quantities are integrals over the step (see
:class:`~src.scheduler.simulator.StepOutcome`): summed over an episode, ``in_system_ms``
equals the sum of all turnaround times, so ``w_turnaround`` targets the task completion
time directly.

``reward.paper_sign_as_printed: true`` selects an alternative sign convention for the
response-time term (response time is added instead of subtracted, the form printed in the
source paper), kept as an ablation: the reward is then exactly
``w_utilisation · U − w_turnaround · T + w_response · R`` with ``U = busy_ms/duration_ms``,
``T = in_system_ms/τ`` and ``R = response_wait_ms/τ``.
"""

from __future__ import annotations

from .config import RewardConfig
from .simulator import StepOutcome


def compute_reward(outcome: StepOutcome, cfg: RewardConfig) -> float:
    """Reward of one executed step (see the module docstring for both sign conventions)."""
    tau = cfg.time_scale_ms
    utilisation = outcome.busy_ms / outcome.duration_ms if outcome.duration_ms > 0 else 0.0
    if cfg.paper_sign_as_printed:
        return float(
            cfg.w_utilisation * utilisation
            - cfg.w_turnaround * outcome.in_system_ms / tau
            + cfg.w_response * outcome.response_wait_ms / tau
        )
    return float(
        -cfg.w_wait * outcome.wait_ms / tau
        - cfg.w_turnaround * outcome.in_system_ms / tau
        - cfg.w_response * outcome.response_wait_ms / tau
        - cfg.w_slo_violation * len(outcome.deadline_misses)
        + cfg.w_completion * len(outcome.completed)
        + cfg.w_utilisation * utilisation
    )
