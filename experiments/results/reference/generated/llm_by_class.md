Source label: [Reproduced]. Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run). The same run, with every metric computed separately for the tasks of one class. For each class and metric the Before method is the **best of the four baselines on that metric**; After = Double DQN (guardrails on). Load profiles light, medium and heavy are pooled. Values are mean ± sample standard deviation over 5 seeds. A workload that happens to contain no task of a class contributes nothing to that class. Underlying CSV: `experiments/results/reference/before_after/scheduling_llm_by_class.csv`.

| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value | Delta (absolute) | Improvement % | Source Label |
|---|---|---|---|---|---|---|---|---|---|
| Inference requests: turnaround time | ms | Lower is better | SJF | 83.5 ± 6.1 | Double DQN (guardrails on) | 98.5 ± 53.2 | +15.0 | -17.9% | [Reproduced] |
| Inference requests: response time | ms | Lower is better | SJF | 40.8 ± 5.4 | Double DQN (guardrails on) | 41.5 ± 32.4 | +0.8 | -1.9% | [Reproduced] |
| Inference requests: SLO violation rate | fraction of tasks | Lower is better | SJF | 0.4274 ± 0.0279 | Double DQN (guardrails on) | 0.0759 ± 0.0038 | -0.3515 | +82.2% | [Reproduced] |
| Fine-tuning jobs: turnaround time | ms | Lower is better | SJF | 1005.2 ± 104.9 | Double DQN (guardrails on) | 1167.8 ± 66.5 | +162.6 | -16.2% | [Reproduced] |
| Fine-tuning jobs: response time | ms | Lower is better | Round Robin | 46.1 ± 7.9 | Double DQN (guardrails on) | 143.8 ± 40.2 | +97.7 | -212.1% | [Reproduced] |
| Fine-tuning jobs: SLO violation rate | fraction of tasks | Lower is better | SJF | 0.0786 ± 0.0262 | Double DQN (guardrails on) | 0.1011 ± 0.0131 | +0.0225 | -28.6% | [Reproduced] |

Improvement % convention: a positive value always means better after. For higher-is-better metrics, Improvement % = (After − Before) / |Before| × 100; for lower-is-better metrics, Improvement % = (Before − After) / |Before| × 100. Delta = After − Before in the metric's own unit. Both are computed from unrounded means measured under the same config, dataset, workload and seeds; a regression shows as a negative Improvement %.

**Every method per task class, load profiles pooled** (mean ± sample standard deviation across seeds):

| Method | Inference requests: turnaround time (ms) | Inference requests: response time (ms) | Inference requests: SLO violation rate (fraction of tasks) | Fine-tuning jobs: turnaround time (ms) | Fine-tuning jobs: response time (ms) | Fine-tuning jobs: SLO violation rate (fraction of tasks) |
|---|---|---|---|---|---|---|
| FCFS | 451.7 ± 46.0 | 270.8 ± 29.9 | 0.5767 ± 0.0413 | 1316.3 ± 117.6 | 186.8 ± 31.2 | 0.1795 ± 0.0281 |
| SJF | 83.5 ± 6.1 | 40.8 ± 5.4 | 0.4274 ± 0.0279 | 1005.2 ± 104.9 | 174.7 ± 21.3 | 0.0786 ± 0.0262 |
| Round Robin | 272.7 ± 53.2 | 62.1 ± 7.8 | 0.4685 ± 0.0464 | 2544.4 ± 492.4 | 46.1 ± 7.9 | 0.3592 ± 0.0647 |
| Priority | 100.2 ± 8.5 | 52.3 ± 7.5 | 0.4735 ± 0.0271 | 1126.1 ± 152.3 | 221.5 ± 31.2 | 0.1384 ± 0.0325 |
| Double DQN (guardrails on) | 98.5 ± 53.2 | 41.5 ± 32.4 | 0.0759 ± 0.0038 | 1167.8 ± 66.5 | 143.8 ± 40.2 | 0.1011 ± 0.0131 |
| SRTF (preemptive reference) | 39.7 ± 1.9 | 8.5 ± 1.6 | 0.0492 ± 0.0121 | 1006.1 ± 64.4 | 147.0 ± 25.2 | 0.0832 ± 0.0133 |
| Double DQN (guardrail overrides off) | 57.2 ± 28.2 | 11.7 ± 5.5 | 0.0694 ± 0.0109 | 1079.9 ± 80.3 | 143.2 ± 35.4 | 0.0882 ± 0.0165 |

**Every method per task class, heavy load only** (mean ± sample standard deviation across seeds):

| Method | Inference requests: turnaround time (ms) | Inference requests: response time (ms) | Inference requests: SLO violation rate (fraction of tasks) | Fine-tuning jobs: turnaround time (ms) | Fine-tuning jobs: response time (ms) | Fine-tuning jobs: SLO violation rate (fraction of tasks) |
|---|---|---|---|---|---|---|
| FCFS | 825.5 ± 112.2 | 497.0 ± 79.2 | 0.7568 ± 0.0442 | 2025.1 ± 255.7 | 326.1 ± 58.9 | 0.3248 ± 0.0718 |
| SJF | 101.2 ± 10.5 | 53.9 ± 9.1 | 0.5344 ± 0.0199 | 1428.2 ± 151.0 | 326.4 ± 59.9 | 0.1541 ± 0.0533 |
| Round Robin | 472.9 ± 176.6 | 105.4 ± 20.9 | 0.6683 ± 0.0508 | 3838.7 ± 940.5 | 74.4 ± 16.0 | 0.5585 ± 0.0807 |
| Priority | 129.9 ± 13.1 | 72.9 ± 11.7 | 0.6054 ± 0.0188 | 1693.1 ± 308.2 | 410.2 ± 53.2 | 0.2758 ± 0.0710 |
| Double DQN (guardrails on) | 210.3 ± 159.6 | 105.3 ± 96.5 | 0.1292 ± 0.0242 | 1910.9 ± 324.6 | 252.0 ± 76.0 | 0.2055 ± 0.0551 |
| SRTF (preemptive reference) | 47.5 ± 5.1 | 12.9 ± 3.9 | 0.0885 ± 0.0149 | 1412.4 ± 113.1 | 284.2 ± 81.2 | 0.1679 ± 0.0312 |
| Double DQN (guardrail overrides off) | 95.2 ± 85.6 | 21.6 ± 17.5 | 0.1217 ± 0.0317 | 1689.5 ± 296.5 | 248.8 ± 58.1 | 0.1890 ± 0.0736 |
