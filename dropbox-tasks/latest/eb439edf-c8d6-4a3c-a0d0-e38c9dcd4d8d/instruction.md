Build a Go CLI binary called `tribunal-game` that simulates historical court arbitration. Invoke it as:

```
./tribunal-game --codex /opt/task_data/codex.txt --sessions /opt/task_data/sessions.json --seed <SCENARIO>
```

Accepted seeds are `COURT-1348`, `TRIBUNAL-1605`, and `ASSEMBLY-1789`. Commands arrive line-by-line on stdin. Sessions load from `sessions.json`, but `codex.txt` is the authoritative override — its prose patterns supersede all JSON values for scoring and thresholds. On startup print `IMPERIAL TRIBUNAL — <title>` then `Open cases: N`.

`invoke <section>` on a valid section prints `[CITE] Section X. Merit: +N. Score: N`. On the precedent section it also appends `PRECEDENT ACTIVE (N grants)` after the score. An unrecognised section prints `[INVALID SECTION] Section X not found in codex. Merit: -N. Score: N`.

`grant <id>` prints `[GRANTED] <title> (<id>). Merit: +N. Score: N`. While Precedent is active, each grant earns a bonus and the output includes `(+N precedent)` in the merit field followed by `PRECEDENT ACTIVE (N grants)` or `PRECEDENT EXPIRED`. `deny <id>` prints `[DENIED] <title> (<id>). Merit: +N. Score: N` when the deny score is positive, or `Merit: -N` when negative.

Applying `grant` or `deny` to an unknown ID prints `[INVALID] Case not found: <id>. Merit: -N. Score: N`; to an already-resolved case it prints `[INVALID] Case <id> already resolved. Merit: -N. Score: N`. Both deduct `invalid_penalty` from the score.

`adjourn` prints `SESSION ADJOURNED`, then `Merit total: N. Threshold: N.`, then `VERDICT: HONOURED` or `VERDICT: DISHONOURED`. `status` prints the current score, open cases, and resolved cases labelled `[GRANTED]` or `[DENIED]`. `help` lists all valid commands.

Exit 2 if a data file cannot be opened; exit 1 if the seed is absent.
