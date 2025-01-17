# Source paper

This file is the record of the source paper of this repository and the values it reports. The
method in this repository follows the Double DQN scheduler described in it.

## Citation

Sun, X., Duan, Y., Deng, Y., Guo, F., Cai, G., and Peng, Y. (2025). Dynamic Operating System
Scheduling Using Double DQN: A Reinforcement Learning Approach to Task Optimization. In *2025 8th
International Conference on Advanced Algorithms and Control Engineering (ICAACE)*, pp.
1492–1497. IEEE.

| Field | Value |
|---|---|
| Authors (in order) | Xiaoxuan Sun, Yifei Duan, Yingnan Deng, Fan Guo, Guohui Cai, Yuting Peng |
| Title | Dynamic Operating System Scheduling Using Double DQN: A Reinforcement Learning Approach to Task Optimization |
| Venue | 2025 8th International Conference on Advanced Algorithms and Control Engineering (ICAACE), pp. 1492–1497, IEEE |
| arXiv | [2503.23659](https://arxiv.org/abs/2503.23659) |
| DOI | [10.1109/ICAACE65325.2025.11020551](https://doi.org/10.1109/ICAACE65325.2025.11020551) |
| IEEE Xplore document | [11020551](https://ieeexplore.ieee.org/document/11020551/) |
| BibTeX key | `sun2025ddqn` in [references.bib](references.bib) |

## Method

The paper applies Double DQN to operating-system task scheduling. The agent observes the
status of the task queue, the system load and the available resources, and acts by changing
how tasks are run, for example by raising a task's priority or by allocating a different CPU
time slice. The reward combines resource utilisation, task completion time and system response
time with weighting coefficients. The method is evaluated in experiments and simulations on
a synthetic dataset of tasks of three kinds (CPU-bound, memory-bound and I/O-bound) and compared with
First-Come-First-Serve (FCFS), Shortest Job First (SJF) and Round Robin (RR).

## Reported values

The values below come from a different setup; they are shown for reference only and are not
compared with values from this code. Values read from a figure rather than a table are
approximate and are marked "≈".

Table 1 of the paper ("Experimental Results"), every value `[Paper-reported]`:

| Algorithm | Average task completion time (ms) | System throughput (tasks/sec) | Average response time (ms) |
|---|---|---|---|
| FCFS | 350 `[Paper-reported]` | 2.8 `[Paper-reported]` | 200 `[Paper-reported]` |
| SJF | 290 `[Paper-reported]` | 3.1 `[Paper-reported]` | 170 `[Paper-reported]` |
| RR | 310 `[Paper-reported]` | 3.0 `[Paper-reported]` | 180 `[Paper-reported]` |
| DDQN | 250 `[Paper-reported]` | 3.5 `[Paper-reported]` | 150 `[Paper-reported]` |

Figure 2 of the paper (DDQN only, by load level, read from the charts), every value
`[Paper-reported]`:

| Load level | Completion time (ms) | CPU utilisation (%) | Response time (ms) |
|---|---|---|---|
| Light | ≈ 250 | ≈ 85 | ≈ 150 |
| Medium | ≈ 300 | ≈ 90 | ≈ 180 |
| Heavy | ≈ 350 | ≈ 92 | ≈ 210 |

Figure 3 of the paper (DDQN only, by task type, read from the charts), every value
`[Paper-reported]`: CPU utilisation ≈ 85 / 80 / 75 % for CPU-bound / memory-bound / I/O-bound
tasks; completion time is lowest for CPU-bound and highest for I/O-bound tasks.
