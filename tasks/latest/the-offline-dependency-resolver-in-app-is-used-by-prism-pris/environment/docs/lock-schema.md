# Lockfile and report schema

On success, write a UTF-8 JSON document to the requested lock path:

```json
{
  "packages": [
    {
      "name": "package-name",
      "version": "1.2.3",
      "features": ["feature-a"],
      "dependencies": [
        {"name": "dependency-name", "version": "2.0.0"}
      ]
    }
  ]
}
```

The top-level object has exactly one key, `packages`. Packages are sorted by
`name`. Feature names are sorted lexically. Dependencies are sorted by `name`.
Objects use the field order shown above. Encode with two-space indentation and
one trailing newline.

On success, write this report document:

```json
{
  "conflicts": []
}
```

On resolution failure, leave the lockfile unchanged and write a report document:

```json
{
  "conflicts": [
    {
      "package": "package-name",
      "constraints": [">=1.0.0,<2.0.0", ">=3.0.0,<4.0.0"],
      "reason": "no matching version"
    }
  ]
}
```

Conflicts are sorted by package name. Constraint strings are sorted lexically.
The report uses the same two-space JSON indentation and one trailing newline.
