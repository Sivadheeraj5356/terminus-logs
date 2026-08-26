Memory Vault is a scored dungeon-crawl text adventure. Players walk rooms,
TAKE and DROP items, WAIT to ready a seal, SEAL watched chambers, SCRUB leak
chambers, and EXIT with the key for WIN, LOSE, or PARTIAL endings.

Campaign playthrough scripts live under `/app/environment/cases`. The
adventure under `/app/environment` must score those playthroughs using the
live chamber ledgers in `/app/environment/traces/` and write the campaign
scoreboard:
`/app/output/transcripts/<case_id>.json`,
`/app/output/state/hazard.epoch`,
`/app/output/state/replay.journal`, and
`/app/output/batch.manifest.json`.
Start play with `/app/environment/campaign/play.sh`.

A campaign that pauses after a committed save-log event count (`--stop-after`)
must continue later from that save log and finish with the same scores,
inventories, violations, and endings as an uninterrupted playthrough on the
same inputs. Scoreboard files come from playing the cases—not from pasted
static JSON—because checks clear outputs, swap move scripts or chamber
ledgers, and replay. Public play rules are in `/app/environment/docs/`.
