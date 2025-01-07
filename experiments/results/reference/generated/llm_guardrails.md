Source label: [Reproduced]. Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run). Counts are for Double DQN (guardrails on): how often each override rule fired in one evaluation workload, mean ± sample standard deviation across seeds. The last two columns put the turnaround of that agent next to the same trained network evaluated with the three override rules off; `all` pools the load profiles.

| Load | Starvation overrides (per episode) | SLO-fallback activations (per episode) | Q-divergence latches (per episode) | Decisions overridden (per episode) | Turnaround, Double DQN (guardrails on) (ms) | Turnaround, Double DQN (guardrail overrides off) (ms) |
|---|---|---|---|---|---|---|
| light | 0.26 ± 0.58 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.24 ± 0.54 | 134.9 ± 41.6 | 129.6 ± 30.4 |
| medium | 0.74 ± 1.16 | 0.02 ± 0.04 | 0.00 ± 0.00 | 0.74 ± 1.16 | 186.9 ± 34.5 | 175.0 ± 18.3 |
| heavy | 5.32 ± 1.57 | 0.18 ± 0.11 | 0.00 ± 0.00 | 6.10 ± 1.79 | 477.3 ± 167.8 | 339.5 ± 129.8 |
| all | 2.11 ± 0.64 | 0.07 ± 0.02 | 0.00 ± 0.00 | 2.36 ± 0.54 | 266.4 ± 58.1 | 214.7 ± 44.1 |

**Tasks that waited longer than the starvation threshold, per task class** (tasks per evaluation workload whose longest continuous wait exceeded `metrics.starvation_threshold_ms`; mean ± sample standard deviation across seeds):

| Load | Inference requests, Double DQN (guardrails on) | Inference requests, Double DQN (guardrail overrides off) | Fine-tuning jobs, Double DQN (guardrails on) | Fine-tuning jobs, Double DQN (guardrail overrides off) |
|---|---|---|---|---|
| light | 0.10 ± 0.22 | 0.00 ± 0.00 | 0.14 ± 0.31 | 0.04 ± 0.09 |
| medium | 0.04 ± 0.09 | 0.00 ± 0.00 | 0.42 ± 0.54 | 0.24 ± 0.30 |
| heavy | 1.46 ± 1.20 | 0.32 ± 0.55 | 1.58 ± 0.30 | 1.28 ± 0.28 |
| all | 0.53 ± 0.43 | 0.11 ± 0.18 | 0.71 ± 0.14 | 0.52 ± 0.04 |
