Now make the buildlist subcommand work. Given a registry directory and a main
module manifest, it computes the build list, the map from each module reached in
the transitive graph to its selected version, and writes it as the JSON in
/app/app/docs/CLI.md.

The walk starts from the main module and reads a module version's manifest only
at the moment it first needs it, following require directives outward until no
new module version is reached. Manifests the walk never reaches are never read.
For each distinct module in the graph the selected version is the highest version
that anything in the graph requires of it. A require names a minimum, so the
selection is the maximum over every minimum requested anywhere, and there is no
search and no revising of a choice once it is made. A version that merely exists
in the registry but that nobody requires is never selected, and a later higher
requirement for a module pulls in that higher manifest too and contributes
whatever it requires. The main module itself is never a key in the build list,
and the build list is empty when the main module requires nothing.
