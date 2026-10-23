# Issue board (Incident Zero)

Each entry is one unit of work, one branch and one PR. The GitHub issue holds the
owner, reviewer and the full spec; this table is the index.

Branch: `<type>/<NN>-<slug>`, where NN is the two-digit number in the table.
Feature specs are in [FEATURES.md](FEATURES.md).

| NN | ID | Title | Module | Priority | Depends on | GitHub # | Status |
|---|---|---|---|---|---|---|---|
| 00 | F00 | CI, AGENTS.md override and feature spec | repo setup | P0 | none | PR #1 | merged |
| 01 | F01 | Package skeleton, contracts, config, tool registry | brain | P0 | F00 | [#2](https://github.com/rhrishi-99/opentelemetry-demo/issues/2) | open |
| 02 | F02 | Run log | brain | P0 | F01 | [#3](https://github.com/rhrishi-99/opentelemetry-demo/issues/3) | in progress (`feat/02-run-log`) |
| 03 | F03 | Telemetry backends: live + offline (record & replay) | tools | P0 | F01 | [#4](https://github.com/rhrishi-99/opentelemetry-demo/issues/4) | open |
| 04 | F04 | Tool: get_metrics | tools | P0 | F01, F03 | [#5](https://github.com/rhrishi-99/opentelemetry-demo/issues/5) | open |
| 05 | F05 | Tool: search_traces | tools | P0 | F01, F03 | [#6](https://github.com/rhrishi-99/opentelemetry-demo/issues/6) | open |
| 06 | F06 | Tool: search_logs | tools | P0 | F01, F03 | [#7](https://github.com/rhrishi-99/opentelemetry-demo/issues/7) | open |
| 07 | F07 | Tool: container_health (read-only Docker) | platform | P0 | F01 | [#8](https://github.com/rhrishi-99/opentelemetry-demo/issues/8) | open |
| 08 | F08 | Tool: deploy_history | platform | P1 | F01 | [#9](https://github.com/rhrishi-99/opentelemetry-demo/issues/9) | open |
| 09 | F09 | Investigation loop (Eyes) + LLM client + CLI | brain | P0 | F01, F02 | [#10](https://github.com/rhrishi-99/opentelemetry-demo/issues/10) | open |
| 91 | D01 | Architecture sketch | eval-docs | — | none | [#11](https://github.com/rhrishi-99/opentelemetry-demo/issues/11) | open |
