## What this changes

<!-- One or two sentences. Link the issue, and the accepted Research proposal if one was needed. -->

Closes #

## Checklist

### Code and tests
- [ ] `make lint` passes (ruff and black, line length 100).
- [ ] `make test` passes; new tests are deterministic, use no network, and slow ones are marked `slow`.
- [ ] `make smoke` passes; any new smoke variant stays well under 30 seconds on a laptop CPU.
- [ ] Public functions have type hints and docstrings; library code logs instead of printing.
- [ ] No hyperparameter is hardcoded in Python; every new YAML key has a comment with meaning, unit and provenance tag (`[Assumption — not in paper]` for a setting chosen by this repository).
- [ ] A new baseline, workload generator, guardrail, reward or observation change, or simulator change comes with the tests listed in CONTRIBUTING.md.

### Results integrity (skip if no numbers are touched)
- [ ] Every number carries one source label: `[Paper-reported]`, `[Reproduced]` or `[Target / TBD]`.
- [ ] No `[Paper-reported]` value appears in a `[Reproduced]` cell.
- [ ] `[Reproduced]` numbers use at least 5 seeds, reported as mean ± sample std across seeds.
- [ ] Each `[Reproduced]` number has a raw CSV, `config_used.yaml` and `metadata.json` behind it.
- [ ] Nothing was tuned on seeds 0–4 or on test data.
- [ ] No real medical, financial or personal data, and no secrets, are committed.
- [ ] Regressions are reported as they are; the simulator, baselines, workloads and metrics were not changed to favour a method.
- [ ] A new method is compared on the same paired workloads and seeds as the existing methods, with the same burst-length information, and a preemptive method is also compared with the SRTF reference.

### Documentation
- [ ] No hand edits between `<!-- BEGIN GENERATED: ... -->` and `<!-- END GENERATED: ... -->` markers.
- [ ] If table generation changed, `make results` was run and `make docs-check` passes.
- [ ] Prose docs and docstrings are updated for any behaviour change.
