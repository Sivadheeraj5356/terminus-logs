# modverse

A command line build list computer for the fictional modverse module ecosystem,
written in Scala 3 with the standard library only. It parses module manifests,
orders version strings, and computes which module versions a build uses.

## Layout

Sources live under /app/app/src/main/scala/modverse. The reference docs that fix
every contract are under /app/app/docs. VERSIONS.md defines the version string
grammar and the total order. MANIFEST.md defines the manifest file grammar.
BUILDLIST.md describes what the build list and the loaded manifest set are.
CLI.md defines the subcommands and the exact JSON each one writes.

A small example registry sits at /app/app/sample-registry with a main manifest at
/app/app/sample-registry/main.mod so you can try the CLI by hand.

## Building and running

Compile after editing sources with /app/app/build.sh. Then invoke the CLI through
the launcher on the path, for example

```
modverse buildlist --registry /app/app/sample-registry --main /app/app/sample-registry/main.mod
```

The launcher script is /app/app/modverse and the build script is /app/app/build.sh.
Both are stdlib only and run offline.
