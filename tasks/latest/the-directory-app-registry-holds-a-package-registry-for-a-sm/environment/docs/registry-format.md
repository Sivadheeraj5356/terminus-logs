# Registry layout

Every package lives under /app/registry/<name>/<version>/, one directory per released version. Each version directory holds index.json (the dependency metadata) and a Go source stub. A version whose stub removes or changes a previously public symbol also ships a MIGRATION.md describing the change; versions that only add a release without touching the public surface do not.

index.json has four fields: name, version, requires, and conflicts. requires is a list where each entry is either a plain requirement, `{"package": ..., "range": ...}`, meaning that exact package must be present in the resolved set at a version satisfying range, or an alternative group, `{"any_of": [{"package": ..., "range": ...}, ...]}`, meaning at least one of the listed alternatives must hold among the present packages. conflicts lists plain requirements too; if a present package's version falls in a listed conflict range, that package and the one declaring the conflict cannot both appear in the same resolved set, regardless of which side's index.json carries the declaration.

Below is a self-contained toy registry, unrelated to the one under /app/registry, showing the shape:

```
registry/cogwheel/1.0.0/index.json
{
  "name": "cogwheel",
  "version": "1.0.0",
  "requires": [
    {"package": "beltdrive", "range": ">=2.0.0"}
  ],
  "conflicts": []
}

registry/beltdrive/2.0.0/index.json
{
  "name": "beltdrive",
  "version": "2.0.0",
  "requires": [
    {"any_of": [
      {"package": "washer", "range": "=1.0.0"},
      {"package": "washer", "range": "=1.1.0"}
    ]}
  ],
  "conflicts": [
    {"package": "washer", "range": "=0.9.0"}
  ]
}

registry/washer/1.0.0/index.json
{"name": "washer", "version": "1.0.0", "requires": [], "conflicts": []}
```

A resolution for a manifest requiring cogwheel would need cogwheel 1.0.0, beltdrive 2.0.0 (pulled in by cogwheel's plain requirement), and either washer 1.0.0 or washer 1.1.0 (beltdrive's any_of is satisfied by whichever is present); washer 0.9.0 could never join that set alongside beltdrive 2.0.0, conflict declaration or not.
