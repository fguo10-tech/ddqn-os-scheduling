"""Guardrails that filter the agent's decisions inside the environment step.

Three override rules, each with its own enable flag, plus a master switch
``guardrails.enabled`` that turns all three overrides off (and nothing else):

1. **Starvation prevention.** (a) *Aging*: effective priority rises by one level per
   ``aging.interval_ms`` of continuous waiting (up to ``aging.max_boost``); it changes the
   order of the agent's visible window. Aging is part of the observation encoding, applied
   in :mod:`src.scheduler.env` and controlled only by ``aging.enabled`` — the master switch
   below does not touch it. (b) *Max-wait override*: if any READY task has waited continuously for at least
   ``starvation.max_wait_ms``, the proposed decision is replaced by a dispatch of the
   longest-waiting such task (ties by ``ready_seq``) for ``starvation.forced_time_slice_ms``.
2. **SLO fallback to Round Robin.** The engine keeps the last ``window_completions``
   completions; when at least ``violation_threshold`` of them missed their deadline it
   switches to Round Robin (quantum ``fallback_quantum_ms``) for ``fallback_duration_ms`` of
   simulated time, then hands control back and clears the window so it cannot re-trigger
   instantly. Completions during the fallback period are not recorded.
3. **Q-divergence / NaN fallback.** The agent reports its Q-values before acting; if any
   output is NaN or infinite, or ``max |Q|`` over the *valid* actions exceeds
   ``q_abs_limit``, the engine latches into the configured
   fallback baseline. A latched engine stays latched until ``reset(clear_latch=True)``.
   (:class:`~src.scheduler.env.SchedulerEnv` clears the latch at every episode reset, so in
   the benchmark a latch lasts for the rest of the episode; the plugin keeps it across
   ``reset()`` until an operator clears it.)

Precedence when several rules apply: the Q-divergence latch replaces the agent with its
fallback baseline; an active SLO fallback replaces that with Round Robin; the starvation
override is applied last and therefore wins. ``rule`` in the result names the rule that
produced the executed decision.

All settings are ``[Assumption — not in paper]``.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import Sequence

import numpy as np

from .baselines import RoundRobin, make_fallback_policy
from .config import GuardrailsConfig
from .simulator import Decision, SimView

RULE_STARVATION = "starvation"
RULE_SLO_FALLBACK = "slo_fallback"
RULE_Q_DIVERGENCE = "q_divergence"
GUARDRAIL_RULES = (RULE_STARVATION, RULE_SLO_FALLBACK, RULE_Q_DIVERGENCE)

GUARDRAIL_COUNTER_FIELDS = (
    "guardrail_starvation_triggers",
    "guardrail_slo_fallback_activations",
    "guardrail_slo_fallback_decisions",
    "guardrail_q_divergence_latches",
    "guardrail_q_divergence_decisions",
    "guardrail_overrides",
)
"""Counters reported per episode (raw CSV columns)."""


@dataclasses.dataclass(frozen=True)
class GuardrailResult:
    """What the engine did with one proposed decision."""

    decision: Decision
    proposed: Decision
    rule: str | None
    rules_fired: tuple[str, ...]
    overridden: bool


class GuardrailEngine:
    """Stateful filter between the agent and the simulator (see module docstring)."""

    def __init__(self, cfg: GuardrailsConfig) -> None:
        self.cfg = cfg
        slo = cfg.slo_fallback
        self._rr = RoundRobin(slo.fallback_quantum_ms)
        qd = cfg.q_divergence
        self._fallback = make_fallback_policy(qd.fallback_policy, qd.fallback_quantum_ms)
        self._window: deque[bool] = deque(maxlen=slo.window_completions)
        self._fallback_until: float | None = None
        self._latched = False
        self._pending_q: np.ndarray | None = None
        self.counts: dict[str, int] = {}
        self.last_q_problem: str | None = None
        self.reset(clear_latch=True)

    # ------------------------------------------------------------------ state
    def reset(self, clear_latch: bool = True) -> None:
        """Start a new episode: clear the SLO window, the fallback timer and the counters.

        The Q-divergence latch survives unless ``clear_latch`` is true.
        """
        self._window.clear()
        self._fallback_until = None
        self._pending_q = None
        if clear_latch:
            self._latched = False
            self.last_q_problem = None
        self.counts = {name: 0 for name in GUARDRAIL_COUNTER_FIELDS}

    @property
    def latched(self) -> bool:
        """True while the Q-divergence latch is engaged."""
        return self._latched

    def slo_fallback_active(self, now_ms: float) -> bool:
        """True while the SLO fallback period covers ``now_ms``."""
        return self._fallback_until is not None and now_ms < self._fallback_until

    @property
    def active(self) -> bool:
        """Master switch."""
        return self.cfg.enabled

    # ------------------------------------------------------------------ inputs
    def report_q_values(
        self, q_values: Sequence[float] | np.ndarray, mask: np.ndarray | None = None
    ) -> bool:
        """Check the agent's Q-values before it acts; latch on NaN/inf/huge values.

        The NaN / infinity test covers every output. The magnitude test (``q_abs_limit``)
        covers only the valid actions given by ``mask`` (all actions if ``mask`` is None):
        outputs for empty slots are never trained and may be arbitrary.
        Returns True if this call engaged the latch.
        """
        q = np.asarray(q_values, dtype=np.float64)
        self._pending_q = q
        qd = self.cfg.q_divergence
        if not (self.cfg.enabled and qd.enabled) or self._latched:
            return False
        problem = None
        valid = q if mask is None else q[np.asarray(mask, dtype=bool)]
        if not np.all(np.isfinite(q)):
            problem = "non-finite Q-value"
        elif valid.size and float(np.max(np.abs(valid))) > qd.q_abs_limit:
            problem = f"max |Q| over valid actions = {float(np.max(np.abs(valid))):.4g} > "
            problem += f"{qd.q_abs_limit:.4g}"
        if problem is None:
            return False
        self._latched = True
        self.last_q_problem = problem
        self.counts["guardrail_q_divergence_latches"] += 1
        return True

    def record_completions(self, now_ms: float, late_flags: Sequence[bool]) -> None:
        """Record completed tasks (True = finished after its deadline); may start a fallback."""
        slo = self.cfg.slo_fallback
        if not (self.cfg.enabled and slo.enabled):
            return
        self._expire_fallback(now_ms)
        if self.slo_fallback_active(now_ms):
            return
        for late in late_flags:
            self._window.append(bool(late))
            if sum(self._window) >= slo.violation_threshold:
                self._fallback_until = now_ms + slo.fallback_duration_ms
                self.counts["guardrail_slo_fallback_activations"] += 1
                self._window.clear()
                return

    def _expire_fallback(self, now_ms: float) -> None:
        """End an expired fallback period and clear the window, exactly once.

        Called both before recording completions and before filtering, so a completion
        recorded just after the period ends is kept rather than wiped by the next filter.
        """
        if self._fallback_until is not None and now_ms >= self._fallback_until:
            self._fallback_until = None
            self._window.clear()

    # ------------------------------------------------------------------ filter
    def filter(self, view: SimView, proposed: Decision) -> GuardrailResult:
        """Return the decision to execute in place of ``proposed`` (possibly the same one)."""
        self._pending_q = None
        if not self.cfg.enabled:
            return GuardrailResult(proposed, proposed, None, (), False)
        now = view.now_ms
        decision = proposed
        rule: str | None = None
        fired: list[str] = []

        if self._latched and self.cfg.q_divergence.enabled:
            decision = self._fallback.decide(view)
            rule = RULE_Q_DIVERGENCE
            fired.append(RULE_Q_DIVERGENCE)
            self.counts["guardrail_q_divergence_decisions"] += 1

        self._expire_fallback(now)
        if self.slo_fallback_active(now) and self.cfg.slo_fallback.enabled:
            decision = self._rr.decide(view)
            rule = RULE_SLO_FALLBACK
            fired.append(RULE_SLO_FALLBACK)
            self.counts["guardrail_slo_fallback_decisions"] += 1

        starv = self.cfg.starvation
        if starv.enabled:
            starving = [t for t in view.ready if t.wait_ms >= starv.max_wait_ms]
            if starving:
                victim = min(starving, key=lambda t: (-t.wait_ms, t.ready_seq))
                decision = Decision.dispatch(victim.task_id, starv.forced_time_slice_ms)
                rule = RULE_STARVATION
                fired.append(RULE_STARVATION)
                self.counts["guardrail_starvation_triggers"] += 1

        overridden = decision != proposed
        if overridden:
            self.counts["guardrail_overrides"] += 1
        return GuardrailResult(decision, proposed, rule, tuple(fired), overridden)


def q_values_ok(q_values: np.ndarray, limit: float) -> bool:
    """True when every Q-value is finite and ``max |Q| <= limit``."""
    q = np.asarray(q_values, dtype=np.float64)
    return bool(np.all(np.isfinite(q)) and (q.size == 0 or float(np.max(np.abs(q))) <= limit))


def decided_by(rule: str | None) -> str:
    """Plugin label for the rule that produced a decision."""
    if rule is None:
        return "agent"
    if rule == RULE_Q_DIVERGENCE:
        return "fallback:q_divergence"
    return f"guardrail:{rule}"
