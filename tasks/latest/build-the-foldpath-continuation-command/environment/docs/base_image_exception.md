# Base-image exception and canonical catalog proposal

Foldpath uses the digest-pinned Docker Library image
`public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c`
as a task-local exception to the current canonical t-bench image catalog.

The task requires GCC 13, GNU make, binutils, the C runtime and development
headers throughout the agent session. Agents must clean-rebuild a C11 static
library, the existing native checker, and the new native continuation command
from `/opt/foldpath`. The verifier removes the installed continuation command
and performs another clean source build after task start. A runtime-only image
would not satisfy this observable offline contract without reconstructing the
same toolchain from mutable package repositories. The selected image is
immutable by digest and uses the public Docker Library mirror.

Canonical-catalog proposal: admit this exact digest as the GCC 13 / Debian
Bookworm native C build image, or provide a catalog-owned replacement containing
GCC 13, GNU make, binutils, libc development headers, Python 3 for the verifier,
and the terminal-session dependencies `tmux` and `asciinema`. Migration is
permitted only after the replacement passes the UTF-8 session-tool preflight,
the clean starter build and public checker, the complete oracle verifier, the
untouched-starter rejection, and split/resume and rename-recovery cases
unchanged.

The normal agent session starts in `/app`, following the Terminal-Bench 2.0
convention. All source, examples, documentation, smoke checks, and product
artifacts remain at their observable absolute paths under `/opt/foldpath` and
`/usr/local/bin`; changing the session directory does not alter the task
contract.
