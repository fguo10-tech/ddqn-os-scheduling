Source label: [Reproduced]. Before = FCFS, SJF, Round Robin and Priority; After = Double DQN (guardrails on). Load profiles light, medium and heavy are pooled. Values are mean ± sample standard deviation over 5 seeds. Underlying CSV: `experiments/results/reference/before_after/scheduling.csv`.

| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value | Delta (absolute) | Improvement % | Source Label |
|---|---|---|---|---|---|---|---|---|---|
| Completion / turnaround time | ms | Lower is better | FCFS | 333.3 ± 20.9 | Double DQN (guardrails on) | 198.2 ± 54.6 | -135.2 | +40.5% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | SJF | 178.0 ± 8.0 | Double DQN (guardrails on) | 198.2 ± 54.6 | +20.2 | -11.3% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Round Robin | 402.3 ± 64.9 | Double DQN (guardrails on) | 198.2 ± 54.6 | -204.2 | +50.7% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Priority | 259.0 ± 13.7 | Double DQN (guardrails on) | 198.2 ± 54.6 | -60.8 | +23.5% | [Reproduced] |
| Throughput | tasks/s | Higher is better | FCFS | 15.586 ± 0.833 | Double DQN (guardrails on) | 16.216 ± 0.884 | +0.630 | +4.0% | [Reproduced] |
| Throughput | tasks/s | Higher is better | SJF | 16.468 ± 0.956 | Double DQN (guardrails on) | 16.216 ± 0.884 | -0.253 | -1.5% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Round Robin | 14.807 ± 0.892 | Double DQN (guardrails on) | 16.216 ± 0.884 | +1.409 | +9.5% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Priority | 16.154 ± 0.889 | Double DQN (guardrails on) | 16.216 ± 0.884 | +0.061 | +0.4% | [Reproduced] |
| Response time | ms | Lower is better | FCFS | 106.9 ± 10.6 | Double DQN (guardrails on) | 27.7 ± 10.3 | -79.1 | +74.0% | [Reproduced] |
| Response time | ms | Lower is better | SJF | 52.8 ± 5.4 | Double DQN (guardrails on) | 27.7 ± 10.3 | -25.0 | +47.4% | [Reproduced] |
| Response time | ms | Lower is better | Round Robin | 48.8 ± 7.6 | Double DQN (guardrails on) | 27.7 ± 10.3 | -21.0 | +43.1% | [Reproduced] |
| Response time | ms | Lower is better | Priority | 104.2 ± 11.0 | Double DQN (guardrails on) | 27.7 ± 10.3 | -76.4 | +73.4% | [Reproduced] |
| Waiting time | ms | Lower is better | FCFS | 247.7 ± 21.3 | Double DQN (guardrails on) | 113.4 ± 53.2 | -134.3 | +54.2% | [Reproduced] |
| Waiting time | ms | Lower is better | SJF | 94.9 ± 7.3 | Double DQN (guardrails on) | 113.4 ± 53.2 | +18.5 | -19.5% | [Reproduced] |
| Waiting time | ms | Lower is better | Round Robin | 311.9 ± 63.5 | Double DQN (guardrails on) | 113.4 ± 53.2 | -198.5 | +63.7% | [Reproduced] |
| Waiting time | ms | Lower is better | Priority | 175.5 ± 15.1 | Double DQN (guardrails on) | 113.4 ± 53.2 | -62.1 | +35.4% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | FCFS | 0.3606 ± 0.0364 | Double DQN (guardrails on) | 0.0828 ± 0.0270 | -0.2778 | +77.0% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | SJF | 0.1539 ± 0.0174 | Double DQN (guardrails on) | 0.0828 ± 0.0270 | -0.0711 | +46.2% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Round Robin | 0.3141 ± 0.0399 | Double DQN (guardrails on) | 0.0828 ± 0.0270 | -0.2313 | +73.6% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Priority | 0.2621 ± 0.0245 | Double DQN (guardrails on) | 0.0828 ± 0.0270 | -0.1793 | +68.4% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | FCFS | 0.933 ± 0.535 | Double DQN (guardrails on) | 0.567 ± 0.629 | -0.367 | +39.3% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | SJF | 0.227 ± 0.064 | Double DQN (guardrails on) | 0.567 ± 0.629 | +0.340 | -150.0% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Round Robin | 0.000 ± 0.000 | Double DQN (guardrails on) | 0.567 ± 0.629 | +0.567 | N/A — baseline zero / not comparable | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Priority | 1.060 ± 0.435 | Double DQN (guardrails on) | 0.567 ± 0.629 | -0.493 | +46.5% | [Reproduced] |

- Starvation count, Round Robin → Double DQN (guardrails on): Before is zero or near zero (|Before| <= 0.05 tasks per episode), so a percentage would be meaningless.

Improvement % convention: a positive value always means better after. For higher-is-better metrics, Improvement % = (After − Before) / |Before| × 100; for lower-is-better metrics, Improvement % = (Before − After) / |Before| × 100. Delta = After − Before in the metric's own unit. Both are computed from unrounded means measured under the same config, dataset, workload and seeds; a regression shows as a negative Improvement %.
