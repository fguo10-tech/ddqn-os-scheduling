Source label: [Reproduced]. Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run). One table per load profile. Values are mean ± sample standard deviation over 5 seeds.

**Load profile: light**

| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value | Delta (absolute) | Improvement % | Source Label |
|---|---|---|---|---|---|---|---|---|---|
| Completion / turnaround time | ms | Lower is better | FCFS | 225.4 ± 74.5 | Double DQN (guardrails on) | 134.9 ± 41.6 | -90.5 | +40.2% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | SJF | 157.2 ± 33.1 | Double DQN (guardrails on) | 134.9 ± 41.6 | -22.4 | +14.2% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Round Robin | 249.6 ± 89.5 | Double DQN (guardrails on) | 134.9 ± 41.6 | -114.8 | +46.0% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Priority | 164.5 ± 40.8 | Double DQN (guardrails on) | 134.9 ± 41.6 | -29.6 | +18.0% | [Reproduced] |
| Throughput | tasks/s | Higher is better | FCFS | 8.714 ± 1.225 | Double DQN (guardrails on) | 8.747 ± 1.153 | +0.033 | +0.4% | [Reproduced] |
| Throughput | tasks/s | Higher is better | SJF | 8.757 ± 1.120 | Double DQN (guardrails on) | 8.747 ± 1.153 | -0.010 | -0.1% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Round Robin | 8.311 ± 1.269 | Double DQN (guardrails on) | 8.747 ± 1.153 | +0.436 | +5.2% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Priority | 8.759 ± 1.155 | Double DQN (guardrails on) | 8.747 ± 1.153 | -0.012 | -0.1% | [Reproduced] |
| Response time | ms | Lower is better | FCFS | 74.3 ± 30.4 | Double DQN (guardrails on) | 16.5 ± 11.8 | -57.7 | +77.7% | [Reproduced] |
| Response time | ms | Lower is better | SJF | 30.7 ± 5.9 | Double DQN (guardrails on) | 16.5 ± 11.8 | -14.1 | +46.1% | [Reproduced] |
| Response time | ms | Lower is better | Round Robin | 19.9 ± 6.6 | Double DQN (guardrails on) | 16.5 ± 11.8 | -3.3 | +16.7% | [Reproduced] |
| Response time | ms | Lower is better | Priority | 34.4 ± 9.1 | Double DQN (guardrails on) | 16.5 ± 11.8 | -17.9 | +51.9% | [Reproduced] |
| Waiting time | ms | Lower is better | FCFS | 136.8 ± 64.5 | Double DQN (guardrails on) | 48.5 ± 32.1 | -88.3 | +64.5% | [Reproduced] |
| Waiting time | ms | Lower is better | SJF | 70.2 ± 24.2 | Double DQN (guardrails on) | 48.5 ± 32.1 | -21.7 | +30.9% | [Reproduced] |
| Waiting time | ms | Lower is better | Round Robin | 150.1 ± 74.3 | Double DQN (guardrails on) | 48.5 ± 32.1 | -101.6 | +67.7% | [Reproduced] |
| Waiting time | ms | Lower is better | Priority | 77.2 ± 31.6 | Double DQN (guardrails on) | 48.5 ± 32.1 | -28.6 | +37.1% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | FCFS | 0.3094 ± 0.0374 | Double DQN (guardrails on) | 0.0263 ± 0.0150 | -0.2831 | +91.5% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | SJF | 0.2524 ± 0.0306 | Double DQN (guardrails on) | 0.0263 ± 0.0150 | -0.2261 | +89.6% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Round Robin | 0.2260 ± 0.0703 | Double DQN (guardrails on) | 0.0263 ± 0.0150 | -0.1997 | +88.4% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Priority | 0.2640 ± 0.0326 | Double DQN (guardrails on) | 0.0263 ± 0.0150 | -0.2377 | +90.0% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | FCFS | 0.640 ± 1.266 | Double DQN (guardrails on) | 0.240 ± 0.537 | -0.400 | +62.5% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | SJF | 0.340 ± 0.329 | Double DQN (guardrails on) | 0.240 ± 0.537 | -0.100 | +29.4% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Round Robin | 0.000 ± 0.000 | Double DQN (guardrails on) | 0.240 ± 0.537 | +0.240 | N/A — baseline zero / not comparable | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Priority | 0.200 ± 0.292 | Double DQN (guardrails on) | 0.240 ± 0.537 | +0.040 | -20.0% | [Reproduced] |

- Starvation count, Round Robin → Double DQN (guardrails on): Before is zero or near zero (|Before| <= 0.05 tasks per episode), so a percentage would be meaningless.

**Load profile: medium**

| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value | Delta (absolute) | Improvement % | Source Label |
|---|---|---|---|---|---|---|---|---|---|
| Completion / turnaround time | ms | Lower is better | FCFS | 530.7 ± 71.7 | Double DQN (guardrails on) | 186.9 ± 34.5 | -343.8 | +64.8% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | SJF | 221.9 ± 25.9 | Double DQN (guardrails on) | 186.9 ± 34.5 | -35.0 | +15.8% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Round Robin | 693.9 ± 238.7 | Double DQN (guardrails on) | 186.9 ± 34.5 | -507.0 | +73.1% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Priority | 248.9 ± 20.4 | Double DQN (guardrails on) | 186.9 ± 34.5 | -62.0 | +24.9% | [Reproduced] |
| Throughput | tasks/s | Higher is better | FCFS | 12.018 ± 0.789 | Double DQN (guardrails on) | 12.553 ± 1.131 | +0.535 | +4.5% | [Reproduced] |
| Throughput | tasks/s | Higher is better | SJF | 12.648 ± 0.784 | Double DQN (guardrails on) | 12.553 ± 1.131 | -0.095 | -0.7% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Round Robin | 10.361 ± 0.507 | Double DQN (guardrails on) | 12.553 ± 1.131 | +2.192 | +21.2% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Priority | 12.617 ± 0.841 | Double DQN (guardrails on) | 12.553 ± 1.131 | -0.065 | -0.5% | [Reproduced] |
| Response time | ms | Lower is better | FCFS | 228.7 ± 58.0 | Double DQN (guardrails on) | 29.7 ± 4.7 | -199.0 | +87.0% | [Reproduced] |
| Response time | ms | Lower is better | SJF | 60.6 ± 8.9 | Double DQN (guardrails on) | 29.7 ± 4.7 | -30.9 | +51.0% | [Reproduced] |
| Response time | ms | Lower is better | Round Robin | 58.4 ± 17.3 | Double DQN (guardrails on) | 29.7 ± 4.7 | -28.7 | +49.1% | [Reproduced] |
| Response time | ms | Lower is better | Priority | 79.5 ± 13.0 | Double DQN (guardrails on) | 29.7 ± 4.7 | -49.8 | +62.7% | [Reproduced] |
| Waiting time | ms | Lower is better | FCFS | 435.6 ± 72.7 | Double DQN (guardrails on) | 100.5 ± 28.7 | -335.1 | +76.9% | [Reproduced] |
| Waiting time | ms | Lower is better | SJF | 134.9 ± 23.7 | Double DQN (guardrails on) | 100.5 ± 28.7 | -34.4 | +25.5% | [Reproduced] |
| Waiting time | ms | Lower is better | Round Robin | 568.6 ± 227.6 | Double DQN (guardrails on) | 100.5 ± 28.7 | -468.1 | +82.3% | [Reproduced] |
| Waiting time | ms | Lower is better | Priority | 161.3 ± 21.7 | Double DQN (guardrails on) | 100.5 ± 28.7 | -60.8 | +37.7% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | FCFS | 0.5480 ± 0.0698 | Double DQN (guardrails on) | 0.0728 ± 0.0284 | -0.4752 | +86.7% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | SJF | 0.3905 ± 0.0500 | Double DQN (guardrails on) | 0.0728 ± 0.0284 | -0.3177 | +81.4% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Round Robin | 0.4828 ± 0.0923 | Double DQN (guardrails on) | 0.0728 ± 0.0284 | -0.4100 | +84.9% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Priority | 0.4460 ± 0.0551 | Double DQN (guardrails on) | 0.0728 ± 0.0284 | -0.3732 | +83.7% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | FCFS | 3.600 ± 1.283 | Double DQN (guardrails on) | 0.460 ± 0.602 | -3.140 | +87.2% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | SJF | 0.900 ± 0.224 | Double DQN (guardrails on) | 0.460 ± 0.602 | -0.440 | +48.9% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Round Robin | 0.000 ± 0.000 | Double DQN (guardrails on) | 0.460 ± 0.602 | +0.460 | N/A — baseline zero / not comparable | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Priority | 0.940 ± 0.055 | Double DQN (guardrails on) | 0.460 ± 0.602 | -0.480 | +51.1% | [Reproduced] |

- Starvation count, Round Robin → Double DQN (guardrails on): Before is zero or near zero (|Before| <= 0.05 tasks per episode), so a percentage would be meaningless.

**Load profile: heavy**

| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value | Delta (absolute) | Improvement % | Source Label |
|---|---|---|---|---|---|---|---|---|---|
| Completion / turnaround time | ms | Lower is better | FCFS | 1012.5 ± 129.3 | Double DQN (guardrails on) | 477.3 ± 167.8 | -535.2 | +52.9% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | SJF | 298.0 ± 35.8 | Double DQN (guardrails on) | 477.3 ± 167.8 | +179.3 | -60.2% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Round Robin | 1005.9 ± 318.3 | Double DQN (guardrails on) | 477.3 ± 167.8 | -528.6 | +52.6% | [Reproduced] |
| Completion / turnaround time | ms | Lower is better | Priority | 367.0 ± 74.9 | Double DQN (guardrails on) | 477.3 ± 167.8 | +110.3 | -30.1% | [Reproduced] |
| Throughput | tasks/s | Higher is better | FCFS | 13.002 ± 1.013 | Double DQN (guardrails on) | 14.095 ± 1.146 | +1.093 | +8.4% | [Reproduced] |
| Throughput | tasks/s | Higher is better | SJF | 14.497 ± 1.375 | Double DQN (guardrails on) | 14.095 ± 1.146 | -0.401 | -2.8% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Round Robin | 10.454 ± 1.072 | Double DQN (guardrails on) | 14.095 ± 1.146 | +3.641 | +34.8% | [Reproduced] |
| Throughput | tasks/s | Higher is better | Priority | 13.925 ± 1.788 | Double DQN (guardrails on) | 14.095 ± 1.146 | +0.170 | +1.2% | [Reproduced] |
| Response time | ms | Lower is better | FCFS | 472.1 ± 69.9 | Double DQN (guardrails on) | 124.5 ± 82.6 | -347.6 | +73.6% | [Reproduced] |
| Response time | ms | Lower is better | SJF | 98.1 ± 16.1 | Double DQN (guardrails on) | 124.5 ± 82.6 | +26.4 | -26.9% | [Reproduced] |
| Response time | ms | Lower is better | Round Robin | 101.4 ± 19.7 | Double DQN (guardrails on) | 124.5 ± 82.6 | +23.1 | -22.8% | [Reproduced] |
| Response time | ms | Lower is better | Priority | 126.6 ± 22.3 | Double DQN (guardrails on) | 124.5 ± 82.6 | -2.1 | +1.7% | [Reproduced] |
| Waiting time | ms | Lower is better | FCFS | 906.3 ± 123.1 | Double DQN (guardrails on) | 377.8 ± 161.5 | -528.5 | +58.3% | [Reproduced] |
| Waiting time | ms | Lower is better | SJF | 207.8 ± 29.1 | Double DQN (guardrails on) | 377.8 ± 161.5 | +170.0 | -81.8% | [Reproduced] |
| Waiting time | ms | Lower is better | Round Robin | 868.3 ± 301.6 | Double DQN (guardrails on) | 377.8 ± 161.5 | -490.5 | +56.5% | [Reproduced] |
| Waiting time | ms | Lower is better | Priority | 272.9 ± 63.2 | Double DQN (guardrails on) | 377.8 ± 161.5 | +104.9 | -38.5% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | FCFS | 0.7025 ± 0.0422 | Double DQN (guardrails on) | 0.1429 ± 0.0266 | -0.5596 | +79.7% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | SJF | 0.4829 ± 0.0141 | Double DQN (guardrails on) | 0.1429 ± 0.0266 | -0.3400 | +70.4% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Round Robin | 0.6598 ± 0.0457 | Double DQN (guardrails on) | 0.1429 ± 0.0266 | -0.5169 | +78.3% | [Reproduced] |
| SLO violation rate | fraction of tasks | Lower is better | Priority | 0.5643 ± 0.0194 | Double DQN (guardrails on) | 0.1429 ± 0.0266 | -0.4214 | +74.7% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | FCFS | 10.780 ± 3.038 | Double DQN (guardrails on) | 3.040 ± 1.050 | -7.740 | +71.8% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | SJF | 1.940 ± 0.351 | Double DQN (guardrails on) | 3.040 ± 1.050 | +1.100 | -56.7% | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Round Robin | 0.000 ± 0.000 | Double DQN (guardrails on) | 3.040 ± 1.050 | +3.040 | N/A — baseline zero / not comparable | [Reproduced] |
| Starvation count | tasks per episode | Lower is better | Priority | 2.440 ± 0.723 | Double DQN (guardrails on) | 3.040 ± 1.050 | +0.600 | -24.6% | [Reproduced] |

- Starvation count, Round Robin → Double DQN (guardrails on): Before is zero or near zero (|Before| <= 0.05 tasks per episode), so a percentage would be meaningless.

Improvement % convention: a positive value always means better after. For higher-is-better metrics, Improvement % = (After − Before) / |Before| × 100; for lower-is-better metrics, Improvement % = (Before − After) / |Before| × 100. Delta = After − Before in the metric's own unit. Both are computed from unrounded means measured under the same config, dataset, workload and seeds; a regression shows as a negative Improvement %.
