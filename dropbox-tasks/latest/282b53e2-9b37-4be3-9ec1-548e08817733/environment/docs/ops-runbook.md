# Campaign playbook

Play Memory Vault scoring:

```bash
bash /app/environment/campaign/play.sh
```

Optional mid-campaign save pause:

```bash
bash /app/environment/campaign/play.sh --stop-after <N>
```

`<N>` is how many save-log events were written before the pause. Later
continues must resume and match a clean playthrough. Operators may set
`OUT_DIR` to redirect the scoreboard root.

Scoreboard paths under `/app/output` (or `$OUT_DIR`):

- `transcripts/<case_id>.json` — one adventure ending (WIN / LOSE / PARTIAL)
- `state/hazard.epoch` — chamber-hazard generation for this campaign
- `state/replay.journal` — append-only campaign save log
- `batch.manifest.json` — lexical case list with `generation`, `hazard_epoch`,
  move fingerprints, status, and score

Extra drill cases may use stems such as `zdrop` or `zexit`. Shipped case
`c02` lives under `/app/environment/cases/`. Transcript names such as
`c01.json`, `zdrop.json`, and `zexit.json` may appear during checks. A
mid-save integrity probe may insert a non-record line like
`NOTAVALID|record`.

Poisoned scoreboard values such as generation `deadbeefdeadbeef` must not
survive a fresh playthrough when inputs changed.
