| Index | Name | Description | Normalisation | Constants (from YAML) |
|---:|---|---|---|---|
| 0 | `ready_queue_length` | number of READY tasks | / observation.count_norm | `observation.count_norm` = 10.0; then clipped to ±`observation.clip` = 10 |
| 1 | `blocked_tasks` | number of tasks blocked on I/O | / observation.count_norm | `observation.count_norm` = 10.0; then clipped to ±`observation.clip` = 10 |
| 2 | `free_memory_fraction` | 1 − resident / capacity (negative when over-committed) | clipped to [-1, 1] | then clipped to ±`observation.clip` = 10 |
| 3 | `recent_cpu_utilisation` | exponentially decaying busy fraction | none (already in [0, 1]) | then clipped to ±`observation.clip` = 10 |
| 4 | `ready_current_burst_work` | sum of the remaining current CPU bursts of READY tasks | / (observation.work_norm_ms × observation.count_norm) | `observation.work_norm_ms` = 100.0; `observation.count_norm` = 10.0; then clipped to ±`observation.clip` = 10 |
| 5 | `mean_ready_wait` | mean continuous waiting time of READY tasks | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 6 | `max_ready_wait` | max continuous waiting time of READY tasks | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 7 | `slo_pressure` | fraction of READY tasks with deadline slack below observation.slo_slack_threshold_ms | none (fraction) | then clipped to ±`observation.clip` = 10 |
| 8 | `recent_arrival_rate` | exponentially decaying arrival rate (tasks/s) | / observation.arrival_rate_norm_per_s | `observation.arrival_rate_norm_per_s` = 50.0; then clipped to ±`observation.clip` = 10 |
| 9 | `recent_slo_violation_rate` | late fraction of the last observation.recent_completions completions | none (fraction) | then clipped to ±`observation.clip` = 10 |
| 10 | `priority_adjust_budget` | remaining consecutive priority actions before a dispatch is forced | / actions.max_priority_adjusts_per_dispatch (0 if that is 0) | `actions.max_priority_adjusts_per_dispatch` = 2; then clipped to ±`observation.clip` = 10 |
| 11 | `slot0.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 12 | `slot0.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 13 | `slot0.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 14 | `slot0.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 15 | `slot0.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 16 | `slot0.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 17 | `slot0.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 18 | `slot0.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 19 | `slot0.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 20 | `slot0.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 21 | `slot0.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 22 | `slot1.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 23 | `slot1.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 24 | `slot1.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 25 | `slot1.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 26 | `slot1.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 27 | `slot1.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 28 | `slot1.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 29 | `slot1.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 30 | `slot1.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 31 | `slot1.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 32 | `slot1.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 33 | `slot2.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 34 | `slot2.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 35 | `slot2.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 36 | `slot2.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 37 | `slot2.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 38 | `slot2.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 39 | `slot2.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 40 | `slot2.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 41 | `slot2.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 42 | `slot2.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 43 | `slot2.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 44 | `slot3.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 45 | `slot3.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 46 | `slot3.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 47 | `slot3.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 48 | `slot3.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 49 | `slot3.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 50 | `slot3.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 51 | `slot3.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 52 | `slot3.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 53 | `slot3.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 54 | `slot3.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 55 | `slot4.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 56 | `slot4.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 57 | `slot4.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 58 | `slot4.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 59 | `slot4.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 60 | `slot4.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 61 | `slot4.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 62 | `slot4.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 63 | `slot4.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 64 | `slot4.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 65 | `slot4.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 66 | `slot5.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 67 | `slot5.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 68 | `slot5.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 69 | `slot5.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 70 | `slot5.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 71 | `slot5.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 72 | `slot5.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 73 | `slot5.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 74 | `slot5.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 75 | `slot5.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 76 | `slot5.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 77 | `slot6.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 78 | `slot6.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 79 | `slot6.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 80 | `slot6.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 81 | `slot6.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 82 | `slot6.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 83 | `slot6.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 84 | `slot6.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 85 | `slot6.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 86 | `slot6.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 87 | `slot6.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 88 | `slot7.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 89 | `slot7.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 90 | `slot7.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 91 | `slot7.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 92 | `slot7.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 93 | `slot7.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 94 | `slot7.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 95 | `slot7.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 96 | `slot7.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 97 | `slot7.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 98 | `slot7.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 99 | `slot8.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 100 | `slot8.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 101 | `slot8.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 102 | `slot8.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 103 | `slot8.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 104 | `slot8.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 105 | `slot8.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 106 | `slot8.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 107 | `slot8.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 108 | `slot8.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 109 | `slot8.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 110 | `slot9.occupied` | 1 if the slot holds a task (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 111 | `slot9.current_burst_remaining` | remaining time of the current CPU burst (0 if the slot is empty) | / observation.work_norm_ms | `observation.work_norm_ms` = 100.0; then clipped to ±`observation.clip` = 10 |
| 112 | `slot9.memory_fraction` | memory request / capacity (0 if the slot is empty) | / machine.memory_capacity_mb | `machine.memory_capacity_mb` = 4096; then clipped to ±`observation.clip` = 10 |
| 113 | `slot9.started` | 1 if the task already holds its memory (0 if the slot is empty) | none | then clipped to ±`observation.clip` = 10 |
| 114 | `slot9.current_wait` | continuous waiting time in the ready queue (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 115 | `slot9.time_in_system` | now − arrival (0 if the slot is empty) | / observation.wait_norm_ms | `observation.wait_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 116 | `slot9.effective_priority` | priority + agent offset + aging boost (0 if the slot is empty) | / (levels − 1 + aging max_boost when aging is on) | divisor = 6 (`machine.num_priority_levels` = 4, `guardrails.aging.max_boost` = 3 when aging is on); then clipped to ±`observation.clip` = 10 |
| 117 | `slot9.deadline_slack` | deadline − now − current burst remaining (− total remaining CPU with the oracle flag) (0 if the slot is empty) | / observation.slack_norm_ms | `observation.slack_norm_ms` = 500.0; then clipped to ±`observation.clip` = 10 |
| 118 | `slot9.type_cpu_bound` | 1 if the task is cpu-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 119 | `slot9.type_memory_bound` | 1 if the task is memory-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
| 120 | `slot9.type_io_bound` | 1 if the task is io-bound (0 if the slot is empty) | none (one-hot) | then clipped to ±`observation.clip` = 10 |
