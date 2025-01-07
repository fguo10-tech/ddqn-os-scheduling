Source label: [Reproduced]. All values are average turnaround times in ms, computed from `experiments/results/reference/scheduler/raw_episodes.csv`.

**Per seed, heavy load** (mean over that seed's evaluation workloads):

| Method | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Mean ± std across seeds |
|---|---|---|---|---|---|---|
| FCFS | 511.9 | 542.8 | 544.5 | 587.0 | 530.1 | 543.3 ± 27.7 |
| SJF | 231.9 | 207.6 | 214.5 | 228.9 | 213.4 | 219.3 ± 10.6 |
| Round Robin | 775.2 | 646.6 | 825.8 | 856.2 | 689.7 | 758.7 ± 88.9 |
| Priority | 338.2 | 387.8 | 386.7 | 405.4 | 375.2 | 378.7 ± 25.0 |
| Double DQN (guardrails on) | 212.3 | 197.9 | 224.3 | 555.8 | 421.2 | 322.3 ± 159.3 |
| SRTF (preemptive reference) | 174.1 | 161.9 | 185.6 | 179.9 | 165.5 | 173.4 ± 9.9 |
| Double DQN (guardrail overrides off) | 212.2 | 196.0 | 224.3 | 453.1 | 339.1 | 284.9 ± 109.6 |

**Distribution over single evaluation workloads, heavy load** (all seeds together):

| Method | Workloads | Median | 90th percentile | Maximum |
|---|---|---|---|---|
| FCFS | 50 | 391.1 | 981.6 | 1693.9 |
| SJF | 50 | 209.1 | 275.7 | 412.7 |
| Round Robin | 50 | 351.7 | 1733.6 | 3816.9 |
| Priority | 50 | 339.4 | 627.9 | 978.3 |
| Double DQN (guardrails on) | 50 | 190.5 | 341.1 | 3334.7 |
| SRTF (preemptive reference) | 50 | 163.5 | 229.0 | 298.9 |
| Double DQN (guardrail overrides off) | 50 | 190.5 | 330.9 | 2395.0 |

**Paired comparison on identical workloads** — in how many evaluation workloads does Double DQN (guardrails on) have a lower turnaround than the other method:

| Load | Workloads | Lower than SJF | Lower than SRTF (preemptive reference) | More than twice SJF |
|---|---|---|---|---|
| light | 50 | 50 of 50 | 1 of 50 | 0 |
| medium | 50 | 45 of 50 | 0 of 50 | 0 |
| heavy | 50 | 33 of 50 | 0 of 50 | 3 |

**The five worst heavy-load workloads of Double DQN (guardrails on):**

| Seed | Workload | Tasks | Turnaround, Double DQN (guardrails on) | Turnaround, SJF | Guardrail overrides | SLO-fallback activations | Starvation triggers |
|---|---|---|---|---|---|---|---|
| 3 | 1 | 47 | 3334.7 | 412.7 | 59 | 2 | 58 |
| 4 | 7 | 57 | 2638.7 | 353.7 | 49 | 2 | 44 |
| 3 | 6 | 49 | 504.7 | 248.9 | 16 | 1 | 4 |
| 3 | 4 | 45 | 476.5 | 259.3 | 4 | 0 | 4 |
| 1 | 6 | 60 | 342.4 | 273.1 | 5 | 0 | 5 |
