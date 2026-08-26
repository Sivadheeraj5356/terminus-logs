#!/bin/bash
set -euo pipefail
printf '%s' "$1" | openssl dgst -sha256 -r | awk '{print $1}' | cut -c1-16
