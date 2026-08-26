# Cryptographic verifier interface

The executable is `/app/bin/pfseal-worker`.

```
pfseal-worker --db ABSOLUTE_PATH --worker-id ID [--once | --idle-limit N] [--poll-ms N] [--at RFC3339]
```

`--db` and `--worker-id` are required. Worker ids match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. `--poll-ms` is an integer from 10 through 60000 and defaults to 1000. `--idle-limit` is an integer from 0 through 1000 and defaults to 0; zero means no automatic background exit. `--at` must be canonical UTC RFC 3339 with milliseconds and defaults to the startup time. All jobs in one invocation use that same effective time. Repeated options, unknown options, empty values, out-of-range values, relative database paths, and combining `--once` with a nonzero idle limit are usage errors.

`--once` verifies eligible incidents until the first empty selection and exits. Otherwise the verifier waits for `--poll-ms` after an empty selection and exits after `--idle-limit` consecutive empty selections when that limit is nonzero. Claiming an incident resets the consecutive-empty count. SIGINT or SIGTERM requests a clean exit after the current verification; while idle, the signal must cancel the active wait immediately rather than waiting for `--poll-ms`. A normal exit writes exactly one minified JSON line to stdout, with keys in this order:

```
{"workerId":"ID","claimed":0,"succeeded":0,"failed":0,"rotations":0,"jobs":[]}
```

`jobs` is in claim order. Success elements are `{"jobId":N,"status":"succeeded","decision":"current|rotate"}`. Failure elements are `{"jobId":N,"status":"failed","error":"CODE"}`. Counts are integers; `rotations` counts inserted rotation rows. No progress or secret content is printed.

`--help` is valid only by itself and prints the usage line to stdout with exit 0. Usage errors print `pfseal-worker: MESSAGE` and a newline to stderr, nothing to stdout, and exit 64. `MESSAGE` is the parser reason using these stable forms: `unknown option OPTION`, `duplicate OPTION`, `OPTION requires a value`, `OPTION is required`, `OPTION must be an absolute path`, `OPTION is invalid`, `OPTION must be an integer`, `OPTION must be between MIN and MAX`, `--at must be canonical UTC RFC3339 with milliseconds`, or `--once cannot be combined with --idle-limit`. An unexpected startup or database error prints exactly `pfseal-worker: fatal worker error` and a newline to stderr, nothing to stdout, and exits 70.
