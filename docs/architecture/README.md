# Architecture diagrams

Four diagrams of the draft research code, each drawn from the code as it is. Every file has one
Mermaid diagram followed by an explanation that names the implementing source files, the
assumptions, the design alternatives considered and what the diagram does not show. Other
documents embed these diagrams through the generated blocks `diagram_*`, which
`experiments/build_results.py` extracts from the first Mermaid block of each file, so the file
names below are fixed.

| File | Generated block | Diagram |
|---|---|---|
| [01-system-overview.md](01-system-overview.md) | `diagram_system_overview` | The scheduler module, the shared `src/common` package and the experiment and reporting layer, with the data flow between them. |
| [02-scheduler-detail.md](02-scheduler-detail.md) | `diagram_scheduler_detail` | Simulator, observation encoding with aging, Double DQN with target network and replay buffer, the override rules inside the environment step, and the baselines that see the whole ready queue. |
| [03-experiment-flow.md](03-experiment-flow.md) | `diagram_experiment_flow` | Configuration, benchmark run, raw CSV, summary, Before / After CSV and chart, generated block, and the documents that include it. |
| [04-deployment-sketch.md](04-deployment-sketch.md) | `diagram_deployment_sketch` | For platform teams: what a platform would supply to the scheduler plugin, what comes back, and which guardrail and fallback react when the model misbehaves. A sketch, not a production integration. |

Read them in order: diagram 1 for the parts of the repository, diagram 2 for one scheduling
decision, diagram 3 for how a result reaches a document, and diagram 4 for what a platform
team would have to build around the research code.

None of the diagrams shows a large-language-model component or an integrated demo, because this
draft implements neither. The LLM-style workload profile (`configs/scheduler_llm_workload.yaml`:
synthetic inference requests and fine-tuning jobs) is a second config that travels the path of
diagram 3; it adds no component to any diagram, and no language model is run. None of the
diagrams shows a result; reproduced values appear only in the generated blocks.
