# faultctl

Inject and reset practice incidents on the local demo (F18). This is a
**human/test tool**: the agent under `oncall/` must never import, call or read
it (CI `rules` job enforces this).

```bash
python scripts/faultctl/faultctl.py list
python scripts/faultctl/faultctl.py inject scenario-06
python scripts/faultctl/faultctl.py status
python scripts/faultctl/faultctl.py reset            # always run when done
```

- Scenarios live in `scenarios.yaml` with neutral ids. Types: `stop`,
  `cpu_limit`, `mem_limit`, `flag`. The answers live only in
  `eval/expected.yaml`.
- `flag` (params `key`, `variant`) sets that flag's `defaultVariant` in
  `src/flagd/demo.flagd.json`, refusing keys or variants the file does not
  have and changing nothing else (formatting kept). flagd polls the file
  ("fileinfo" sync) and reloads within a second; faultctl waits for flagd's
  `filepath event` log line and restarts flagd only if it does not appear in
  30 s. The flag UI (http://127.0.0.1:8080/feature) edits the same file.
- One scenario at a time: `inject` refuses while another is active unless
  `--combo` is given.
- `status` warns while the flag file differs from git HEAD (flag scenario or a
  manual flag-UI toggle). **Never commit that file** - CI rejects PRs that
  touch `src/`.
- Only containers of the compose project `opentelemetry-demo` are touched.
- `inject` records the original state and limits in `.state.json`
  (gitignored) before changing anything.
- `reset` restores the flag file from git (`git checkout --`) whenever it
  differs from HEAD and waits for flagd to reload it, then restores every
  recorded container change, starts any exited container of the
  project, then waits up to 120 s (`--wait`) until all demo containers are
  running and not `starting`/`unhealthy`. Exit code 1 if they are not. Safe to
  run repeatedly.
- `cpu_limit` uses `--cpu-period/--cpu-quota`, not `--cpus`: a `--cpus` limit
  cannot be removed with `docker update` (verified on Docker 29.1.5), while
  `--cpu-quota -1` restores "unlimited". If a container already has a `--cpus`
  limit, faultctl uses `--cpus` and restores the original value.
- `mem_limit` sets `--memory` and `--memory-swap` to the same value; reset
  restores both originals.

Tests: `pytest -q scripts/faultctl/` (docker is mocked).
