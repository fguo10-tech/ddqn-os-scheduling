| Method | Metric | Paper-reported | Reproduced (mean ± std) | Notes |
|---|---|---|---|---|
| FCFS | Average completion (turnaround) time | 350 ms [Paper-reported] | 333.3 ± 20.9 ms [Reproduced] | Baseline. |
| FCFS | Throughput | 2.8 tasks/s [Paper-reported] | 15.586 ± 0.833 tasks/s [Reproduced] | Baseline. |
| FCFS | Average response time | 200 ms [Paper-reported] | 106.9 ± 10.6 ms [Reproduced] | Baseline. |
| SJF | Average completion (turnaround) time | 290 ms [Paper-reported] | 178.0 ± 8.0 ms [Reproduced] | Non-preemptive, shortest next CPU burst. |
| SJF | Throughput | 3.1 tasks/s [Paper-reported] | 16.468 ± 0.956 tasks/s [Reproduced] | Non-preemptive, shortest next CPU burst. |
| SJF | Average response time | 170 ms [Paper-reported] | 52.8 ± 5.4 ms [Reproduced] | Non-preemptive, shortest next CPU burst. |
| Round Robin | Average completion (turnaround) time | 310 ms [Paper-reported] | 402.3 ± 64.9 ms [Reproduced] | Quantum set in `configs/scheduler_baselines.yaml`. |
| Round Robin | Throughput | 3 tasks/s [Paper-reported] | 14.807 ± 0.892 tasks/s [Reproduced] | Quantum set in `configs/scheduler_baselines.yaml`. |
| Round Robin | Average response time | 180 ms [Paper-reported] | 48.8 ± 7.6 ms [Reproduced] | Quantum set in `configs/scheduler_baselines.yaml`. |
| Priority | Average completion (turnaround) time | not reported | 259.0 ± 13.7 ms [Reproduced] | Added by this repository. |
| Priority | Throughput | not reported | 16.154 ± 0.889 tasks/s [Reproduced] | Added by this repository. |
| Priority | Average response time | not reported | 104.2 ± 11.0 ms [Reproduced] | Added by this repository. |
| SRTF (preemptive reference) | Average completion (turnaround) time | not reported | 139.5 ± 5.4 ms [Reproduced] | Reference added by this repository: preemptive shortest-remaining-burst-first. |
| SRTF (preemptive reference) | Throughput | not reported | 16.515 ± 0.962 tasks/s [Reproduced] | Reference added by this repository: preemptive shortest-remaining-burst-first. |
| SRTF (preemptive reference) | Average response time | not reported | 26.6 ± 4.7 ms [Reproduced] | Reference added by this repository: preemptive shortest-remaining-burst-first. |
| Double DQN (guardrails on) | Average completion (turnaround) time | 250 ms [Paper-reported] | 198.2 ± 54.6 ms [Reproduced] | Reward with time penalties and a completion bonus; standard Double DQN target; guardrails on. |
| Double DQN (guardrails on) | Throughput | 3.5 tasks/s [Paper-reported] | 16.216 ± 0.884 tasks/s [Reproduced] | Reward with time penalties and a completion bonus; standard Double DQN target; guardrails on. |
| Double DQN (guardrails on) | Average response time | 150 ms [Paper-reported] | 27.7 ± 10.3 ms [Reproduced] | Reward with time penalties and a completion bonus; standard Double DQN target; guardrails on. |

The Paper-reported column is shown for reference only: it comes from a different setup, while the Reproduced column comes from this repository's simulator with the settings in `configs/scheduler_ddqn.yaml` (all three load profiles pooled). No difference between the two columns is computed anywhere in this repository.
