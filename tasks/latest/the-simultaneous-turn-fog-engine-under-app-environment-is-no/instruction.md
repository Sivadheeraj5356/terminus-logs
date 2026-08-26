The simultaneous-turn fog engine under `/app/environment` is not meeting its case ladder yet. Repair TypeScript modules under `/app/environment` so digest, mix, and certificate helpers match the published rules and the play pipeline regenerates correct artifacts.

From `/app/environment` run

```
npm run play -- --cases /app/environment/fixtures/cases.toml
```

That must rewrite `/app/output/sheet.json` and `/app/output/vlog.jsonl` for every case id in the cases file. grid_a means a visible geometry case, grid_b means a visible mix case, grid_c means a visible timing-mask case, grid_x means the held-out geometry case, and grid_y means the held-out mix case. Contract details, including the field run_digest, live in `/app/environment/docs/k_rules.md` with schemas `/app/environment/docs/sheet.schema.json` and `/app/environment/docs/vlog.schema.json`. Static or manual output writes are insufficient; copying outputs without running the normal play pipeline will not pass. Rerunning play after deleting the two outputs must replay the same digests and certificates. Expect the same play command to be re-run by the test runner after repairs.
