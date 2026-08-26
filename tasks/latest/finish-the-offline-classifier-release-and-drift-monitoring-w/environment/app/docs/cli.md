# CLI reference

`/app/p/wf --help` identifies both available subcommands, `train` and `run-drift`.

- `train [--data PATH] [--artifacts-dir PATH]`
- `run-drift --batch-id ID [--api-url URL] [--data PATH] [--artifacts-dir PATH]`

Defaults are `/app/data/training.parquet`, `/app/artifacts`, and `http://127.0.0.1:8000/api/v1`.

A successful `train` writes exactly one line to stdout: `trained <model_version> champion <name> oof_f1 <value> worst_repeat_f1 <value> worst_fold_f1 <value> calibrated_brier <value> threshold <value>`. The three F1 values use three digits after the decimal point; calibrated Brier and threshold use six. The line ends with a newline.

A successful `run-drift` writes exactly `submitted drift evaluation id <integer>` followed by a newline to stdout. Prefect lifecycle logging remains on stderr.

Release validation completes before the first product API request. On a local integrity or semantic failure, `run-drift` exits non-zero and stderr contains the concrete offending path. Attribution follows the file whose bytes or meaning are wrong: a policy digest or policy-schema mismatch names `/app/config/repro_config.json`; a training binding mismatch names the supplied `--data` path; a malformed release binding names `artifact_manifest.json`; and an artifact digest or semantic mismatch names that artifact's full path. A dotted manifest key or basename alone does not satisfy this contract.
