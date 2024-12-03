# Security policy

## Status

This is draft research code, version 0.1.x. It is maintained on a best-effort basis. There is no
promised response time and no supported-release window; fixes land on `main`.

## How to report privately

Use GitHub private vulnerability reporting: open the repository's **Security** tab and choose
**Report a vulnerability**. Never report a security issue in a public issue, pull request or
discussion. The same private channel is used for Code of Conduct reports.

Please include what you found, the commit you looked at, the steps or the config that show the
problem, and what you think the impact is. Give the maintainers a reasonable chance to fix the
problem before you disclose it publicly.

## What counts as a security issue here

- Ordinary code vulnerabilities, for example unsafe deserialisation of a checkpoint, or path
  traversal in the run, plotting and reporting scripts.
- A scheduler guardrail that does not trigger when its documented condition holds, or a
  Q-divergence latch that releases without the explicit operator call `reset(clear_latch=True)`
  in the plugin.
- A path in `SchedulerPlugin` or the adapter sketches that sends a decision, calls a cluster
  API or reads a file it was not given, since the documentation states that they translate
  dictionaries only.
- Committed secrets (keys, tokens, credentials) or committed sensitive data, including any copy
  of a real dataset or a non-synthetic record.

## Out of scope

- Weaknesses that follow from the stated limits of a simulated component (see the warning
  below), unless the documentation claims a protection the code does not give.
- A guardrail that triggers as specified but does not improve the result. That is a research
  observation, already reported in the results, not a security issue.
- Vulnerabilities in third-party packages that are not triggered by this repository's code;
  please report those upstream.
- Results that differ from this repository's reference run. These are research questions, not
  security issues; to report such a difference, use the "Replication report" issue form.
- Denial of service by running very large configs on your own machine.

## Warning

- Do not use this code to schedule real workloads, and do not feed it real job data that
  contains personal information, without an independent security review.
- The scheduler is a simulator of one CPU with synthetic workloads. The guardrails were shown
  by unit tests to fire as specified; the reference run did not show that they contain the
  failure that occurred under heavy load. The `SchedulerPlugin` job-queue adapters are sketches, not
  production integrations, and must not be connected to a real cluster as they are.
