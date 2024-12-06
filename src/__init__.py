"""ddqn-os-scheduling — draft reference implementation.

Sub-packages
------------
``src.common``     seeding, configuration, logging, statistics, plotting, Before/After tables
``src.scheduler``  discrete-event OS scheduling simulator, baselines, Double DQN, guardrails,
                   and the SchedulerPlugin interface with job-queue adapter sketches

The import package is called ``src``, following the folder layout. Use it from a checkout
installed in editable mode (``pip install -e ".[all]"``), one virtual environment per project.
"""

__version__ = "0.1.0.dev0"
