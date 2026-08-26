# Prefect orchestration profile

`run-drift` executes through Prefect 2 with normal lifecycle logging on stderr. `load-release` completes the full offline digest and semantic audit before `fetch-inference-batch` performs the first product API request. The fetch task owns the entire cursor chain and returns one validated, de-duplicated batch binding to the scoring task.

| Kind | name |
|---|---|
| flow | `drift-monitoring-run` |
| task | `load-release` |
| task | `fetch-inference-batch` |
| task | `score-and-measure-drift` |
| task | `submit-drift-evaluation` |

The named flow is the execution entry point for every `run-drift` invocation.
