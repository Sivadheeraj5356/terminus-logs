# modverse command line

The build runs through the launcher at `/usr/local/bin/modverse`, which executes
the compiled CLI. Rebuild after editing sources by running
`/app/app/build.sh`. Every subcommand writes JSON to the path given by `--out`,
or to standard output when `--out` is omitted. JSON keys use the spellings shown
below and module versions are written with the leading `v`.

## version

`modverse version --compare A B` compares two version strings and writes
`{"compare": -1}` when A is lower, `{"compare": 0}` when they are equal, and
`{"compare": 1}` when A is higher.

`modverse version --sort v1.0.0,v1.0.0-rc.1,v2.0.0+incompatible` takes a comma
separated list of version strings and writes a sorted array under the `sorted`
key, for example `{"sorted": ["v1.0.0-rc.1", "v1.0.0", "v2.0.0+incompatible"]}`,
with the versions in ascending order, each spelled with a leading `v`.

## manifest

`modverse manifest --file PATH` parses one manifest file and writes a JSON object
describing it, shaped like the following.

```
{
  "module": "sample/web",
  "lang": "1.21",
  "require": [
    {"path": "sample/json", "version": "v1.2.0", "indirect": false}
  ],
  "replace": [
    {"oldPath": "sample/json", "oldVersion": "v1.2.0",
     "newPath": "sample/json", "newVersion": "v1.1.0", "newIsLocal": false}
  ],
  "exclude": [
    {"path": "sample/json", "version": "v1.0.5"}
  ]
}
```

A replace whose right side is a filesystem path sets `newPath` to that path,
leaves `newVersion` as the empty string, and sets `newIsLocal` to true. A replace
whose left side omits a version sets `oldVersion` to the empty string. The
`require`, `replace`, and `exclude` arrays preserve the order the entries appear
in the file and a block expands in place at its position. When no lang line is
present, `lang` is the string `0.0`.

## buildlist

`modverse buildlist --registry DIR --main PATH --out RESULT.json` computes the
build list for the main module at `PATH` against the registry rooted at `DIR`. It
writes the following.

```
{
  "buildList": {
    "sample/json": "v1.2.0",
    "sample/text": "v1.4.1"
  }
}
```

The `buildList` object maps each selected module name to its selected version.
The main module is not a key. When the main module requires nothing the
`buildList` object is empty. When a main module replace points a module at a
local filesystem path, the entry is still keyed under the module name on the left
side of the replace, never under the filesystem path, and its selected version is
read from the local `module.mod`.

## graph

`modverse graph --registry DIR --main PATH --out RESULT.json` computes the build
list exactly as `buildlist` does and additionally reports which manifest files
were read while computing it. It writes the following.

```
{
  "buildList": {
    "sample/json": "v1.2.0"
  },
  "loaded": [
    "sample/json@v1.2.0/module.mod"
  ]
}
```

The `loaded` array lists, in any order, the registry relative path of every
manifest file the walk actually read, not counting the main module manifest given
on the command line. A manifest replaced by a filesystem path contributes the
path target's `module.mod` spelled relative to the registry root when it sits
under the root, or its path as given otherwise. A manifest that the pruning rule
keeps the walk from reading does not appear.
