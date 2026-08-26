We ship a terminal fighting-game duel under `/app/environment`: two fighters on a line, integer tick physics, and online match play where the opponent's inputs arrive a few frames late.

Complete the movement and combat simulation plus the predicting match client so every competitive tape stays bit-identical between the authoritative host and the online client. Build and run:

```bash
/app/environment/scripts/build_all.sh
/app/environment/bin/duel
```

That must exit 0 and write `/app/output/duel_report.json` with one row per tape in `/app/environment/tapes`. Every row converges on the host trajectory for the confirmed path, keeps the on-screen trajectory and rollback count consistent with the session rulebook, and reports final health from the fight rules.

Fight physics and the report schema are in `/app/environment/docs/duel_rules.md`. Online frame timing, digest split, and worked match journals are in `/app/environment/docs/session_semantics.md` and `/app/environment/docs/traces/`. Hand-written report JSON is not enough.
