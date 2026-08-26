Implement the Helm chart values coalesce precedence auditor at /app/bin/helmvals.

The CLI walks a local chart tree (Chart.yaml, values.yaml, nested charts/) and emits a resolved values manifest with a precedence trail. Authoritative behavior is defined in /app/docs/chart-contract.md, /app/docs/coalesce-contract.md, /app/docs/global-contract.md, /app/docs/condition-contract.md, /app/docs/cli-contract.md, and /app/docs/manifest-output.md. Read those documents end-to-end before changing code.

## Command

helmvals resolve --chart PATH [--values FILE ...] [--set key=value ...] --out PATH

--chart is the root chart directory. --values files apply in the order given on the command line. --set pairs apply after all --values files. Parent directories for --out are created when needed.

The resolver must honor dependency alias and condition fields, deep-merge global: blocks into every active chart, apply Helm-style map coalesce with scalar last-wins precedence, parse escaped dotted --set keys per the CLI contract, exclude condition-false subcharts from active_charts, and compute manifest_hash from canonical JSON excluding that field.

Edit the Go sources under /app, then rebuild with /app/scripts/verifier-rebuild.sh before verification. Legacy helpers under /app/internal/decoy are not authoritative.

Do not use network access or external services at runtime.
