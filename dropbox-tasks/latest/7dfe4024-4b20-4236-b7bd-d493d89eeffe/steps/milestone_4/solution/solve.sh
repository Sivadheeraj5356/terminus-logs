#!/bin/bash
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$DIR/solve4.sh"