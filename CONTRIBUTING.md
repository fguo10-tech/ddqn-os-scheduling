# Contributing

Thank you for looking at this repository. It is a reference implementation for researchers of
a learned operating-system scheduler, following the Double DQN scheduler described by Sun et
al. (2025), and it shows its contribution as a Before / After comparison measured under
documented conditions. The repository contains a
discrete-event operating-system scheduling simulator with FCFS, SJF, Round Robin and Priority
baselines, a preemptive SRTF reference, a Double DQN agent with guardrails, and a
`SchedulerPlugin` interface with job-queue adapter sketches. Every workload is synthetic and
generated from seeds; there is no dataset to download.

This is draft research code (version 0.1.x). Interfaces may still change.

## Who this guide is for

- Researchers who want to reproduce a result, benchmark a new method against the existing
  baselines, or extend the benchmark (a new scheduler, guardrail, reward variant or workload generator).
- Researchers who ran the code independently and want to report what they found, whether it
  matched or not.
- Platform engineers who want to look at the `SchedulerPlugin` interface or the job-queue
  adapter sketches. These are sketches, not production integrations; see `SECURITY.md`.

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security
problems, including a guardrail that does not trigger when it should, go through [SECURITY.md](SECURITY.md), never a
public issue.

## Setup

Python 3.11 or 3.12 is required. A CPU is enough for everything.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
make install                       # editable install with every optional extra
make test                          # full test suite, no network
make smoke                         # tiny end-to-end run of the benchmark, synthetic workloads
```

No step needs a network connection after installation, because the workloads are generated
from seeds. `make test-fast` leaves out the tests marked `slow`. `make scheduler` runs the full
benchmark over the reporting seeds into your own run folder. Run `make help` to see
every target. Your own run outputs go to `experiments/results/runs/`, which is git-ignored.
`experiments/results/reference/` holds the run behind every `[Reproduced]` number in the
documentation, and only `make reference` writes there; contributors do not commit to it.

## Branch and pull-request workflow

1. Open or find an issue first for anything larger than a typo, so that work is not duplicated.
   Changes listed under [Research proposals (RFCs)](#research-proposals-rfcs) need an accepted
   proposal before a pull request.
2. Fork the repository and create a topic branch from `main` with a short descriptive name,
   for example `feature/mlfq-baseline` or `fix/srtf-tie-breaking`.
3. Keep each pull request to one logical change. Separate refactoring from behaviour changes.
4. Before pushing, run `make format`, `make lint`, `make test` and `make smoke`.
5. Open the pull request against `main` and fill in the template checklist. CI runs lint
   (ruff, black), the test suite on Python 3.11 and 3.12, the smoke runs and `make docs-check`.
6. A maintainer reviews. Push new commits in response rather than force-pushing over review
   history.

## Code style

- **Formatting and lint.** ruff and black, line length 100, Python 3.11 syntax. `make format`
  fixes most findings; `make lint` must pass with no changes needed.
- **Type hints** on every public function; `from __future__ import annotations` at the top of
  each module.
- **Docstrings** on every public module, class and function.
- **Logging, not print.** Library code under `src/` logs through
  `src.common.logging_utils.get_logger(__name__)`. Command-line scripts call `setup_logging` and
  may log a short final summary.
- **No hyperparameter in Python.** Every hyperparameter and experimental setting lives in a YAML
  file under `configs/`. Config dataclasses declare no defaults and are built with
  `src.common.config.from_dict`, which rejects missing and unknown keys.
- **Every YAML key is commented** with its meaning, its unit where one applies, and a provenance
  tag. A setting chosen by this repository is tagged `[Assumption — not in paper]`.
- **Seeds.** Explicit integer seeds; child seeds come from `src.common.seeding.derive_seed`.
- **Reuse `src/common/`** (config, seeding, io, metrics, plotting, labels, Before / After
  tables) instead of re-implementing it.
- **Smoke variant.** Every config may carry a `smoke_overrides:` mapping; entry points accept
  `--smoke`, and the smoke variant of a benchmark must stay well under 30 seconds on a laptop CPU.

## Test requirements

Tests use pytest, must be deterministic and must not touch the network. Mark tests that take
more than about five seconds with `@pytest.mark.slow`, the only marker the test configuration
defines. Build paths from the `repo_root` and `configs_dir` fixtures.

What a new component must come with:

- **A new scheduling baseline.** Hand-computed tests on a small fixed workload (completion,
  waiting and response times checked against values worked out by hand), a test that every job
  completes exactly once, and a determinism test (same seed, same output).
- **A new workload generator or trace loader.** Tests against a tiny synthetic fixture
  committed under `tests/` (never a full trace), a schema check, a test that every task has
  valid arrival, burst and memory values, and a determinism test (same seed, same tasks).
- **A new workload profile** (a YAML file that inherits `configs/scheduler_ddqn.yaml` and
  replaces the task classes, like `configs/scheduler_llm_workload.yaml`). A comment with a
  provenance tag on every key (add the file to `EXPERIMENT_CONFIGS` in
  `tests/test_config_comments.py`), a test that generated workloads have the shape the profile
  describes, and a smoke run with `--class-metrics`. Fix the values before the first run on the
  reporting seeds and say in the profile's header what the mix stands for and what it does not.
- **A new guardrail.** One test where it must trigger and one where it must not, a test that
  the fallback action it takes is the documented one, and a test of its precedence against the
  existing rules in `GuardrailEngine.filter`.
- **A change to the reward or the observation.** A test of the new term or feature on a
  hand-built state, and a check that `scheduler_state_table` or the reward description still
  matches the code after `make results`.
- **A change to the simulator.** The cross-check tests in
  `tests/test_scheduler_reference_crosscheck.py` and `tests/test_scheduler_reference_full.py`
  compare the simulator with independent reference implementations; they must keep passing,
  or the reference implementations must be changed in the same pull request with a stated
  reason.

## Integrity rules for results

Reviewers check every pull request that touches results, tables, figures or documentation
against this list.

1. Every number in code, comments, configs, tables and prose carries exactly one source label:
   `[Paper-reported]` (printed in a source paper and shown for reference only, taken only from
   `src/common/paper_values.py`; never a target for this code and never compared numerically
   with a value from this code), `[Reproduced]` (obtained by running this repository's code under
   the documented conditions; the label says where a number comes from, not that a number
   printed in a paper was reproduced) or `[Target / TBD]` (specified but not run; the cell shows `TBD`, never a value).
2. A `[Paper-reported]` value never appears in a `[Reproduced]` cell, and a reproduced number
   is never labelled `[Paper-reported]`.
3. A `[Reproduced]` number comes from at least 5 seeds.
4. `mean ± std` means: average within a seed, then the mean and the sample standard deviation
   (ddof = 1) across seeds, computed with `src.common.metrics.summarise_by_seed`.
5. Every `[Reproduced]` number has a raw CSV, a `config_used.yaml` and a `metadata.json` behind
   it (written by `src.common.io.save_run_metadata`).
6. Nothing is tuned on the reporting seeds 0–4 or on test data. Use seeds 100 and above for
   development and tuning.
7. No real medical, financial or personal data is committed. Workloads are synthetic; a public
   trace, if one is added, is downloaded by script into a git-ignored folder, and only
   generators, download scripts, checksums and tiny synthetic fixtures are committed.
8. Regressions are reported as they are. If the method under study loses to a baseline, that is
   the result. The simulator, baselines, metrics and workloads are not changed to make one
   method look better.

## Generated documentation

Result tables in the documentation sit between markers:

```markdown
<!-- BEGIN GENERATED: before_after_summary -->
...
<!-- END GENERATED: before_after_summary -->
```

Everything between a pair of markers is written by `make results` from the reference run. Never
edit it by hand; your edit will be overwritten, and if it is not, the table no longer matches the
data. `make docs-check` fails CI when any generated block is stale. If you change how a table is
built, change the generating code and run `make results` so the docs and the code agree in the
same pull request. Prose outside the markers is edited normally.

## Research proposals (RFCs)

Open a "Research proposal" issue before writing code for any change to:

- simulator semantics (event ordering, preemption, time accounting, the machine model);
- the reward definition of the scheduling agent;
- metric definitions, or which metrics are reported;
- the workload generator, the load profiles, or the split between training and evaluation
  workloads;
- the guardrail rules, their thresholds or their precedence;
- public interfaces, such as `SchedulerPlugin`, the config schema or the CSV column tuples.

The form asks for the question, the hypothesis, the design, the evidence that would change the
conclusion, data sources and compute needs. A proposal is accepted when a maintainer says so in
the issue; the pull request then links to it.

## Submitting a benchmark result

Use the "Benchmark submission" issue form. Run your method on the standard protocol (at least 5
seeds, the three load profiles light, medium and heavy, and evaluation on the same paired
workloads as the existing methods) and attach:

- the summary CSV and the raw per-seed CSVs;
- `config_used.yaml` and `metadata.json` from each run directory;
- the exact command, including every `--set` override;
- the seeds;
- the hardware and the package versions recorded in `metadata.json`.

Confirm in the form that nothing was tuned on seeds 0–4 or on test data. Submitted numbers are
labelled `[Reproduced]` only after a maintainer has re-run them from your config; until then they
are listed as external submissions with your attachments.

## Submitting a replication report

Use the "Replication report" issue form whether or not your numbers matched. A failed
replication is as useful as a successful one. Attach the same items as for a benchmark result
(summary CSV, `config_used.yaml`, `metadata.json`, exact command, seeds, hardware), state the
commit you ran, and give the observed values next to the values from this repository's reference run that you
compared against, with their source labels.

## How external replications are credited

Replications are recorded in [docs/REPLICATIONS.md](docs/REPLICATIONS.md) and mentioned in the
release notes of the next release. The reporter's name and affiliation are recorded only with
their explicit consent; otherwise the entry is anonymous. A replication reporter is credited as a
replicator. They are not added as an author of the code or of any write-up, and a replication is
never presented as an endorsement of the project.

## Review criteria

A reviewer asks:

- Does the change do one thing, and is it described accurately?
- Do lint, tests, smoke runs and `make docs-check` pass?
- Does every new setting live in YAML with a comment and a provenance tag?
- Does every number carry the right source label, and do the integrity rules above hold?
- Do the tests cover the behaviour, including the failure cases?
- Is the change reproducible from the config and seeds alone?
- Does it keep the baselines, simulator, workloads and metrics fair to every method, including
  the information each method is given (the current-burst oracle)?
- Are documentation and docstrings updated?

## Good first issues

- Add a multi-level feedback queue (MLFQ) baseline, with hand-computed tests.
- Add a trace-driven workload loader that replays a public cluster trace format, with a tiny
  synthetic fixture for tests.
- Add SJF and SRTF variants that estimate burst lengths by exponential averaging of past bursts
  instead of reading the exact length, to measure how much the oracle is worth.
- Re-create the reference run of the benchmark with `--class-metrics` and add the per-class
  tables for its three classes (CPU-bound, memory-bound, I/O-bound) to `RESULTS.md`; the flag
  and the table builder exist, the benchmark's reference run was made without the flag.
- Confirm the bounded forced time slice of the starvation override on the LLM-style workload
  profile. The named ablation `starvation_bounded_slice` exists and was run once, post hoc, on
  the reporting seeds (`RESULTS.md`, section 4.8). Repeat it on seeds not used so far, with the
  slice lengths and the reading rule fixed before the run.
- Write a workload profile for another workload family, with the tests listed above.
- Add a semi-Markov discount option, so that the discount depends on the simulated time a
  decision takes rather than applying once per decision.
- Port the CI test matrix to macOS runners.
- Add a schema check that every YAML key in `configs/` carries a provenance-tagged comment.
