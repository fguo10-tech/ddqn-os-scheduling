Load profiles pooled:

- **Completion / turnaround time** (lower is better): Double DQN (guardrails on) 198.2 ± 54.6 ms; best baseline SJF 178.0 ± 8.0 ms; Improvement -11.3% (worse). Better than 3 of 4 baselines with a computable percentage (FCFS, Round Robin, Priority). [Reproduced]
- **Throughput** (higher is better): Double DQN (guardrails on) 16.216 ± 0.884 tasks/s; best baseline SJF 16.468 ± 0.956 tasks/s; Improvement -1.5% (worse). Better than 3 of 4 baselines with a computable percentage (FCFS, Round Robin, Priority). [Reproduced]
- **Response time** (lower is better): Double DQN (guardrails on) 27.7 ± 10.3 ms; best baseline Round Robin 48.8 ± 7.6 ms; Improvement +43.1% (better). Better than 4 of 4 baselines with a computable percentage (FCFS, SJF, Round Robin, Priority). [Reproduced]
- **Waiting time** (lower is better): Double DQN (guardrails on) 113.4 ± 53.2 ms; best baseline SJF 94.9 ± 7.3 ms; Improvement -19.5% (worse). Better than 3 of 4 baselines with a computable percentage (FCFS, Round Robin, Priority). [Reproduced]
- **SLO violation rate** (lower is better): Double DQN (guardrails on) 0.0828 ± 0.0270 fraction of tasks; best baseline SJF 0.1539 ± 0.0174 fraction of tasks; Improvement +46.2% (better). Better than 4 of 4 baselines with a computable percentage (FCFS, SJF, Round Robin, Priority). [Reproduced]
- **Starvation count** (lower is better): Double DQN (guardrails on) 0.567 ± 0.629 tasks per episode; best baseline Round Robin 0.000 ± 0.000 tasks per episode; no percentage (N/A — baseline zero / not comparable). Better than 2 of 3 baselines with a computable percentage (FCFS, Priority). [Reproduced]
- Against the best baseline per metric, Double DQN (guardrails on) is better on 2 of 5 metrics with a computable percentage. [Reproduced]

Completion / turnaround time by load profile:

- light: Double DQN (guardrails on) 115.7 ± 3.4 ms; best baseline SJF 133.4 ± 6.0 ms; Improvement +13.3% (better). [Reproduced]
- medium: Double DQN (guardrails on) 156.6 ± 14.0 ms; best baseline SJF 181.4 ± 8.7 ms; Improvement +13.7% (better). [Reproduced]
- heavy: Double DQN (guardrails on) 322.3 ± 159.3 ms; best baseline SJF 219.3 ± 10.6 ms; Improvement -47.0% (worse). [Reproduced]

References that are not Before methods (pooled):

- SRTF (preemptive reference) — Completion / turnaround time: reference 139.5 ± 5.4 versus 198.2 ± 54.6 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 42.0% worse than the reference); Response time: reference 26.6 ± 4.7 versus 27.7 ± 10.3 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 4.5% worse than the reference); SLO violation rate: reference 0.0550 ± 0.0135 versus 0.0828 ± 0.0270 fraction of tasks for Double DQN (guardrails on) (Double DQN (guardrails on) is 50.6% worse than the reference). [Reproduced]
  - light: completion / turnaround time reference 109.2 ± 1.4 versus 115.7 ± 3.4 ms (Double DQN (guardrails on) is 6.0% worse than the reference).
  - medium: completion / turnaround time reference 136.0 ± 6.3 versus 156.6 ± 14.0 ms (Double DQN (guardrails on) is 15.1% worse than the reference).
  - heavy: completion / turnaround time reference 173.4 ± 9.9 versus 322.3 ± 159.3 ms (Double DQN (guardrails on) is 85.8% worse than the reference).
- Double DQN (guardrail overrides off) — Completion / turnaround time: reference 185.6 ± 38.7 versus 198.2 ± 54.6 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 6.8% worse than the reference); Response time: reference 27.7 ± 11.5 versus 27.7 ± 10.3 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 0.1% worse than the reference); SLO violation rate: reference 0.0815 ± 0.0279 versus 0.0828 ± 0.0270 fraction of tasks for Double DQN (guardrails on) (Double DQN (guardrails on) is 1.6% worse than the reference). [Reproduced]
  - light: completion / turnaround time reference 115.7 ± 3.4 versus 115.7 ± 3.4 ms (Double DQN (guardrails on) is 0.0% worse than the reference).
  - medium: completion / turnaround time reference 156.2 ± 14.4 versus 156.6 ± 14.0 ms (Double DQN (guardrails on) is 0.2% worse than the reference).
  - heavy: completion / turnaround time reference 284.9 ± 109.6 versus 322.3 ± 159.3 ms (Double DQN (guardrails on) is 13.1% worse than the reference).

- Plain throughput differs by at most 11.2% between the five compared methods (pooled). [Reproduced]
