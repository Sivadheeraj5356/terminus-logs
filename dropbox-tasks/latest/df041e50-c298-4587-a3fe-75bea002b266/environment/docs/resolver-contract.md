# Resolver contract

Invoke the CLI as:

```text
prism-dependency-forge --workspace <absolute-file> --registry <absolute-dir> --lock <absolute-file> --report <absolute-file>
```

All four paths must be absolute. The workspace file and registry directory must
exist. Relative paths, missing inputs, malformed registry records, or malformed
workspace records are usage/input failures and exit 2. A resolution conflict
also exits 2, writes a conflict report, and leaves any existing lockfile
byte-for-byte unchanged. Other output failures exit 1 and must also leave any
existing lockfile byte-for-byte unchanged. A successful run exits 0. Diagnostics
go to stderr; successful runs do not write to stdout.

The workspace file is line-oriented. Empty lines and lines beginning with `#`
are ignored. Each root request has this form:

```text
root <alias> <package> <constraint> [features=a,b,c]
```

`alias` is the name used by the workspace, and `package` is the canonical package
name in the registry. Aliases do not create separate locked packages; all
constraints and features are merged by canonical package name.

Each registry package lives at `<registry>/<package>.pkg`. Files are
line-oriented, with blank lines and `#` comments ignored. A version starts with:

```text
version <semver> [yanked=true]
```

Following `dep` and `feature` lines belong to the most recent version:

```text
dep <package> <constraint> [features=a,b,c]
feature <feature-name> <package> <constraint> [features=a,b,c]
```

Only dependencies of the selected version are active. A `dep` line is always
active when its version is selected. A `feature` line is active only if that
feature has been requested for the selected package. Feature requests from roots
and dependencies are unified by canonical package name, and activating a feature
may add more dependencies that must also be resolved. Unknown requested features
are allowed and still appear in the lockfile, but they add no dependencies.

Version constraints are comma-separated comparisons using `>=`, `>`, `<=`, `<`,
or `=` against semantic versions. Select the highest non-yanked version that
satisfies every active constraint for a package. Pre-release versions sort lower
than the corresponding final release and are only selected when they satisfy the
same comparison rules as any other version.

The resolver must work entirely offline and must produce byte-identical output
for identical inputs. Successful runs create missing parent directories for the
requested lockfile and report paths.
