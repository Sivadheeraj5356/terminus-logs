# The modverse build list

The build list is the set of module versions that a build actually uses. It has
one entry per module reached from the main module, mapping each module name to
the single version selected for it. The main module itself is not part of its own
build list.

Two stable facts about the manifest format decide how much of the dependency
graph a build has to read. A manifest declares the format generation it was
authored against with its lang line, and the indirect tracking generation is lang
`1.17`. A module authored at lang `1.17` or above records all of its
requirements in its own manifest, both the direct ones and the transitive ones,
and the transitive entries carry the `// indirect` marker so they can be told
apart from direct imports. A module authored below lang `1.17` records only its
direct requirements and leaves its indirect ones to be discovered from the
manifests further down the graph. The `// indirect` marker never changes what a
requirement means on its own, it only records where the requirement came from.

The direct requirements named in the main module manifest are always read,
whatever lang the main module itself declares. The lang generation of a manifest
only decides whether the requirements it already records are enough to stop
reading further down the graph beneath it, so it governs whether the walk
descends past a dependency, not whether the main module's own direct requirements
are opened.

The set of manifest files a build reads is itself an output. The graph subcommand
reports it alongside the build list, and the exact JSON shape for both the build
list and that loaded set is in /app/app/docs/CLI.md.
