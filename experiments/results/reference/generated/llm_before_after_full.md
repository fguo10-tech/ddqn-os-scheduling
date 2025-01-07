Source label: [Reproduced]. Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run). Before = FCFS, SJF, Round Robin and Priority; After = Double DQN (guardrails on). Load profiles light, medium and heavy are pooled. Values are mean ± sample standard deviation over 5 seeds. Underlying CSV: `experiments/results/reference/before_after/scheduling_llm.csv`.

| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value | Delta (absolute) | Improvement % | Source Label |
|---|---|---|---|---|---|---|---|---|---|
| Completion / turnaround time | ms | Lower is better | FCFS | 589.5 ± 59.7 | Double DQN (guardrails on) | 266.4 ± 58.1 | -323.2 | +54.8% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | SJF | 225.7 ± 27.3 | Double DQN (guardrails on) | 266.4 ± 58.1 | +40.7 | -18.0% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Round Robin | 649.8 ± 146.2 | Double DQN (guardrails on) | 266.4 ± 58.1 | -383.5 | +59.0% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Priority | 260.1 ± 39.9 | Double DQN (guardrails on) | 266.4 ± 58.1 | +6.2 | -2.4% | [Reproduced] |
| Throughput | tasks/s | Higher is better | FCFS | 11.244 ± 0.546 | Double DQN (guardrails on) | 11.798 ± 0.618 | +0.554 | +4.9% | [Reproduced] |
| Throughput | tasks/s | Higher is better | SJF | 11.967 ± 0.636 | Double DQN (guardrails on) | 11.798 ± 0.618 | -0.169 | -1.4% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Round Robin | 9.709 ± 0.633 | Double DQN (guardrails on) | 11.798 ± 0.618 | +2.090 | +21.5% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Priority | 11.767 ± 0.812 | Double DQN (guardrails on) | 11.798 ± 0.618 | +0.031 | +0.3% | [Reproduced] |
| Response time | ms | Lower is better | FCFS | 258.3 ± 28.7 | Double DQN (guardrails on) | 56.9 ± 30.6 | -201.4 | +78.0% | [Reproduced] |
| Response time | ms | Lower is better | SJF | 63.1 ± 8.1 | Double DQN (guardrails on) | 56.9 ± 30.6 | -6.2 | +9.8% | [Reproduced] |
| Response time | ms | Lower is better | Round Robin | 59.9 ± 7.5 | Double DQN (guardrails on) | 56.9 ± 30.6 | -3.0 | +5.0% | [Reproduced] |
| Response time | ms | Lower is better | Priority | 80.2 ± 13.2 | Double DQN (guardrails on) | 56.9 ± 30.6 | -23.3 | +29.0% | [Reproduced] |
| Waiting time | ms | Lower is better | FCFS | 492.9 ± 55.6 | Double DQN (guardrails on) | 175.6 ± 53.7 | -317.3 | +64.4% | [Reproduced] |
| Waiting time | ms | Lower is better | SJF | 137.6 ± 22.3 | Double DQN (guardrails on) | 175.6 ± 53.7 | +38.0 | -27.6% | [Reproduced] |
| Waiting time | ms | Lower is better | Round Robin | 529.0 ± 133.4 | Double DQN (guardrails on) | 175.6 ± 53.7 | -353.4 | +66.8% | [Reproduced] |
| Waiting time | ms | Lower is better | Priority | 170.4 ± 34.2 | Double DQN (guardrails on) | 175.6 ± 53.7 | +5.2 | -3.0% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | FCFS | 0.5200 ± 0.0373 | Double DQN (guardrails on) | 0.0807 ± 0.0024 | -0.4393 | +84.5% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | SJF | 0.3752 ± 0.0269 | Double DQN (guardrails on) | 0.0807 ± 0.0024 | -0.2946 | +78.5% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Round Robin | 0.4562 ± 0.0477 | Double DQN (guardrails on) | 0.0807 ± 0.0024 | -0.3755 | +82.3% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Priority | 0.4248 ± 0.0265 | Double DQN (guardrails on) | 0.0807 ± 0.0024 | -0.3441 | +81.0% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | FCFS | 5.007 ± 1.298 | Double DQN (guardrails on) | 1.247 ± 0.371 | -3.760 | +75.1% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | SJF | 1.060 ± 0.249 | Double DQN (guardrails on) | 1.247 ± 0.371 | +0.187 | -17.6% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Round Robin | 0.000 ± 0.000 | Double DQN (guardrails on) | 1.247 ± 0.371 | +1.247 | N/A — baseline zero / not comparable | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Priority | 1.193 ± 0.319 | Double DQN (guardrails on) | 1.247 ± 0.371 | +0.053 | -4.5% | [Reproduced] |

- Starvation count, Round Robin → Double DQN (guardrails on): Before is zero or near zero (|Before| <= 0.05 tasks per episode), so a percentage would be meaningless.

Improvement % convention: a positive value always means better after. For higher-is-better metrics, Improvement % = (After − Before) / |Before| × 100; for lower-is-better metrics, Improvement % = (Before − After) / |Before| × 100. Delta = After − Before in the metric's own unit. Both are computed from unrounded means measured under the same config, dataset, workload and seeds; a regression shows as a negative Improvement %.
