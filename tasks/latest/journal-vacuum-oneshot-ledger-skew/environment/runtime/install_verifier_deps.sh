#!/bin/bash
set -euo pipefail

pip_bin="${1:?pip binary required}"
lock_file="${2:?requirements lock path required}"

"${pip_bin}" install --no-cache-dir --require-hashes --no-deps -r "${lock_file}"
