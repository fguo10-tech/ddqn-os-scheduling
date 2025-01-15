# External replications

This page records independent attempts to replicate the scheduling benchmark in this repository, whatever
their outcome. A replication that does not reproduce a result is recorded exactly like one that
does. Reports arrive through the "Replication report" issue form; see `CONTRIBUTING.md`.

**No external replication has been reported yet.**

## Columns

| Column | Meaning |
|---|---|
| Date | Date the report was accepted (YYYY-MM-DD). |
| Benchmark | What was re-run: the main benchmark (baselines, SRTF reference and Double DQN), the same benchmark on the LLM-style workload profile, an ablation by name, or the smoke run; and the workload used (built-in synthetic generator, a workload profile by file name, modified generator, or a named trace). |
| Commit | The commit the replicator ran. |
| Replicator and affiliation | Listed only with the replicator's explicit consent; otherwise "anonymous". |
| Outcome | Reproduced, partially reproduced, or not reproduced, as stated in the report. |
| Link | The replication-report issue, which holds the attachments (summary CSV, `config_used.yaml`, `metadata.json`, command, seeds, hardware). |

Replicators are credited here and in the release notes of the next release. They are credited
as replicators only: they are not listed as authors of the code or of any write-up, and an entry
here is not an endorsement of the project.

## Registry

| Date | Benchmark | Commit | Replicator and affiliation | Outcome | Link |
|---|---|---|---|---|---|
