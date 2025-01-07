Workload: the LLM-style profile of `configs/scheduler_llm_workload.yaml` (synthetic inference requests and fine-tuning jobs on the simulated node; no language model is run).

Load profiles pooled:

- **Completion / turnaround time** (lower is better): Double DQN (guardrails on) 266.4 ± 58.1 ms; best baseline SJF 225.7 ± 27.3 ms; Improvement -18.0% (worse). Better than 2 of 4 baselines with a computable percentage (FCFS, Round Robin). [Reproduced]
- **Throughput** (higher is better): Double DQN (guardrails on) 11.798 ± 0.618 tasks/s; best baseline SJF 11.967 ± 0.636 tasks/s; Improvement -1.4% (worse). Better than 3 of 4 baselines with a computable percentage (FCFS, Round Robin, Priority). [Reproduced]
- **Response time** (lower is better): Double DQN (guardrails on) 56.9 ± 30.6 ms; best baseline Round Robin 59.9 ± 7.5 ms; Improvement +5.0% (better). Better than 4 of 4 baselines with a computable percentage (FCFS, SJF, Round Robin, Priority). [Reproduced]
- **Waiting time** (lower is better): Double DQN (guardrails on) 175.6 ± 53.7 ms; best baseline SJF 137.6 ± 22.3 ms; Improvement -27.6% (worse). Better than 2 of 4 baselines with a computable percentage (FCFS, Round Robin). [Reproduced]
- **SLO violation rate** (lower is better): Double DQN (guardrails on) 0.0807 ± 0.0024 fraction of tasks; best baseline SJF 0.3752 ± 0.0269 fraction of tasks; Improvement +78.5% (better). Better than 4 of 4 baselines with a computable percentage (FCFS, SJF, Round Robin, Priority). [Reproduced]
- **Starvation count** (lower is better): Double DQN (guardrails on) 1.247 ± 0.371 tasks per episode; best baseline Round Robin 0.000 ± 0.000 tasks per episode; no percentage (N/A — baseline zero / not comparable). Better than 1 of 3 baselines with a computable percentage (FCFS). [Reproduced]
- Against the best baseline per metric, Double DQN (guardrails on) is better on 2 of 5 metrics with a computable percentage. [Reproduced]

Completion / turnaround time by load profile:

- light: Double DQN (guardrails on) 134.9 ± 41.6 ms; best baseline SJF 157.2 ± 33.1 ms; Improvement +14.2% (better). [Reproduced]
- medium: Double DQN (guardrails on) 186.9 ± 34.5 ms; best baseline SJF 221.9 ± 25.9 ms; Improvement +15.8% (better). [Reproduced]
- heavy: Double DQN (guardrails on) 477.3 ± 167.8 ms; best baseline SJF 298.0 ± 35.8 ms; Improvement -60.2% (worse). [Reproduced]

References that are not Before methods (pooled):

- SRTF (preemptive reference) — Completion / turnaround time: reference 188.6 ± 18.1 versus 266.4 ± 58.1 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 41.2% worse than the reference); Response time: reference 31.3 ± 5.0 versus 56.9 ± 30.6 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 82.0% worse than the reference); SLO violation rate: reference 0.0554 ± 0.0122 versus 0.0807 ± 0.0024 fraction of tasks for Double DQN (guardrails on) (Double DQN (guardrails on) is 45.5% worse than the reference). [Reproduced]
  - light: completion / turnaround time reference 132.8 ± 32.0 versus 134.9 ± 41.6 ms (Double DQN (guardrails on) is 1.5% worse than the reference).
  - medium: completion / turnaround time reference 183.4 ± 14.5 versus 186.9 ± 34.5 ms (Double DQN (guardrails on) is 1.9% worse than the reference).
  - heavy: completion / turnaround time reference 249.5 ± 29.3 versus 477.3 ± 167.8 ms (Double DQN (guardrails on) is 91.3% worse than the reference).
