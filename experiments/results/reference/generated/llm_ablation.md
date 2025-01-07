Source label: [Reproduced]. Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run). Post hoc variant `starvation_bounded_slice`: `guardrails.starvation.forced_time_slice_ms` = `20.0` (reference run: `null`). It was added after the reference results of this profile had been seen and is not part of the Before / After tables above. The agent is retrained on the same seeds with this one setting changed, in training and in evaluation, and is evaluated on the same paired workloads, with the override rules on and with them off. Mean ± sample standard deviation across seeds. The gap is the per-seed difference between the agent with the override rules on and the same trained network with them off, on identical workloads: a positive gap means the rules cost that much. `all` pools the load profiles.

**Turnaround of Double DQN (guardrails on) with the override rules on and off (ms):**

| Run | Load | Starvation overrides (per episode) | Decisions overridden (per episode) | Rules on | Rules off | Gap, on − off | Seeds with a higher value with the rules on |
|---|---|---|---|---|---|---|---|
| Reference run | heavy | 5.32 ± 1.57 | 6.10 ± 1.79 | 477.3 ± 167.8 | 339.5 ± 129.8 | +137.8 ± 105.3 | 5 of 5 |
| Reference run | all | 2.11 ± 0.64 | 2.36 ± 0.54 | 266.4 ± 58.1 | 214.7 ± 44.1 | +51.7 ± 39.1 | 5 of 5 |
| Variant `starvation_bounded_slice` | heavy | 2.54 ± 2.92 | 3.60 ± 3.52 | 374.4 ± 163.0 | 364.8 ± 134.1 | +9.6 ± 33.9 | 3 of 5 |
| Variant `starvation_bounded_slice` | all | 1.03 ± 0.85 | 1.45 ± 1.07 | 236.8 ± 60.2 | 235.7 ± 53.1 | +1.1 ± 12.9 | 2 of 5 |

**Tasks that waited longer than the starvation threshold** (tasks per evaluation workload whose longest continuous wait exceeded `metrics.starvation_threshold_ms`):

| Run | Load | Rules on | Rules off | Gap, on − off | Seeds with a higher value with the rules on |
|---|---|---|---|---|---|
| Reference run | heavy | 3.04 ± 1.05 | 1.60 ± 0.68 | +1.44 ± 0.65 | 5 of 5 |
| Reference run | all | 1.25 ± 0.37 | 0.63 ± 0.18 | +0.62 ± 0.35 | 5 of 5 |
| Variant `starvation_bounded_slice` | heavy | 0.98 ± 0.74 | 0.98 ± 0.65 | +0.00 ± 0.19 | 1 of 5 |
| Variant `starvation_bounded_slice` | all | 0.43 ± 0.15 | 0.46 ± 0.12 | -0.03 ± 0.09 | 1 of 5 |

**Reading rule, fixed before the variant was run** (`scheduling_llm.ablation` in `configs/before_after.yaml`). On the `heavy` load profile, the explanation — the length of the forced dispatch is what makes the override rules costly on this profile — counts as supported on a quantity when the gap in the variant is smaller than 0.5 × the gap in the reference run:

| Quantity | Gap, reference run | Gap, variant | Variant gap ÷ reference gap | Below 0.5? |
|---|---|---|---|---|
| Turnaround (ms) | +137.8 | +9.6 | 0.07 | yes |
| Tasks waiting past the starvation threshold (per episode) | +1.44 | +0.00 | 0.00 | yes |

**By this rule the explanation is supported.** [Reproduced]

**Double DQN (guardrails on) in the variant, next to the reference run, the best baseline and the two references.** The baselines and SRTF do not use this setting, so their values are those of the reference run; the guardrail-overrides-off column is the network of the reference run evaluated with the rules off. In the two percentage columns a positive value means the variant is better, a negative value worse. Both runs use the same seeds and the same evaluation workloads, so the column between them counts the seeds in which the per-seed mean of the variant is the better one. Underlying CSV (variant against reference run): `experiments/results/reference/before_after/scheduling_llm_ablation.csv`.

