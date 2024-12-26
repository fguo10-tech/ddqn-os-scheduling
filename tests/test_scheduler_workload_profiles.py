"""Workload profiles: task classes come from the config, and metrics can be split by class.

The benchmark config keeps its three classes and its results; a profile such as
``configs/scheduler_llm_workload.yaml`` (inference requests and fine-tuning jobs, no language
model anywhere) replaces the classes and inherits everything else. Development seeds (>= 100)
only.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from experiments import build_results
from experiments.run_reference import own_ablations
from experiments.run_scheduler_benchmark import summarise_classes
from src.common.config import ConfigError, load_config
from src.common.labels import REPRODUCED, TARGET_TBD, TBD
from src.scheduler.baselines import SJF, RoundRobin
from src.scheduler.config import (
    apply_ablation,
    load_baselines_config,
    load_scheduler_config,
    priority_weights_for,
    scheduler_config_from_dict,
    task_class_names,
)
from src.scheduler.env import SchedulerEnv, obs_layout, observation_fields
from src.scheduler.guardrails import RULE_STARVATION, GuardrailEngine
from src.scheduler.metrics import CLASS_METRIC_FIELDS, class_metrics, episode_metrics
from src.scheduler.simulator import Decision, SchedulerSim
from src.scheduler.tasks import Task, generate_workload
from src.scheduler.training import (
    CLASS_EPISODE_FIELDS,
    evaluate_agent,
    evaluate_policy,
    make_eval_workloads,
    train_agent,
)

BASE = "scheduler_ddqn.yaml"
LLM = "scheduler_llm_workload.yaml"
LLM_CLASSES = ("inference_request", "finetune_job")
LLM_ABLATION = "starvation_bounded_slice"
LLM_ABLATION_SLICE_MS = 20.0
DEV_SEEDS = range(100, 140)


@pytest.fixture(scope="module")
def base_cfg(configs_dir):
    return load_scheduler_config(configs_dir / BASE)


@pytest.fixture(scope="module")
def llm_cfg(configs_dir):
    return load_scheduler_config(configs_dir / LLM)


def test_benchmark_config_keeps_its_three_classes_in_file_order(base_cfg) -> None:
    assert task_class_names(base_cfg.workload) == ("cpu_bound", "memory_bound", "io_bound")
    names = [name for name, _, _ in observation_fields(base_cfg)]
    assert names[-3:] == ["slot9.type_cpu_bound", "slot9.type_memory_bound", "slot9.type_io_bound"]


def test_one_priority_list_equals_the_same_list_per_class(configs_dir, base_cfg) -> None:
    """Writing the priority weights once or once per class must draw the same workloads."""
    raw = load_config(configs_dir / BASE)
    weights = raw["workload"]["priority_level_weights"]
    raw["workload"]["priority_level_weights"] = {name: list(weights) for name in raw["workload"]["task_types"]}  # fmt: skip
    per_class = scheduler_config_from_dict(raw)
    for load in ("light", "heavy"):
        for seed in (100, 101, 102):
            one = generate_workload(base_cfg.workload, load, seed)
            other = generate_workload(per_class.workload, load, seed)
            assert [t.static_dict() for t in one] == [t.static_dict() for t in other]


def test_llm_profile_replaces_the_classes_and_inherits_everything_else(base_cfg, llm_cfg) -> None:
    assert task_class_names(llm_cfg.workload) == LLM_CLASSES
    for section in ("machine", "metrics", "observation", "actions", "reward", "guardrails",
                    "agent", "training", "evaluation", "seeds"):  # fmt: skip
        assert getattr(llm_cfg, section) == getattr(base_cfg, section), section
    for key in ("n_tasks_min", "n_tasks_max", "min_burst_ms", "slo_slack_ms", "load_profiles"):
        assert getattr(llm_cfg.workload, key) == getattr(base_cfg.workload, key), key
    for name, overrides in base_cfg.ablations.items():
        assert llm_cfg.ablations[name] == overrides, name


def test_llm_profile_adds_one_ablation_that_changes_one_setting(configs_dir, base_cfg) -> None:
    """The post hoc variant bounds the forced dispatch of the starvation override, nothing else."""
    raw = load_config(configs_dir / LLM)
    own = [name for name in raw["ablations"] if name not in base_cfg.ablations]
    assert own == [LLM_ABLATION]
    assert own_ablations(f"configs/{LLM}", f"configs/{BASE}") == own
    assert list(raw["ablations"][LLM_ABLATION]) == ["guardrails.starvation.forced_time_slice_ms"]
    plain = scheduler_config_from_dict(raw)
    variant = scheduler_config_from_dict(apply_ablation(raw, LLM_ABLATION))
    assert plain.guardrails.starvation.forced_time_slice_ms is None
    slice_ms = variant.guardrails.starvation.forced_time_slice_ms
    assert slice_ms == variant.guardrails.slo_fallback.fallback_quantum_ms
    assert slice_ms == load_baselines_config(configs_dir / "scheduler_baselines.yaml").round_robin.quantum_ms  # fmt: skip
    restored = dataclasses.replace(
        variant,
        guardrails=dataclasses.replace(
            variant.guardrails,
            starvation=dataclasses.replace(
                variant.guardrails.starvation, forced_time_slice_ms=None
            ),
        ),
    )
    assert restored == plain
    with pytest.raises(ConfigError, match="unknown ablation"):
        apply_ablation(load_config(configs_dir / BASE), LLM_ABLATION)


def test_bounded_forced_slice_returns_the_processor_after_the_slice(configs_dir) -> None:
    """With the variant, a forced dispatch of a long job ends after the slice, not the burst."""
    raw = load_config(configs_dir / LLM)
    for name in (None, LLM_ABLATION):
        cfg = scheduler_config_from_dict(apply_ablation(raw, name) if name else raw)
        limit = cfg.guardrails.starvation.max_wait_ms
        job = Task(0, 0.0, "finetune_job", (200.0, 50.0), (10.0,), 2048.0, 0, 1e6)
        request = Task(1, 0.0, "inference_request", (10.0,), (), 128.0, 3, 1e6)
        sim = SchedulerSim([job, request], cfg.machine)
        seen = sim.view()
        ready = tuple(
            dataclasses.replace(task, wait_ms=limit) if task.task_id == 0 else task
            for task in seen.ready
        )
        engine = GuardrailEngine(cfg.guardrails)
        result = engine.filter(dataclasses.replace(seen, ready=ready), Decision.dispatch(1, 10.0))
        assert result.overridden and result.rule == RULE_STARVATION
        assert result.decision.task_id == 0
        outcome = sim.execute(result.decision)
        if name is None:
            assert outcome.busy_ms == pytest.approx(200.0), "the whole first burst"
            assert sim.ready_ids == (1,), "the job now waits for its data, not for the processor"
        else:
            assert outcome.busy_ms == pytest.approx(LLM_ABLATION_SLICE_MS)
            assert sim.ready_ids == (1, 0), "the job is back in the queue, behind the request"


def test_llm_profile_changes_only_the_class_one_hot_of_the_observation(base_cfg, llm_cfg) -> None:
    base, llm = obs_layout(base_cfg), obs_layout(llm_cfg)
    assert (llm.global_dim, llm.num_slots, llm.num_slices) == (
        base.global_dim,
        base.num_slots,
        base.num_slices,
    )
    assert llm.slot_dim == base.slot_dim - 3 + len(LLM_CLASSES)
    names = [name for name, _, _ in observation_fields(llm_cfg)]
    assert names[-2:] == ["slot9.type_inference_request", "slot9.type_finetune_job"]
    assert not any("cpu_bound" in name for name in names)


def test_llm_workloads_have_the_shape_the_profile_describes(llm_cfg) -> None:
    work = llm_cfg.workload
    shares, work_shares = [], []
    for seed in DEV_SEEDS:
        tasks = generate_workload(work, "medium", seed)
        jobs = [t for t in tasks if t.task_type == "finetune_job"]
        requests = [t for t in tasks if t.task_type == "inference_request"]
        assert len(jobs) + len(requests) == len(tasks)
        for task in tasks:
            tcfg = work.task_types[task.task_type]
            assert tcfg.memory_min_mb <= task.memory_mb <= tcfg.memory_max_mb
            assert tcfg.io_ops_min <= len(task.io_waits_ms) <= tcfg.io_ops_max
            budget = tcfg.slo_factor * (task.total_cpu_ms + task.total_io_ms) + work.slo_slack_ms
            assert task.deadline_ms == pytest.approx(task.arrival_ms + budget, abs=2e-3)
        assert all(t.priority >= 2 for t in requests), "requests are interactive (levels 2-3)"
        assert all(t.priority <= 1 for t in jobs), "jobs are batch work (levels 0-1)"
        shares.append(len(jobs) / len(tasks))
        total = sum(t.total_cpu_ms for t in tasks)
        work_shares.append(sum(t.total_cpu_ms for t in jobs) / total)
    assert 0.10 < float(np.mean(shares)) < 0.20, "about 15% of the tasks are fine-tuning jobs"
    assert float(np.mean(work_shares)) > 0.6, "which carry most of the compute demand"


@pytest.mark.parametrize(
    ("patch", "match"),
    [
        ({"priority_level_weights": {"inference_request": [0, 0, 1, 1]}}, "exactly the task classes"),
        ({"priority_level_weights": {"inference_request": [0, 1], "finetune_job": [1, 0]}}, "num_priority_levels"),
        ({"priority_level_weights": [0, 0, 0, 0]}, "positive sum"),
        ({"priority_level_weights": [1, 1, 1, -1]}, "non-negative"),
    ],
)  # fmt: skip
def test_bad_priority_weights_are_rejected(configs_dir, patch, match) -> None:
    raw = load_config(configs_dir / LLM)
    raw["workload"].update(patch)
    with pytest.raises(ConfigError, match=match):
        scheduler_config_from_dict(raw)


def test_bad_class_names_and_empty_class_sets_are_rejected(configs_dir) -> None:
    raw = load_config(configs_dir / LLM)
    classes = raw["workload"]["task_types"]
    raw["workload"]["task_types"] = {"Inference-Request": classes["inference_request"]}
    raw["workload"]["priority_level_weights"] = [1, 1, 1, 1]
    with pytest.raises(ConfigError, match="task-class name"):
        scheduler_config_from_dict(raw)
    raw["workload"]["task_types"] = {}
    with pytest.raises(ConfigError, match="at least one task class"):
        scheduler_config_from_dict(raw)


def test_priority_weights_lookup(base_cfg, llm_cfg) -> None:
    assert priority_weights_for(base_cfg.workload, "io_bound") == [0.25, 0.25, 0.25, 0.25]
    assert priority_weights_for(llm_cfg.workload, "inference_request")[:2] == [0.0, 0.0]
    assert priority_weights_for(llm_cfg.workload, "finetune_job")[2:] == [0.0, 0.0]


def _assert_class_view_matches_episode_view(sim: SchedulerSim, threshold: float) -> None:
    whole = episode_metrics(sim, threshold)
    parts = class_metrics(sim, threshold)
    counts = {name: values["n_tasks"] for name, values in parts.items()}
    assert sum(counts.values()) == whole["n_tasks"]
    assert sum(values["n_completed"] for values in parts.values()) == whole["n_completed"]
    assert sum(values["starvation_count"] for values in parts.values()) == whole["starvation_count"]
    assert max(values["max_wait_ms"] for values in parts.values()) == whole["max_wait_ms"]
    for key in ("avg_turnaround_ms", "avg_response_ms", "avg_waiting_ms", "slo_violation_rate"):
        weighted = sum(parts[name][key] * counts[name] for name in parts) / whole["n_tasks"]
        assert weighted == pytest.approx(whole[key], rel=1e-12, abs=1e-12), key
    for values in parts.values():
        assert tuple(values) == CLASS_METRIC_FIELDS


@pytest.mark.parametrize("config_name", [BASE, LLM])
def test_class_metrics_add_up_to_the_episode_metrics(configs_dir, config_name) -> None:
    cfg = load_scheduler_config(configs_dir / config_name)
    threshold = cfg.metrics.starvation_threshold_ms
    for seed, policy in ((100, SJF()), (101, RoundRobin(20.0))):
        sim = SchedulerSim(generate_workload(cfg.workload, "heavy", seed), cfg.machine)
        sim.run(policy)
        assert sim.done
        _assert_class_view_matches_episode_view(sim, threshold)
        assert set(class_metrics(sim, threshold)) <= set(task_class_names(cfg.workload))


def test_class_metrics_follow_the_truncation_rules(llm_cfg) -> None:
    """Unfinished tasks are charged up to the current time in both views."""
    sim = SchedulerSim(generate_workload(llm_cfg.workload, "heavy", 103), llm_cfg.machine)
    sim.run(RoundRobin(20.0), max_decisions=25)
    assert not sim.done
    _assert_class_view_matches_episode_view(sim, llm_cfg.metrics.starvation_threshold_ms)


def test_llm_profile_runs_through_the_environment(llm_cfg) -> None:
    env = SchedulerEnv(llm_cfg, load_profile="heavy")
    obs, info = env.reset(seed=104)
    assert len(env.OBSERVATION_FIELDS) == obs.shape[0] == env.observation_space.shape[0]
    rng = np.random.default_rng(5)
    done = False
    steps = 0
    while not done:
        assert env.observation_space.contains(obs)
        action = int(rng.choice(np.flatnonzero(info["action_mask"])))
        obs, _, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        steps += 1
    assert terminated and steps > 40


def test_evaluation_can_collect_per_class_rows(configs_dir) -> None:
    cfg = load_scheduler_config(configs_dir / LLM, smoke=True)
    workloads = make_eval_workloads(cfg, 100)
    collected: list[dict] = []
    rows = evaluate_policy(cfg, SJF(), workloads, 100, per_class=collected)
    plain = evaluate_policy(cfg, SJF(), workloads, 100)
    assert rows == plain, "collecting per-class rows must not change the episode rows"
    assert collected and all(tuple(row) == CLASS_EPISODE_FIELDS for row in collected)
    assert {row["task_class"] for row in collected} <= set(LLM_CLASSES)
    assert {row["method"] for row in collected} == {"sjf"}
    by_workload = {(r["load_profile"], r["episode"]): 0 for r in collected}
    for row in collected:
        by_workload[(row["load_profile"], row["episode"])] += row["n_tasks"]
    for row in rows:
        assert by_workload[(row["load_profile"], row["episode"])] == row["n_tasks"]
    summary = summarise_classes(collected)
    assert {r["load_profile"] for r in summary} == {"light", "medium", "heavy", "all"}
    assert all("avg_turnaround_ms_mean" in r and r["n_seeds"] == 1 for r in summary)


@pytest.mark.slow
def test_an_agent_trains_and_evaluates_on_the_llm_profile(configs_dir) -> None:
    cfg = load_scheduler_config(configs_dir / LLM, smoke=True)
    result = train_agent(cfg, 100)
    assert not result.diverged and result.log
    workloads = make_eval_workloads(cfg, 100)
    collected: list[dict] = []
    rows = evaluate_agent(cfg, result.agent, workloads, 100, "ddqn", True, collected)
    again = evaluate_agent(cfg, result.agent, workloads, 100, "ddqn", True)
    assert rows == again
    assert all(row["n_completed"] == row["n_tasks"] for row in rows)
    assert {row["task_class"] for row in collected} <= set(LLM_CLASSES)


def test_tables_of_a_run_that_does_not_exist_are_tbd_not_numbers(tmp_path: Path) -> None:
    """The table builder never fills a result cell without a result file."""
    cfg = load_config(build_results.DEFAULT_CONFIG)
    paths = build_results.Paths(
        reference=tmp_path / "reference",
        generated=tmp_path / "generated",
        before_after=tmp_path / "before_after",
        templates=tmp_path / "templates",
    )
    blocks = build_results.build_llm_workload(cfg, paths, figures=False)
    for block_id in ("llm_before_after_full", "llm_before_after_summary",
                     "llm_before_after_compact", "llm_before_after_by_load", "llm_by_class",
                     "llm_all_methods", "llm_findings", "llm_guardrails",
                     "llm_tail_analysis"):  # fmt: skip
        text = blocks[block_id]
        assert TBD in text and TARGET_TBD in text, block_id
        assert REPRODUCED not in text, f"{block_id} claims a reproduced value without a run"
    assert "no language model is run" in blocks["llm_before_after_full"]
    # The profile table is read from the config and the generator, not from a run.
    assert "Inference requests" in blocks["llm_workload_profile"]


def test_llm_study_reuses_the_metric_definitions_of_the_benchmark() -> None:
    cfg = load_config(build_results.DEFAULT_CONFIG)
    llm = cfg["scheduling_llm"]
    for key in ("metrics", "method_labels", "after_method", "before_methods",
                "reference_methods", "load_profile", "per_load_profiles"):  # fmt: skip
        assert key not in llm, f"scheduling_llm must inherit {key} from the scheduling section"
    known = {entry["key"] for entry in cfg["scheduling"]["metrics"]}
    assert {entry["key"] for entry in llm["class_metrics"]} <= known
    profile = load_scheduler_config(build_results.REPO_ROOT / llm["workload_config"])
    assert tuple(llm["class_labels"]) == task_class_names(profile.workload)
    assert dataclasses.is_dataclass(profile)