- Double DQN (guardrail overrides off) — Completion / turnaround time: reference 214.7 ± 44.1 versus 266.4 ± 58.1 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 24.1% worse than the reference); Response time: reference 32.7 ± 7.2 versus 56.9 ± 30.6 ms for Double DQN (guardrails on) (Double DQN (guardrails on) is 74.1% worse than the reference); SLO violation rate: reference 0.0731 ± 0.0099 versus 0.0807 ± 0.0024 fraction of tasks for Double DQN (guardrails on) (Double DQN (guardrails on) is 10.4% worse than the reference). [Reproduced]
  - light: completion / turnaround time reference 129.6 ± 30.4 versus 134.9 ± 41.6 ms (Double DQN (guardrails on) is 4.1% worse than the reference).
  - medium: completion / turnaround time reference 175.0 ± 18.3 versus 186.9 ± 34.5 ms (Double DQN (guardrails on) is 6.8% worse than the reference).
  - heavy: completion / turnaround time reference 339.5 ± 129.8 versus 477.3 ± 167.8 ms (Double DQN (guardrails on) is 40.6% worse than the reference).

- Plain throughput differs by at most 23.3% between the five compared methods (pooled). [Reproduced]

Per task class (load profiles pooled, best baseline on each metric):

- **Inference requests: turnaround time** (lower is better): Double DQN (guardrails on) 98.5 ± 53.2 ms; best baseline SJF 83.5 ± 6.1 ms; Improvement -17.9% (worse). [Reproduced]
- **Inference requests: response time** (lower is better): Double DQN (guardrails on) 41.5 ± 32.4 ms; best baseline SJF 40.8 ± 5.4 ms; Improvement -1.9% (worse). [Reproduced]
- **Inference requests: SLO violation rate** (lower is better): Double DQN (guardrails on) 0.0759 ± 0.0038 fraction of tasks; best baseline SJF 0.4274 ± 0.0279 fraction of tasks; Improvement +82.2% (better). [Reproduced]
- **Fine-tuning jobs: turnaround time** (lower is better): Double DQN (guardrails on) 1167.8 ± 66.5 ms; best baseline SJF 1005.2 ± 104.9 ms; Improvement -16.2% (worse). [Reproduced]
- **Fine-tuning jobs: response time** (lower is better): Double DQN (guardrails on) 143.8 ± 40.2 ms; best baseline Round Robin 46.1 ± 7.9 ms; Improvement -212.1% (worse). [Reproduced]
- **Fine-tuning jobs: SLO violation rate** (lower is better): Double DQN (guardrails on) 0.1011 ± 0.0131 fraction of tasks; best baseline SJF 0.0786 ± 0.0262 fraction of tasks; Improvement -28.6% (worse). [Reproduced]
- Against the best baseline per class and metric, Double DQN (guardrails on) is better in 1 of 6 comparisons with a computable percentage. [Reproduced]

References that are not Before methods, per task class (pooled):

- SRTF (preemptive reference), inference requests: turnaround time 39.7 ± 1.9 versus 98.5 ± 53.2 ms for Double DQN (guardrails on); response time 8.5 ± 1.6 versus 41.5 ± 32.4 ms for Double DQN (guardrails on); SLO violation rate 0.0492 ± 0.0121 versus 0.0759 ± 0.0038 fraction of tasks for Double DQN (guardrails on). [Reproduced]
- SRTF (preemptive reference), fine-tuning jobs: turnaround time 1006.1 ± 64.4 versus 1167.8 ± 66.5 ms for Double DQN (guardrails on); response time 147.0 ± 25.2 versus 143.8 ± 40.2 ms for Double DQN (guardrails on); SLO violation rate 0.0832 ± 0.0133 versus 0.1011 ± 0.0131 fraction of tasks for Double DQN (guardrails on). [Reproduced]
- Double DQN (guardrail overrides off), inference requests: turnaround time 57.2 ± 28.2 versus 98.5 ± 53.2 ms for Double DQN (guardrails on); response time 11.7 ± 5.5 versus 41.5 ± 32.4 ms for Double DQN (guardrails on); SLO violation rate 0.0694 ± 0.0109 versus 0.0759 ± 0.0038 fraction of tasks for Double DQN (guardrails on). [Reproduced]
- Double DQN (guardrail overrides off), fine-tuning jobs: turnaround time 1079.9 ± 80.3 versus 1167.8 ± 66.5 ms for Double DQN (guardrails on); response time 143.2 ± 35.4 versus 143.8 ± 40.2 ms for Double DQN (guardrails on); SLO violation rate 0.0882 ± 0.0165 versus 0.1011 ± 0.0131 fraction of tasks for Double DQN (guardrails on). [Reproduced]
