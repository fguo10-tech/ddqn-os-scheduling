Every value in this table is read from `configs/scheduler_llm_workload.yaml`, where each key carries the tag `[Assumption — not in paper]`: the values were chosen by hand to give the mix its shape and were not measured on an LLM system or fitted to a trace. Machine: one processor, 4096 MB of memory, 0.5 ms per context switch (inherited from `configs/scheduler_ddqn.yaml`).

| Setting | Inference requests | Fine-tuning jobs |
|---|---|---|
| Config key under `workload.task_types` | `inference_request` | `finetune_job` |
| Share of tasks (mixture weight) | 0.85 | 0.15 |
| Compute demand per task | lognormal, median 12 ms, sigma 0.7, clipped to 2 to 80 ms | lognormal, median 250 ms, sigma 0.5, clipped to 80 to 800 ms |
| Waits inside a task | 0 to 1 | 1 to 4 |
| Length of one wait | 5 to 30 ms | 10 to 60 ms |
| Memory footprint | 64 to 512 MB | 1536 to 3072 MB |
| Deadline | arrival + 2 × (compute + waits) + 20 ms | arrival + 6 × (compute + waits) + 20 ms |
| Priority level weights (level 0 lowest) | [0, 0, 0.5, 0.5] | [0.5, 0.5, 0, 0] |

**The mix the generator produced** [Reproduced] — computed from the 150 evaluation workloads of the reporting seeds (0, 1, 2, 3, 4; 10 workloads per load profile and seed); `all` pools the load profiles. These are properties of the generated input, not results of a scheduler.

| Load profile | Task class | Tasks per workload | Share of tasks | Share of compute demand | Compute demand per task (ms) | Memory per task (MB) |
|---|---|---|---|---|---|---|
| light | Inference requests | 41.1 | 84.1% | 22.6% | 15.6 | 288 |
| light | Fine-tuning jobs | 7.7 | 15.9% | 77.4% | 285.0 | 2310 |
| medium | Inference requests | 43.1 | 85.1% | 23.3% | 15.1 | 287 |
| medium | Fine-tuning jobs | 7.5 | 14.9% | 76.7% | 285.2 | 2297 |
| heavy | Inference requests | 44.0 | 86.0% | 24.3% | 14.9 | 288 |
| heavy | Fine-tuning jobs | 7.1 | 14.0% | 75.7% | 286.9 | 2346 |
| all | Inference requests | 42.7 | 85.1% | 23.4% | 15.2 | 288 |
| all | Fine-tuning jobs | 7.5 | 14.9% | 76.6% | 285.7 | 2317 |
