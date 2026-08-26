Last step. Add the graph subcommand, which computes the same build list as
buildlist and also reports the set of manifest files the walk actually read, in
the JSON shape in /app/app/docs/CLI.md. The point of this step is that not every
manifest in the transitive graph needs to be opened.

Whether the walk descends into a module's deeper dependency manifests depends on
the lang value that module's manifest declares. The main module is the one
exception. The walk always opens the manifests of the direct requirements named
in the main module manifest whatever lang the main module itself declares, and
the lang value only governs whether the walk then keeps descending past a
dependency into that dependency's own deeper requirements. A module at lang 1.17
or above records every requirement it needs, direct and indirect, in its own manifest with
the indirect ones marked, so the walk does not open the manifests of its
dependencies to discover deeper requirements. A module below lang 1.17 does not
record its indirect requirements, so the walk has to read the full transitive
closure beneath it. The build list has to come out identical to what the plain
unpruned walk would give, since every required version is still accounted for,
while the set of manifest files read is smaller. Report both the build list and
that loaded set, and note that the main module manifest named on the command line
does not count as a loaded file.
