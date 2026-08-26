Next, teach the buildlist computation to honour the replace and exclude
directives, but only when they sit in the main module manifest. The same replace
and exclude lines written inside a dependency manifest are read for that
manifest's own require entries and otherwise do nothing to the build as a whole.

A replace in the main module swaps both the manifest and the identity used for
the named module edge, so the requirements that feed selection come from the
replacement target. A replacement may point a module at a version lower than
something else required, and when it does the replacement wins and the build list
follows it rather than the higher required version. A replace target may instead
be a local directory whose own module.mod is read in place of the registry
manifest and feeds its own require entries into selection, and a local replace
path is resolved against the directory that holds the main module manifest rather
than the registry root. A local replace still keys the build list entry under the
module name on the left side of the replace, never under the filesystem path, so
the selected version for that module reads out of its local module.mod while the
key stays the module name. An exclude in the main module drops one exact module
version so that selection moves up to the lowest version the registry publishes
for that module whose number is at least the excluded one and that is not itself
excluded, which can be a version that no requirement names.
