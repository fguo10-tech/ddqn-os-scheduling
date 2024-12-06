"""Paper-reported values, transcribed once.

This module is the single place where numbers printed in the source paper
enter the code base. Table builders read the ``Paper-reported`` column from
here and the ``Reproduced`` column from result CSV files, so the two can never
be mixed up by a copy-paste slip.

All values below are ``[Paper-reported]``. None of them was produced by this
repository. Values read off a figure (rather than a table) are approximate and
are marked as such.

Source
------
X. Sun, Y. Duan, Y. Deng, F. Guo, G. Cai, Y. Peng, "Dynamic Operating
System Scheduling Using Double DQN: A Reinforcement Learning Approach to Task
Optimization", arXiv:2503.23659 (v1, 31 March 2025). Table 1.
"""

from __future__ import annotations

from typing import Final

PAPER_ARXIV: Final = "https://arxiv.org/abs/2503.23659"
PAPER_IEEE: Final = "https://ieeexplore.ieee.org/document/11020551/"

# Table 1 "Experimental Results" of the source paper.
PAPER_TABLE1: Final[dict[str, dict[str, float]]] = {
    "FCFS": {
        "avg_completion_time_ms": 350.0,
        "throughput_tasks_per_s": 2.8,
        "avg_response_time_ms": 200.0,
    },
    "SJF": {
        "avg_completion_time_ms": 290.0,
        "throughput_tasks_per_s": 3.1,
        "avg_response_time_ms": 170.0,
    },
    "RR": {
        "avg_completion_time_ms": 310.0,
        "throughput_tasks_per_s": 3.0,
        "avg_response_time_ms": 180.0,
    },
    "DDQN": {
        "avg_completion_time_ms": 250.0,
        "throughput_tasks_per_s": 3.5,
        "avg_response_time_ms": 150.0,
    },
}

# Figure 2 of the source paper (DDQN only, by load level). Read off bar and line charts:
# approximate.
PAPER_FIGURE2_APPROX: Final[dict[str, dict[str, float]]] = {
    "light": {"completion_time_ms": 250.0, "cpu_utilisation_pct": 85.0, "response_time_ms": 150.0},
    "medium": {"completion_time_ms": 300.0, "cpu_utilisation_pct": 90.0, "response_time_ms": 180.0},
    "heavy": {"completion_time_ms": 350.0, "cpu_utilisation_pct": 92.0, "response_time_ms": 210.0},
}

# Figure 4 of the source paper ("Loss vs Epoch", 0 to 2000 epochs).
PAPER_TRAINING_EPOCHS: Final = 2000
