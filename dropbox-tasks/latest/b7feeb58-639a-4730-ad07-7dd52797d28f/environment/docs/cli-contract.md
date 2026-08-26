# CLI contract

## Invocation

```
helmvals resolve --chart PATH [--values FILE ...] [--set key=value ...] --out PATH
```

Unknown flags or subcommands exit non-zero with `unknown argument` or `unknown command` on stderr.

## --set parsing

Each `--set` argument is `key=value` split on the **first** unescaped `=`. Keys use `.` for nesting except when escaped as `\.` which produces a literal dot in the path segment.

Examples:

| Argument | Path segments |
|----------|----------------|
| `replicas=3` | `["replicas"]` |
| `outer.inner=1` | `["outer","inner"]` |
| `outer\.inner=1` | `["outer.inner"]` |
| `cache.replicas=2` | targets subchart id `cache` |

Values parse as YAML scalars using the same rules as values files.

## Errors

Missing `--chart` or `--out` exits non-zero with `usage:` on stderr. Missing chart files exit non-zero without writing `--out`.
