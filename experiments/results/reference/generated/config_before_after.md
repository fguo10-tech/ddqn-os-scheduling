`configs/before_after.yaml` (verbatim; comments carry the provenance tag of every key):

```yaml
# Before / After comparison definitions.
#
# These are reporting settings — which methods are compared, how metrics are named, oriented
# and rounded. They are not model hyperparameters and they change no measured value.
# `python -m experiments.build_results` reads this file and the summary CSV files of the
# reference run, and writes every Before / After table, CSV and chart from them.
#
# Rules applied to every row (implemented in src/common/before_after.py):
#   Delta = After − Before, in the metric's own unit.
#   Higher is better: Improvement % = (After − Before) / |Before| × 100.
#   Lower is better:  Improvement % = (Before − After) / |Before| × 100.
#   |Before| <= near_zero  ->  "N/A — baseline zero / not comparable" instead of a percentage.
#   A side that has not been run -> TBD. A regression is shown as a negative percentage.

# Folder that holds the reference run (relative to the repository root).
reference_root: experiments/results/reference
# Where the generated Markdown blocks are written (injected into the docs by sync_docs).
generated_dir: experiments/results/reference/generated
# Where the Before / After CSV and chart are written, side by side.
before_after_dir: experiments/results/reference/before_after
# Where header-only CSV schema templates are written.
templates_dir: experiments/results/templates

scheduling:
  # Heading used for the table and the chart.
  title: "Scheduling"
  # Summary CSV of the reference run, relative to reference_root.
  summary_csv: scheduler/summary.csv
  # Row group of the headline table: "all" = light, medium and heavy load pooled.
  load_profile: all
  # Load profiles that get their own supplementary table.
  per_load_profiles: [light, medium, heavy]
  # The After method: the Double DQN agent evaluated with guardrails on.
  after_method: ddqn
  # The Before methods: the four textbook baselines.
  before_methods: [fcfs, sjf, round_robin, priority]
  # Shown in grey in the chart for context; never a Before or After method. SRTF is the
  # preemptive shortest-remaining-burst heuristic: the like-for-like reference for an agent
  # that is allowed to preempt, which textbook SJF is not.
  reference_methods: [srtf, ddqn_unguarded]
  # Display names.
  method_labels:
    fcfs: FCFS
    sjf: SJF
    round_robin: Round Robin
    priority: Priority
    ddqn: Double DQN (guardrails on)
    ddqn_unguarded: Double DQN (guardrail overrides off)
    srtf: SRTF (preemptive reference)
  # key = column prefix in summary.csv; near_zero is in the metric's own unit.
  metrics:
    - {key: avg_turnaround_ms, label: Completion / turnaround time, unit: ms, higher_is_better: false, near_zero: 1.0e-9, digits: 1, scale: 1.0}
    - {key: throughput_tasks_per_s, label: Throughput, unit: tasks/s, higher_is_better: true, near_zero: 1.0e-9, digits: 3, scale: 1.0}
    - {key: avg_response_ms, label: Response time, unit: ms, higher_is_better: false, near_zero: 1.0e-9, digits: 1, scale: 1.0}
    - {key: avg_waiting_ms, label: Waiting time, unit: ms, higher_is_better: false, near_zero: 1.0e-9, digits: 1, scale: 1.0}
    # A rate below half a percentage point is treated as "near zero": a ratio of two such
    # numbers is noise, not an improvement.
    - {key: slo_violation_rate, label: SLO violation rate, unit: fraction of tasks, higher_is_better: false, near_zero: 0.005, digits: 4, scale: 1.0}
    # Fewer than one starving task per twenty episodes is treated as "near zero".
    - {key: starvation_count, label: Starvation count, unit: tasks per episode, higher_is_better: false, near_zero: 0.05, digits: 3, scale: 1.0}

# The same benchmark on the LLM-style workload profile (synthetic inference requests and
# fine-tuning jobs; no language model is run). Every key that is not listed here — the load
# profile settings, the After, Before and reference methods, the display names and the metric
# definitions — is taken from the scheduling section above, so both studies are reported with
# exactly the same methods, units, orientation and rounding.
scheduling_llm:
  # Heading used for the tables and the charts.
  title: "Scheduling, LLM-style workload"
  # Config of the workload profile, relative to the repository root.
  workload_config: configs/scheduler_llm_workload.yaml
  # Summary CSV of the reference run of this profile, relative to reference_root.
  summary_csv: scheduler_llm/summary.csv
  # Per-task-class summary CSV of the same run, relative to reference_root.
  class_summary_csv: scheduler_llm/class_summary.csv
  # Display names of the task classes, in the order of the tables.
  class_labels:
    inference_request: Inference requests
    finetune_job: Fine-tuning jobs
  # Metrics reported per task class: key = a metric of the scheduling section (its unit,
  # orientation, near-zero rule and rounding are reused); label = short name used next to the
  # class name.
  class_metrics:
    - {key: avg_turnaround_ms, label: turnaround time}
    - {key: avg_response_ms, label: response time}
    - {key: slo_violation_rate, label: SLO violation rate}
  # Post hoc ablation of this study: one variant of the profile, run after the reference results
  # had been seen, to check one explanation of them. The three keys below are the reading rule;
  # they were written down before the variant was run and were not changed afterwards.
  ablation:
    # Name of the variant in the `ablations:` section of workload_config; its run is read from
    # <folder of summary_csv>/ablations/<name>/.
    name: starvation_bounded_slice
    # Load profile on which the rule is read: the one where the starvation override fires most.
    check_load_profile: heavy
    # The explanation counts as supported on a quantity (turnaround, tasks waiting past the
    # starvation threshold) when the gap between the agent with the override rules on and the
    # same network with them off is, in the variant, smaller than this fraction of the same gap
    # in the reference run. Supported on both quantities: "supported"; on one: "partly
    # supported"; on none: "not supported".
    max_gap_ratio: 0.5
```
