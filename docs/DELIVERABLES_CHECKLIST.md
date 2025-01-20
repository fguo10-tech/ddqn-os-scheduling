# Deliverables checklist

Checked on 2024-11-19. On 2024-11-20 the LLM-style workload study was added and the checks it
affects were run again: lint, the test suite, both smoke runs, the notebooks,
`make docs-check`, the CI steps in the clean copy (in the environment created for them on
2024-11-19) and the byte-level comparisons named in section 1. Later on 2024-11-20 one post hoc
variant of that study was added (a bounded forced slice for the starvation override), and lint,
the test suite, both smoke runs, `make docs-check` and the CI steps in the clean copy were run
once more; the notebooks do not use that study and were not run again. A box is ticked only if
the item exists **and** the check named beside it was run and passed. Anything that was not run, cannot be checked from a local
machine, or deliberately differs from the original brief is listed in
[section 3](#3-not-done-not-verified-or-deliberately-different) and is not hidden behind a tick.

**Where the checks ran.** The original acceptance checks ran on macOS, CPU only, Python 3.12.14,
with package versions as in [`requirements-lock.txt`](../requirements-lock.txt). The repository
is public at https://github.com/fguo10-tech/ddqn-os-scheduling and has a commit history. GitHub
Actions has completed successfully on a published main revision
([run 44860914326](https://github.com/fguo10-tech/ddqn-os-scheduling/actions/runs/44860914326)).
No outside party has reviewed any part of this draft. "Committed" means tracked by Git.

**Where this repository comes from.** This repository and its companion project
`federated-privacy-adult` were first drafted together as one combined project. On 2024-11-19
the project owner decided to publish them as two independent repositories under the same
direction. The code, configuration, tests and reference results of this topic were moved here
without change; the shared utility code was copied and trimmed to what this topic uses; the
results pipeline was divided; and the documents were rewritten to describe this repository
only. Every check in this file was run on this repository after that division.

**Positioning.** By the project owner's decision the documents focus on the problem and on
what this implementation does: the problem, the design choices with their reasons, the
Before / After comparison with its regressions, and the limits. The source paper appears only
as a background citation, as the tag `[Assumption — not in paper]` and as reference values in
one generated table
([section 3.2](#32-deliberate-differences-from-the-original-brief) lists what this changed
relative to the original brief).

## 1. Acceptance criteria

- [x] **The repository installs from scratch with the documented commands.**
  Checked twice. (a) A new virtual environment inside the repository, `pip install -e ".[all]"`,
  then `make lint`, the test suite, `make smoke` and the example script, with that environment
  active: all succeeded. (b) A copy of only the files that will be committed, in an empty
  folder, a second new environment installed with the extras the CI workflow uses, then the
  workflow's own steps (ruff, black, pytest, `make smoke`, `make smoke-llm`, `make docs-check`)
  and the example: all succeeded. The public clone URL is now available; this original
  clean-room check did not include a fresh clone from GitHub. Python 3.12 only; see section 3
  for Python 3.11.
- [x] **`make test` passes, including the guardrail tests.**
  205 passed, none skipped, both in the repository and in the clean copy.
  `tests/test_scheduler_guardrails.py` forces each of the three rules to fire and checks the
  return to normal and the precedence between rules.
- [x] **Each baseline and the Double DQN smoke run complete at small scale without errors.**
  `make smoke` runs the benchmark end to end on a tiny config, and `make smoke-llm` does the same
  on the LLM-style workload profile. The baselines are checked against
  hand-computed schedules (`tests/test_scheduler_baselines.py`) and against two reference
  implementations that share no code with the simulator
  (`tests/test_scheduler_reference_crosscheck.py`, `tests/test_scheduler_reference_full.py`).
  `tests/test_scheduler_cli.py` checks that results do not depend on the number of worker
  processes.
- [x] **All configs are external YAML, and every run saves raw CSV files and a copy of its
  config.**
  The loader in `src/common/config.py` has no defaults in code: a missing or unknown key is an
  error. Every run folder holds `config_used.yaml`, `metadata.json` and the raw CSV files.
  `tests/test_config_comments.py` checks that every config key has a comment and that every
  setting carries a provenance tag, in the benchmark configs and in the workload profile. Every public function, method and class in `src/` has a
  docstring and full type hints (checked by script; the linter does not enforce this).
- [x] **`README.md` is complete.**
  The fifteen parts of the original brief in order (the title block and fourteen sections),
  about 9,200 words of hand-written prose (generated tables not counted), 14 FAQ answers, the status banner and the Proposed Endeavor
  paragraph verbatim (both checked by `tests/test_docs_integrity.py`).
- [x] **`docs/report/PROJECT_REPORT.md` is complete.**
  Abstract, executive summary, chapters 1 to 13 and five appendices; about 17,700 words of
  hand-written prose; more than six tables; four embedded Mermaid diagrams and six figures.
- [x] **The topic guide is complete.**
  `docs/investigations/01-ddqn-scheduling-reproduction.md`, about 12,900 words: scope, setup,
  results (experiments E1 to E9), observations (F1 to F23), applicability conditions, open
  questions, and suggested use and next experiments.
- [x] **All four architecture diagrams render as Mermaid in Markdown.**
  The four diagrams in `docs/architecture/` and their identical copies embedded in other
  documents rendered without error with Mermaid 11.4.1. Rendering on github.com itself has not
  been observed; see section 3.
- [x] **Both notebooks are present and run in order.**
  `make notebooks` executed both top to bottom (about one minute and two and a half minutes),
  again after the workload generator and the metrics code were changed for the LLM-style study.
  They are committed without outputs, every cell that prints a number also prints its config
  and seeds, and each ends with an "Interpretation and limits" cell.
- [x] **The workloads are synthetic and there is no dataset.**
  Workloads are generated from seeds by `src/scheduler/tasks.py`; nothing is downloaded. The
  README, the dataset card and the report say so (checked by a test).
- [x] **Poster copy and presentation outline are complete.**
  The poster has the exact copy, three results panels, the safety panel and a layout
  specification. The deck has 16 slides plus the five-slide version for platform audiences;
  every slide has three to five full-sentence bullets, a named figure and 80 to 120 words of
  speaker notes (counted by script).
- [x] **The Before / After comparison is complete.**
  The table and the grouped bar chart appear in `RESULTS.md`, the README, the project report,
  the poster and the slides. All five placements are injected from one set of generated files,
  built from the raw CSV files of the reference run; `make docs-check` fails if any placement
  differs. The Before / After table and chart of the LLM-style workload study are in the same
  five placements (checked by a test).
- [x] **The LLM-style workload study is complete, and every document says what it is.**
  A synthetic workload profile (`configs/scheduler_llm_workload.yaml`: inference requests and
  fine-tuning jobs) is run through the same baselines, agent and guardrails; its reference run
  is in `experiments/results/reference/scheduler_llm/`, with metrics per task class. No
  language model is run anywhere in this repository, and a test fails if the README, the
  results file, the report, the poster, the slides or the dataset card stop saying so in
  hand-written prose, or if any document claims that a language model was run. The values of
  the profile were written down before any run and not changed afterwards; development seeds
  100 to 102 were used only to check that episodes finish and training stays stable; the
  reporting seeds were run once; nothing was retuned.
- [x] **Every Delta and Improvement % follows the stated formula and direction convention.**
  Computed in one place, `src/common/before_after.py`, and tested in
  `tests/test_before_after.py`: Delta is After minus Before; a positive percentage always means
  better after; a zero, near-zero, infinite or non-comparable baseline gives
  "N/A — baseline zero / not comparable"; a missing side gives TBD. No percentage mixes a
  paper-reported value with a value from this code. Regressions are shown.
- [x] **No fabricated result appears anywhere, and every TBD is marked.**
  Every `[Reproduced]` number in the documents sits inside a generated block built from
  `experiments/results/reference/`. Three checks stand behind those files. Before the
  division, the whole reference run, including the thirteen ablations, was generated a second
  time with a different number of worker processes and matched byte for byte. After the
  division, every reference file here has the same SHA-256 as its original, every generated
  results table is identical to the one built before the division (identifiers aside), and the
  benchmark was run once more with this repository's own code and environment: `raw_episodes.csv`
  and `summary.csv` matched the committed files byte for byte. After the code change that made
  task classes configurable (2024-11-20), the benchmark and all thirteen ablations were run
  again: every `raw_episodes.csv`, `summary.csv` and `config_used.yaml` matched the committed
  file byte for byte, and every generated table of the benchmark was rebuilt unchanged. The
  reference run of the LLM-style workload study was generated a second time with a different
  number of worker processes; its four result files matched byte for byte. The post hoc variant
  of that study was also generated a second time with a different number of worker processes;
  its four result files and its saved configuration matched byte for byte. When the variant was
  added, the reference run of the study was re-created, because its saved configuration lists
  the profile's ablations; its four result files matched those of the first run byte for byte.
  Paper values come from
  `src/common/paper_values.py` and are labelled `[Paper-reported]`.
- [x] **The researcher profile appears only as an illustrative target user.**
  One profile is named, only in chapter 12 of the project report, with the statement that the
  person is not a collaborator, co-author, endorser or advisor and has not been contacted, and
  with one study shape labelled `[Target / TBD]`. No named scholar is in any author,
  collaborator or acknowledgement field. A test fails if that name appears in any other file,
  or if a name that belongs to the companion project appears at all.
- [x] **No real sensitive data, no secret and no large data file is committed.**
  The project has no dataset. The largest committed file is a chart of about 0.3 MB; the
  committed files total about 14 MB, most of it the two reference runs. A test scans every committed
  file for dataset files, secret patterns and local paths.
- [x] **The documents stay on this repository's topic.**
  A test fails on any leftover of the combined draft, on method vocabulary of the companion
  project, and on text that discusses the source paper instead of this implementation.

## 2. Deliverables by location

| Location | Status | Notes |
|---|---|---|
| `README.md`, `LICENSE` (Apache-2.0), `CITATION.cff`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` | Created | Fan Guo is listed as author; repository URLs and README badges are configured |
| `pyproject.toml`, `requirements.txt`, `requirements-lock.txt`, `Makefile` | Created, used by the checks above | The lock file records the tested versions |
| `.github/workflows/ci.yml`, four issue forms, pull-request template | Created | GitHub Actions has successful runs; see the linked run above |
| GitHub Security settings | Configured | Private vulnerability reporting is enabled |
| `configs/` | Created | `scheduler_ddqn.yaml` (with thirteen ablations), `scheduler_baselines.yaml`, `scheduler_llm_workload.yaml` (the LLM-style workload profile), `before_after.yaml` |
| `src/scheduler/` | Created, tested | Simulator, workloads with task classes defined in the config, four baselines and the SRTF reference, reward, environment, Double DQN agent, guardrails, training, episode metrics and the same metrics per task class, `SchedulerPlugin`, adapter sketches |
| `src/common/` | Created, tested | Config, seeding, logging, statistics, labels, Before / After computation, plotting |
| `tests/` | Created | 18 test files; the result of the full run is in section 1 |
| `data/README.md`, `data/synthetic/` | Created | Dataset card for the synthetic workloads and the workload generator script; there is no dataset |
| `experiments/` | Created | Benchmark runner, plotting script, reference-run script, table builder, document sync and notebook runner |
| `experiments/results/RESULTS.md`, `templates/`, `reference/` | Created | Results document, CSV templates with headers only, and the two reference runs behind every `[Reproduced]` number (the benchmark with its ablations, and the LLM-style workload study) |
| `notebooks/` | Created, executed | Two notebooks, committed without outputs |
| `docs/architecture/` | Created, rendered | Four diagrams, each with explanation, assumptions and alternatives |
| `docs/report/` | Created | Project report, a short record of the source paper and the values it reports (`SOURCE_PAPER_FACTS.md`), bibliography |
| `docs/investigations/` | Created | One topic guide (the folder and file name are kept from the first draft) |
| `docs/poster/`, `docs/slides/` | Created | Poster copy and layout specification; 16-slide deck and five-slide version |
| `docs/REPLICATIONS.md` | Created | Empty register: no external replication has been reported |
| `examples/` | Created, run | One quickstart script |

## 3. Not done, not verified, or deliberately different

### 3.1 Not done or not verified

- **The repository is publicly published** at https://github.com/fguo10-tech/ddqn-os-scheduling.
  The test counts above describe the original validation snapshot, not this later documentation
  cleanup.
- **GitHub Actions has passed** on a published main revision (see the run linked above). The
  badge in the README shows the current workflow status.
- **Python 3.11 is declared but untested.** `pyproject.toml` allows it and the CI matrix
  includes it; every check here used Python 3.12.
- **Linux, Windows and GPU are untested.** Results on other hardware may differ in the last
  digits.
- **Mermaid rendering has not been visually checked on github.com.** Local render checks passed;
  this visual check is separate.
- **The one ablation on the LLM-style workload profile is post hoc.** The bounded forced slice
  of the starvation override was defined after that study's results had been seen and was run
  on the reporting seeds, with one value. It is exploratory. A repeat fixed in advance on fresh
  seeds, other slice lengths and the benchmark's own ablations on that profile have not been
  run, and nothing was retuned for the profile.
- **The LLM-style workload profile is not calibrated.** Its values are hand-chosen; they were
  not measured on an LLM system and not fitted to a trace. The study covers one simulated node,
  without request batching or a model-loading cost.
- **There is no notebook for the LLM-style workload study.** The two notebooks cover the
  benchmark and its ablations.
- **The job-queue adapters are sketches.** They import no cluster API and have never been
  connected to a cluster.
- **No large-language-model component exists.** The Proposed Endeavor mentions one; this
  repository implements learned scheduling with guardrails and lists the rest as planned. The
  LLM-style workload study schedules synthetic tasks shaped like the work of an LLM platform;
  no language model is run.
- **No integrated demonstration with the companion project exists.** It is planned, not
  implemented.
- **No external replication and no outside review.** The review passes described in the
  documents were internal ones made while the draft was written.
- **Poster and slides are Markdown copy,** as the original brief asks; no PDF or slide file was
  produced.

### 3.2 Deliberate differences from the original brief

Decided by the project owner after the first draft:

1. **Two repositories instead of one.** The original brief asked for a single repository
   covering two topics. This repository covers one. As a consequence it has four architecture
   diagrams where the brief listed six across both topics, two notebooks of the three, one
   topic guide of the two, and one of the six researcher profiles; the others are in the
   companion project. The import package of both projects is called `src`, so the two must not
   be installed into the same environment: use one virtual environment per project.
2. **Focus on the problem, not on the source paper.** The original brief asked the documents
   to examine the source paper point by point: a chapter of the report on it, a comparison of
   its values with this code's values, and an investigation report closing with a decision
   summary. The documents do not do that. The README banner reads "Draft reference
   implementation — values printed in the source paper are shown for reference only; …"; the
   values printed in the paper appear in one generated reference table, in `RESULTS.md` and in
   chapter 8 of the report, and are never compared with values from this code; chapter 3 of
   the report is "Design choices and assumptions"; `docs/report/SOURCE_PAPER_FACTS.md` is a
   short record of the paper; the document in `docs/investigations/` is a topic guide that ends
   with suggested use and next experiments; `[Reproduced]` is explained everywhere as "obtained
   by running this repository's code under the documented conditions"; and comments, docstrings
   and table captions in the code describe what the code does. That last change was checked to
   alter no behaviour: the syntax trees of every Python file (docstrings and string text aside)
   and the parsed values of every YAML file are unchanged, two test functions were renamed with
   identical statements, and every result CSV has the same SHA-256 as before. The six figures
   of the reference run were drawn again because their caption changed.

3. **An LLM-style workload study was added.** The original brief had no such study. The
   project owner asked for a workload of inference requests and fine-tuning jobs, run through
   the existing baselines, agent and guardrails, with its own Before / After table. To make it
   possible, task classes are now defined in the config instead of being fixed in the code,
   priorities can be set per class, a config can replace a mapping of its parent
   (`replace_keys`), and the runner can report metrics per task class (`--class-metrics`). The
   benchmark config and its results did not change (section 1).

Decided while the first draft was written:

4. **Two grey reference bars were added to the charts:** preemptive SRTF and the same agent
   with the guardrail overrides off. They are not Before methods, and no Before / After
   percentage is computed against them.
5. **The agent's default settings were not changed after the reporting seeds were seen,**
   although several ablation variants score better on those seeds. Choosing among them would be
   tuning on the test set. For the same reason the After method of the LLM-style workload study
   is the agent with guardrails on, as fixed before the run, although the same network scores
   better there with the override rules off.
6. **Notebook 01 runs all five reporting seeds at the full training budget** (about a minute)
   rather than at a reduced scale, because a subset of seeds changes which method looks better
   on turnaround time.
7. **The reference runs are committed:** about 13 MB of raw CSV files and figures under
   `experiments/results/reference/`. These are results, not datasets; your own runs go to the
   git-ignored `experiments/results/runs/`.

### 3.3 What a reader of the results should know

- **The Before / After comparison has gains and regressions.** In this implementation, with the
  documented configuration and five seeds, the agent's turnaround time is lower than SJF's at
  light and medium load and higher at heavy load and on the pooled average; its response time
  and SLO violation rate are better than every baseline's on the pooled average; preemptive
  SRTF is ahead of the agent on turnaround at every load; the guardrails did not help under
  heavy load. The tables are in [`RESULTS.md`](../experiments/results/RESULTS.md).
- **The LLM-style workload study has one clear gain and several regressions.** On that
  synthetic profile the agent misses far fewer deadlines than each of the four baselines, and
  almost all of that gain is in the inference requests. Its pooled turnaround and waiting time
  are worse than SJF's (better at light and medium load, clearly worse at heavy load);
  fine-tuning jobs are worse off on every per-class metric; preemptive SRTF is better than the
  agent on almost every metric; and with the guardrail overrides on, the agent did worse and
  more tasks waited past the starvation threshold than with them off. The tables are in
  section 4 of [`RESULTS.md`](../experiments/results/RESULTS.md).

## 4. Owner decisions remaining

- No affiliation was supplied; only Fan Guo is listed. Add an affiliation only if it is confirmed.
- Compare the Proposed Endeavor paragraph with the original exhibit, character by character;
  that exhibit is not included in this repository.
- No formal release has been published. The package remains `0.1.0.dev0`; `date-released` is
  omitted from `CITATION.cff` until a release is made.

## 5. Re-running the checks

Run these with the project's virtual environment active.

```bash
make install        # editable install with every optional extra
make lint           # ruff and black --check
make test           # full test suite, including the documentation integrity tests
make smoke          # tiny end-to-end run of the benchmark
make smoke-llm      # the same tiny run on the LLM-style workload profile
make notebooks      # execute the two notebooks top to bottom
make docs-check     # fail if any generated table in the documents is out of date
make reference      # re-create both reference runs (overwrites them), then rebuild every table
```