| Metric | Scope | Best baseline | SRTF (preemptive reference) | Double DQN (guardrail overrides off), reference run | Double DQN (guardrails on), reference run | Double DQN (guardrails on), variant | Variant versus reference run | Seeds in which the variant is better | Variant versus best baseline |
|---|---|---|---|---|---|---|---|---|---|
| Completion / turnaround time (ms) | all loads | SJF 225.7 ± 27.3 | 188.6 ± 18.1 | 214.7 ± 44.1 | 266.4 ± 58.1 | 236.8 ± 60.2 | +11.1% | 4 of 5 | -4.9% |
| Throughput (tasks/s) | all loads | SJF 11.967 ± 0.636 | 11.844 ± 0.671 | 11.874 ± 0.673 | 11.798 ± 0.618 | 11.876 ± 0.637 | +0.7% | 4 of 5 | -0.8% |
| Response time (ms) | all loads | Round Robin 59.9 ± 7.5 | 31.3 ± 5.0 | 32.7 ± 7.2 | 56.9 ± 30.6 | 30.1 ± 5.0 | +47.2% | 5 of 5 | +49.8% |
| Waiting time (ms) | all loads | SJF 137.6 ± 22.3 | 99.9 ± 13.0 | 126.0 ± 39.7 | 175.6 ± 53.7 | 147.5 ± 57.3 | +16.0% | 4 of 5 | -7.2% |
| SLO violation rate (fraction of tasks) | all loads | SJF 0.3752 ± 0.0269 | 0.0554 ± 0.0122 | 0.0731 ± 0.0099 | 0.0807 ± 0.0024 | 0.0826 ± 0.0293 | -2.4% | 2 of 5 | +78.0% |
| Starvation count (tasks per episode) | all loads | Round Robin 0.000 ± 0.000 | 0.993 ± 0.202 | 0.627 ± 0.175 | 1.247 ± 0.371 | 0.433 ± 0.155 | +65.2% | 5 of 5 | N/A — baseline zero / not comparable |
| Completion / turnaround time (ms) | light load | SJF 157.2 ± 33.1 | 132.8 ± 32.0 | 129.6 ± 30.4 | 134.9 ± 41.6 | 133.7 ± 32.9 | +0.9% | 3 of 5 | +15.0% |
| Completion / turnaround time (ms) | medium load | SJF 221.9 ± 25.9 | 183.4 ± 14.5 | 175.0 ± 18.3 | 186.9 ± 34.5 | 202.5 ± 101.4 | -8.3% | 4 of 5 | +8.7% |
| Completion / turnaround time (ms) | heavy load | SJF 298.0 ± 35.8 | 249.5 ± 29.3 | 339.5 ± 129.8 | 477.3 ± 167.8 | 374.4 ± 163.0 | +21.6% | 4 of 5 | -25.6% |
| Turnaround time (ms) | inference requests, all loads | SJF 83.5 ± 6.1 | 39.7 ± 1.9 | 57.2 ± 28.2 | 98.5 ± 53.2 | 76.9 ± 46.7 | +21.9% | 5 of 5 | +7.9% |
| Response time (ms) | inference requests, all loads | SJF 40.8 ± 5.4 | 8.5 ± 1.6 | 11.7 ± 5.5 | 41.5 ± 32.4 | 12.9 ± 6.1 | +69.0% | 5 of 5 | +68.4% |
| SLO violation rate (fraction of tasks) | inference requests, all loads | SJF 0.4274 ± 0.0279 | 0.0492 ± 0.0121 | 0.0694 ± 0.0109 | 0.0759 ± 0.0038 | 0.0807 ± 0.0309 | -6.3% | 2 of 5 | +81.1% |
| Turnaround time (ms) | fine-tuning jobs, all loads | SJF 1005.2 ± 104.9 | 1006.1 ± 64.4 | 1079.9 ± 80.3 | 1167.8 ± 66.5 | 1102.0 ± 123.5 | +5.6% | 3 of 5 | -9.6% |
| Response time (ms) | fine-tuning jobs, all loads | Round Robin 46.1 ± 7.9 | 147.0 ± 25.2 | 143.2 ± 35.4 | 143.8 ± 40.2 | 121.8 ± 20.9 | +15.3% | 3 of 5 | -164.5% |
| SLO violation rate (fraction of tasks) | fine-tuning jobs, all loads | SJF 0.0786 ± 0.0262 | 0.0832 ± 0.0133 | 0.0882 ± 0.0165 | 0.1011 ± 0.0131 | 0.0859 ± 0.0208 | +15.1% | 4 of 5 | -9.2% |
