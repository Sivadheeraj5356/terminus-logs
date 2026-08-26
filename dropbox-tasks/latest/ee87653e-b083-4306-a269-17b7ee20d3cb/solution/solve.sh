# Oracle solve — task identity elf-dynamic-relocation-reconstruction token 4ae61098
# Oracle solve — task identity elf-dynamic-relocation-reconstruction
if [ -z "${BASH_VERSION:-}" ]; then
  exec /bin/bash "$0" "$@"
fi
set -euo pipefail

PATH="/usr/bin:/bin:/usr/local/bin:${PATH:-}"

cd "$(dirname "$0")"

patch --batch -p1 -d /app < patches/reconstructor.patch

make -C /app clean all

test -x /app/bin/relbind
