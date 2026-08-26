We are building a small command line tool called modverse that figures out which
module versions a build actually uses for a made up module ecosystem. The skeleton
is at /app/app with a working CLI, JSON output, file IO, and a registry reader
already wired up. The pieces that decide ordering and meaning are left as stubs
that throw, and your job over the next few steps is to fill them in. Build with
/app/app/build.sh and run the tool through modverse on your path. The whole thing
is Scala 3 with the standard library only, no build tool and no network.

Read the four reference docs under /app/app/docs before you start. /app/app/docs/VERSIONS.md
fixes the version string grammar and the total order over versions, including how
prerelease snapshots and an incompatible release sort against an ordinary tagged
release. /app/app/docs/MANIFEST.md fixes the manifest file grammar with its
require, replace, exclude, and lang directives in single line and block form.
/app/app/docs/BUILDLIST.md describes what the build list and the loaded manifest
set are and what decides how much of the dependency graph a build has to read,
which the later steps build on. /app/app/docs/CLI.md fixes every subcommand and
the exact JSON it writes.

For this first step, make the version and the manifest subcommands work. The
version subcommand has to order any two valid version strings and sort a list of
them, following the total order in the docs exactly, and the manifest subcommand
has to parse a manifest file into the model and emit it as the JSON described in
/app/app/docs/CLI.md. Get the precedence of pseudo versions, plain tagged
releases, and incompatible releases right, and make sure require, replace,
exclude, and the lang line all round trip through the parser with their fields and
ordering preserved.
