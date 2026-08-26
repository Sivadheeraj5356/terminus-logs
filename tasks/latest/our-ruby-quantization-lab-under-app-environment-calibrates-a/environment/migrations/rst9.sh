#!/usr/bin/env bash
set -euo pipefail
ruby -r /app/environment/f5/scratch_arena.rb -e 'F5::ScratchArena.poison!'
