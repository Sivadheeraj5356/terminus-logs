#!/usr/bin/env bash
set -euo pipefail
/app/bin/nxctl inspect --json "${@}"
