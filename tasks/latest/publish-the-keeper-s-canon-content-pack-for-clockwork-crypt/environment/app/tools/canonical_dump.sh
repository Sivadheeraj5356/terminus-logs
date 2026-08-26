#!/bin/bash
set -euo pipefail

DB_PATH="${1:-/app/state/world.db}"

sqlite3 -batch -noheader "$DB_PATH" <<'SQL'
SELECT 'room|' || id || '|' || name || '|north=' || COALESCE(north, '') || '|east=' || COALESCE(east, '') || '|south=' || COALESCE(south, '') || '|west=' || COALESCE(west, '')
FROM rooms ORDER BY id;
SELECT 'item|' || id || '|' || display_name || '|room=' || room_id || '|unlocks=' || unlocks || '|reusable=' || reusable
FROM items ORDER BY id;
SELECT 'lock|' || id || '|room=' || room_id || '|item=' || requires_item || '|flag=' || opens_flag
FROM locks ORDER BY id;
SELECT 'npc|' || id || '|room=' || room_id || '|gate=' || gate_flag || '|dialogue=' || dialogue_flag || '|grants=' || grants_flag
FROM npcs ORDER BY id;
SELECT 'clue|' || id || '|source=' || source || '|position=' || position || '|rotation=' || rotation || '|matte=' || upper(matte)
FROM clues ORDER BY id;
SELECT 'beat|' || position || '|room=' || room_id || '|action=' || action || '|subject=' || subject_id || '|requires=' || requires_flag || '|emits=' || emits_flag
FROM beats ORDER BY position;
SQL
