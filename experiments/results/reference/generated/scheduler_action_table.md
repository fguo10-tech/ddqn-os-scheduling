| Index | Family | Slot | Time slice (ms) / priority delta | Meaning | Masked when |
|---:|---|---:|---|---|---|
| 0 | DISPATCH | 0 | 10.0 | run slot 0 for 10.0 ms | slot 0 is empty |
| 1 | DISPATCH | 0 | 40.0 | run slot 0 for 40.0 ms | slot 0 is empty |
| 2 | DISPATCH | 0 | until burst ends | run slot 0 until its burst ends | slot 0 is empty |
| 3 | DISPATCH | 1 | 10.0 | run slot 1 for 10.0 ms | slot 1 is empty |
| 4 | DISPATCH | 1 | 40.0 | run slot 1 for 40.0 ms | slot 1 is empty |
| 5 | DISPATCH | 1 | until burst ends | run slot 1 until its burst ends | slot 1 is empty |
| 6 | DISPATCH | 2 | 10.0 | run slot 2 for 10.0 ms | slot 2 is empty |
| 7 | DISPATCH | 2 | 40.0 | run slot 2 for 40.0 ms | slot 2 is empty |
| 8 | DISPATCH | 2 | until burst ends | run slot 2 until its burst ends | slot 2 is empty |
| 9 | DISPATCH | 3 | 10.0 | run slot 3 for 10.0 ms | slot 3 is empty |
| 10 | DISPATCH | 3 | 40.0 | run slot 3 for 40.0 ms | slot 3 is empty |
| 11 | DISPATCH | 3 | until burst ends | run slot 3 until its burst ends | slot 3 is empty |
| 12 | DISPATCH | 4 | 10.0 | run slot 4 for 10.0 ms | slot 4 is empty |
| 13 | DISPATCH | 4 | 40.0 | run slot 4 for 40.0 ms | slot 4 is empty |
| 14 | DISPATCH | 4 | until burst ends | run slot 4 until its burst ends | slot 4 is empty |
| 15 | DISPATCH | 5 | 10.0 | run slot 5 for 10.0 ms | slot 5 is empty |
| 16 | DISPATCH | 5 | 40.0 | run slot 5 for 40.0 ms | slot 5 is empty |
| 17 | DISPATCH | 5 | until burst ends | run slot 5 until its burst ends | slot 5 is empty |
| 18 | DISPATCH | 6 | 10.0 | run slot 6 for 10.0 ms | slot 6 is empty |
| 19 | DISPATCH | 6 | 40.0 | run slot 6 for 40.0 ms | slot 6 is empty |
| 20 | DISPATCH | 6 | until burst ends | run slot 6 until its burst ends | slot 6 is empty |
| 21 | DISPATCH | 7 | 10.0 | run slot 7 for 10.0 ms | slot 7 is empty |
| 22 | DISPATCH | 7 | 40.0 | run slot 7 for 40.0 ms | slot 7 is empty |
| 23 | DISPATCH | 7 | until burst ends | run slot 7 until its burst ends | slot 7 is empty |
| 24 | DISPATCH | 8 | 10.0 | run slot 8 for 10.0 ms | slot 8 is empty |
| 25 | DISPATCH | 8 | 40.0 | run slot 8 for 40.0 ms | slot 8 is empty |
| 26 | DISPATCH | 8 | until burst ends | run slot 8 until its burst ends | slot 8 is empty |
| 27 | DISPATCH | 9 | 10.0 | run slot 9 for 10.0 ms | slot 9 is empty |
| 28 | DISPATCH | 9 | 40.0 | run slot 9 for 40.0 ms | slot 9 is empty |
| 29 | DISPATCH | 9 | until burst ends | run slot 9 until its burst ends | slot 9 is empty |
| 30 | PRIORITY | 0 | +1 | raise priority of slot 0 | slot 0 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 31 | PRIORITY | 0 | -1 | lower priority of slot 0 | slot 0 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 32 | PRIORITY | 1 | +1 | raise priority of slot 1 | slot 1 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 33 | PRIORITY | 1 | -1 | lower priority of slot 1 | slot 1 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 34 | PRIORITY | 2 | +1 | raise priority of slot 2 | slot 2 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 35 | PRIORITY | 2 | -1 | lower priority of slot 2 | slot 2 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 36 | PRIORITY | 3 | +1 | raise priority of slot 3 | slot 3 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 37 | PRIORITY | 3 | -1 | lower priority of slot 3 | slot 3 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 38 | PRIORITY | 4 | +1 | raise priority of slot 4 | slot 4 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 39 | PRIORITY | 4 | -1 | lower priority of slot 4 | slot 4 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 40 | PRIORITY | 5 | +1 | raise priority of slot 5 | slot 5 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 41 | PRIORITY | 5 | -1 | lower priority of slot 5 | slot 5 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 42 | PRIORITY | 6 | +1 | raise priority of slot 6 | slot 6 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 43 | PRIORITY | 6 | -1 | lower priority of slot 6 | slot 6 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 44 | PRIORITY | 7 | +1 | raise priority of slot 7 | slot 7 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 45 | PRIORITY | 7 | -1 | lower priority of slot 7 | slot 7 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 46 | PRIORITY | 8 | +1 | raise priority of slot 8 | slot 8 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 47 | PRIORITY | 8 | -1 | lower priority of slot 8 | slot 8 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 48 | PRIORITY | 9 | +1 | raise priority of slot 9 | slot 9 is empty; or the task's priority + offset is already 3 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
| 49 | PRIORITY | 9 | -1 | lower priority of slot 9 | slot 9 is empty; or the task's priority + offset is already 0 (range 0..3, `machine.num_priority_levels`); or 2 consecutive priority actions were taken since the last dispatch (`actions.max_priority_adjusts_per_dispatch`) |
