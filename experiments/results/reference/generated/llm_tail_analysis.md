Source label: [Reproduced]. Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run). All values are average turnaround times in ms, computed from `experiments/results/reference/scheduler_llm/raw_episodes.csv`.

**Per seed, heavy load** (mean over that seed's evaluation workloads):

| Method | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Mean ± std across seeds |
|---|---|---|---|---|---|---|
| FCFS | 1037.9 | 1007.3 | 931.6 | 872.9 | 1212.8 | 1012.5 ± 129.3 |
| SJF | 294.1 | 334.9 | 260.4 | 266.1 | 334.3 | 298.0 ± 35.8 |
| Round Robin | 1233.3 | 947.6 | 693.6 | 729.6 | 1425.7 | 1005.9 ± 318.3 |
| Priority | 329.8 | 443.1 | 278.3 | 336.6 | 447.2 | 367.0 ± 74.9 |
| Double DQN (guardrails on) | 690.6 | 597.1 | 333.5 | 298.5 | 466.7 | 477.3 ± 167.8 |
| SRTF (preemptive reference) | 267.2 | 241.9 | 209.3 | 242.1 | 286.9 | 249.5 ± 29.3 |
| Double DQN (guardrail overrides off) | 556.0 | 280.6 | 241.1 | 256.7 | 363.0 | 339.5 ± 129.8 |

**Distribution over single evaluation workloads, heavy load** (all seeds together):

| Method | Workloads | Median | 90th percentile | Maximum |
|---|---|---|---|---|
| FCFS | 50 | 638.8 | 2314.7 | 5279.5 |
| SJF | 50 | 239.9 | 467.6 | 1239.4 |
| Round Robin | 50 | 608.9 | 1995.5 | 5972.8 |
| Priority | 50 | 269.6 | 595.3 | 1642.6 |
| Double DQN (guardrails on) | 50 | 171.9 | 1201.7 | 4801.2 |
| SRTF (preemptive reference) | 50 | 203.7 | 475.7 | 853.4 |
| Double DQN (guardrail overrides off) | 50 | 171.4 | 701.1 | 3496.0 |

**Paired comparison on identical workloads** — in how many evaluation workloads does Double DQN (guardrails on) have a lower turnaround than the other method:

| Load | Workloads | Lower than SJF | Lower than SRTF (preemptive reference) | More than twice SJF |
|---|---|---|---|---|
| light | 50 | 46 of 50 | 22 of 50 | 0 |
| medium | 50 | 43 of 50 | 19 of 50 | 0 |
| heavy | 50 | 35 of 50 | 22 of 50 | 8 |

**The five worst heavy-load workloads of Double DQN (guardrails on):**

| Seed | Workload | Tasks | Turnaround, Double DQN (guardrails on) | Turnaround, SJF | Guardrail overrides | SLO-fallback activations | Starvation triggers |
|---|---|---|---|---|---|---|---|
| 0 | 4 | 59 | 4801.2 | 916.5 | 66 | 2 | 57 |
| 1 | 6 | 60 | 4350.4 | 1239.4 | 64 | 2 | 64 |
| 4 | 0 | 57 | 1539.2 | 461.1 | 22 | 1 | 22 |
| 4 | 7 | 57 | 1528.7 | 679.4 | 24 | 0 | 24 |
| 2 | 4 | 53 | 1307.7 | 415.0 | 31 | 0 | 32 |
