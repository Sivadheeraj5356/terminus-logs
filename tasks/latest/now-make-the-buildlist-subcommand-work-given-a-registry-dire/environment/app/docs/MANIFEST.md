# Modverse manifest grammar

Each module version owns one manifest file. In a registry the manifest for a
module named `x/y/z` at version `v1.4.0` lives at the path
`x/y/z@v1.4.0/module.mod` under the registry root. The main module of a build is
named by a single manifest file path passed on the command line, and its module
name need not appear in the registry.

A manifest is a sequence of lines. Blank lines and lines whose first non space
character is `//` are comments and carry no meaning. Leading and trailing spaces
on a line are insignificant. The grammar has five directive kinds.

The module line names the module the manifest describes. It is written as
`module NAME`, for example `module sample/web`.

The lang line declares the manifest format generation the module was authored
against. It is written as `lang N.M`, for example `lang 1.21`. The lang value is
a two field dotted number compared field by field as integers. A manifest has at
most one lang line. A manifest with no lang line is treated as `lang 0.0`.

A require directive states that the module needs another module at a minimum
version. The single line form is `require NAME VERSION`, for example
`require sample/json v1.2.0`. The block form opens with `require (` on its own
line, lists `NAME VERSION` pairs one per line, and closes with a `)` on its own
line. A trailing `// indirect` marker may follow a require entry and records that
the requirement comes from a transitive dependency rather than a direct import.
The marker does not change the meaning of the requirement itself, but it is read
by the pruning rule in the graph layer.

A replace directive rewrites an edge in the module graph. It is written as
`replace OLD => NEW` or `replace OLD VERSION => NEW VERSION`, and the block form
opens with `replace (` and closes with `)`. The left side names the module
version being replaced, where omitting the version means every version of that
module. The right side names what to use instead. The right side is either
another module name with a version, for example
`replace sample/json v1.2.0 => sample/json v1.1.0`, or a filesystem path that
starts with `./` or `../`, for example
`replace sample/json => ../local/json`. A path target points at a directory that
contains its own `module.mod` manifest, which is read in place of the registry
manifest for the replaced module and contributes its own require directives to
the build. A relative path target is resolved against the directory that holds
the main module manifest, the file named on the command line, and never against
the registry root.

An exclude directive removes a single module version from consideration. It is
written as `exclude NAME VERSION`, and the block form opens with `exclude (` and
closes with `)`. An excluded version is never selected. If a module is required
at an excluded version, selection moves up to the lowest version that the
registry actually publishes for that module whose number is at least the
excluded one and that is not itself excluded. The candidate versions are taken
from what the registry holds for the module, not only from versions that some
requirement already names, so a higher version that no requirement mentions can
still be chosen when the required one is excluded.
