"""Scheduler configs: strict loading, ablations, and a comment on every YAML key."""

from __future__ import annotations

import re

import pytest

from src.common.config import ConfigError, load_config
from src.scheduler.config import (
    apply_ablation,
    load_baselines_config,
    load_scheduler_config,
    scheduler_config_from_dict,
)

REQUIRED_ABLATIONS = {
    "reward_paper_sign_as_printed",
    "gamma_low",
    "gamma_high",
    "lr_low",
    "lr_high",
    "network_mlp",
    "no_guardrails_in_training",
}


def test_both_configs_load(configs_dir) -> None:
    cfg = load_scheduler_config(configs_dir / "scheduler_ddqn.yaml")
    smoke = load_scheduler_config(configs_dir / "scheduler_ddqn.yaml", smoke=True)
    base = load_baselines_config(configs_dir / "scheduler_baselines.yaml")
    assert cfg.agent.network.type in ("mlp", "slot_shared")
    assert all(seed >= 100 for seed in smoke.seeds)  # smoke never touches reporting seeds
    assert set(base.methods) == {"fcfs", "sjf", "round_robin", "priority"}
    assert cfg.actions.time_slices_ms[-1] is None


def test_typo_key_fails(configs_dir) -> None:
    with pytest.raises(ConfigError, match="learnin_rate"):
        load_scheduler_config(configs_dir / "scheduler_ddqn.yaml", ["agent.learnin_rate=0.1"])
    with pytest.raises(ConfigError, match="quantum"):
        load_baselines_config(configs_dir / "scheduler_baselines.yaml",
                              ["round_robin.quantum=5"])  # fmt: skip


def test_missing_key_and_bad_value_fail(configs_dir) -> None:
    raw = load_config(configs_dir / "scheduler_ddqn.yaml")
    del raw["agent"]["gamma"]
    with pytest.raises(ConfigError, match="gamma"):
        scheduler_config_from_dict(raw)
    with pytest.raises(ConfigError):
        load_scheduler_config(configs_dir / "scheduler_ddqn.yaml", ["agent.network.type=cnn"])
    with pytest.raises(ConfigError):
        load_scheduler_config(
            configs_dir / "scheduler_ddqn.yaml",
            ["workload.task_types.memory_bound.memory_max_mb=99999"],
        )


def test_every_ablation_is_valid(configs_dir) -> None:
    raw = load_config(configs_dir / "scheduler_ddqn.yaml")
    names = set(raw["ablations"])
    assert REQUIRED_ABLATIONS <= names
    assert (
        sum(1 for n in names if n.startswith("reward_") and n != "reward_paper_sign_as_printed")
        >= 2
    )
    for name in names:
        cfg = scheduler_config_from_dict(apply_ablation(raw, name))
        assert cfg is not None
    assert (
        scheduler_config_from_dict(apply_ablation(raw, "network_mlp")).agent.network.type == "mlp"
    )
    with pytest.raises(ConfigError):
        apply_ablation(raw, "does_not_exist")


@pytest.mark.parametrize(
    "name", ["scheduler_ddqn.yaml", "scheduler_baselines.yaml", "scheduler_llm_workload.yaml"]
)
def test_every_yaml_key_is_commented(configs_dir, name) -> None:
    lines = (configs_dir / name).read_text(encoding="utf-8").splitlines()
    key = re.compile(r"^\s*[A-Za-z_][\w.]*\s*:")
    for i, line in enumerate(lines):
        if not key.match(line):
            continue
        previous = next((p for p in reversed(lines[:i]) if p.strip()), "")
        assert previous.strip().startswith("#") or "#" in line, f"{name}:{i + 1}: {line}"


@pytest.mark.parametrize("name", ["scheduler_ddqn.yaml", "scheduler_llm_workload.yaml"])
def test_leaf_comments_carry_provenance_tag(configs_dir, name) -> None:
    text = (configs_dir / name).read_text(encoding="utf-8")
    lines = text.splitlines()
    leaf = re.compile(r"^\s*[A-Za-z_][\w.]*\s*:\s*\S")
    for i, line in enumerate(lines):
        if leaf.match(line) and not line.strip().startswith("#"):
            comment = next(p for p in reversed(lines[:i]) if p.strip())
            assert (
                "[Assumption — not in paper]" in comment or "[Paper-reported]" in comment
            ), f"line {i + 1}: {line}"
