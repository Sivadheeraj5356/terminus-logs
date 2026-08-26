#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/src
cp "$(dirname "$0")/fold.cpp" /app/src/fold.cpp
cd /app/src
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -o fold fold.cpp
