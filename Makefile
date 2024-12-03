# ddqn-os-scheduling — common tasks. Run from the repository root.
#
#   make install     editable install with every optional extra
#   make test        full test suite (no network, no dataset)
#   make smoke       tiny end-to-end run of the benchmark
#   make scheduler   the benchmark (four baselines + Double DQN, 5 seeds)
#   make scheduler-llm  the same benchmark on the LLM-style workload profile
#   make results     rebuild every table and chart from the reference run and sync the docs
#
# Outputs of your own runs go to experiments/results/runs/ (git-ignored).
# experiments/results/reference/ holds the run behind every [Reproduced] number in the docs;
# only `make reference` re-creates its raw results (`make results` rebuilds the tables and
# charts derived from them, under reference/generated and reference/before_after).

PYTHON ?= python
WORKERS ?= 4
RUNS := experiments/results/runs
REFERENCE := experiments/results/reference
CODE := src tests experiments examples data

.DEFAULT_GOAL := help
.PHONY: help install lint format test test-fast smoke smoke-llm scheduler scheduler-llm \
        reference results docs-check notebooks clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'

install: ## Editable install with every optional extra (CPU is enough)
	$(PYTHON) -m pip install -e ".[all]"

lint: ## Static checks: ruff and black --check
	$(PYTHON) -m ruff check $(CODE)
	$(PYTHON) -m black --check $(CODE)

format: ## Auto-fix lint findings and format the code
	$(PYTHON) -m ruff check --fix $(CODE)
	$(PYTHON) -m black $(CODE)

test: ## Full test suite (no network, no dataset: the workloads are synthetic)
	$(PYTHON) -m pytest

test-fast: ## Test suite without the slower smoke runs
	$(PYTHON) -m pytest -m "not slow"

smoke: ## Tiny end-to-end run of the benchmark; well under a minute
	$(PYTHON) -m experiments.run_scheduler_benchmark --config configs/scheduler_ddqn.yaml \
		--baselines-config configs/scheduler_baselines.yaml --smoke --out $(RUNS)/smoke_scheduler
	$(PYTHON) -m experiments.plot_scheduler --run-dir $(RUNS)/smoke_scheduler

smoke-llm: ## The same tiny run on the LLM-style workload profile, with per-class metrics
	$(PYTHON) -m experiments.run_scheduler_benchmark --config configs/scheduler_llm_workload.yaml \
		--baselines-config configs/scheduler_baselines.yaml --smoke --class-metrics \
		--out $(RUNS)/smoke_scheduler_llm
	$(PYTHON) -m experiments.plot_scheduler --run-dir $(RUNS)/smoke_scheduler_llm \
		--title "LLM-style workload"

scheduler: ## The benchmark: FCFS, SJF, Round Robin, Priority and Double DQN over 5 seeds
	$(PYTHON) -m experiments.run_scheduler_benchmark --config configs/scheduler_ddqn.yaml \
		--baselines-config configs/scheduler_baselines.yaml --workers $(WORKERS) --out $(RUNS)/scheduler
	$(PYTHON) -m experiments.plot_scheduler --run-dir $(RUNS)/scheduler

scheduler-llm: ## The same benchmark on the LLM-style workload profile (inference requests, fine-tuning jobs)
	$(PYTHON) -m experiments.run_scheduler_benchmark --config configs/scheduler_llm_workload.yaml \
		--baselines-config configs/scheduler_baselines.yaml --workers $(WORKERS) --class-metrics \
		--out $(RUNS)/scheduler_llm
	$(PYTHON) -m experiments.plot_scheduler --run-dir $(RUNS)/scheduler_llm --title "LLM-style workload"

reference: ## Re-create the reference runs that the documentation cites (overwrites reference/)
	$(PYTHON) -m experiments.run_reference --workers $(WORKERS)
	$(MAKE) results

results: ## Rebuild tables, Before/After CSVs and charts from reference/, then sync them into the docs
	$(PYTHON) -m experiments.build_results
	$(PYTHON) -m experiments.sync_docs

docs-check: ## Fail if any generated table in the documentation is out of date
	$(PYTHON) -m experiments.sync_docs --check

notebooks: ## Execute the notebooks top to bottom into notebooks/_executed (git-ignored)
	$(PYTHON) -m experiments.run_notebooks

clean: ## Remove caches and your own run outputs (never the reference run)
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info $(RUNS) notebooks/_executed
	find . -name __pycache__ -type d -not -path "./.venv/*" -prune -exec rm -rf {} +
