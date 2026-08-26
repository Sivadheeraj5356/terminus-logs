# Safari census runtime

During scoring, the verifier starts one seeded census and invokes `node /app/safari_dispatch.mjs <base_url>`. The dispatcher continues that census rather than creating another one.

## HTTP surface

`GET /health` reports readiness. `GET /scenarios` lists the three public census profiles, each with its own route shortcuts and weather pattern. `POST /new_game` accepts `{ "scenario_id": "open_savanna", "seed": 1234 }` for local rehearsal; scored setup is verifier-owned.

`GET /state` returns `status`, `end_reason`, `turn`, `turn_limit`, `score`, `scenario`, `limits`, `conditions`, `forecast`, `habitats`, `routes`, `explorers`, `reports`, `summary`, `scoreboard`, `action_schema`, `legal_actions`, `recent_events`, and `server_info`. `server_info` identifies the runtime revision and active-run serial. Hidden counts, unrevealed species, unrevealed route risk, and the seed are omitted.

`POST /act` advances one field turn. Submit either a finish request or up to four commands:

```json
{ "finish": true }
```

```json
{
  "commands": [
    { "type": "assess_route", "explorer_id": "tracker_ama", "to": "habitat_1" },
    { "type": "move", "explorer_id": "tracker_ama", "to": "habitat_1" },
    { "type": "observe", "explorer_id": "spotter_jo" },
    { "type": "report", "explorer_id": "spotter_jo", "species_id": "zebra", "estimate": 6 },
    { "type": "rest", "explorer_id": "ranger_kito" }
  ]
}
```

Each explorer can receive one command per turn. Movement follows one published route edge. A route's risk is `unknown` until an explorer assesses it. Simultaneous movement by at least two co-located explorers to the same destination is paired travel. Unknown, moderate, and high-risk crossings can cause unsupported-risk penalties and fatigue when their public safety requirements are not met. Explorer roles can also reduce specific risks, but pairing remains the dependable field practice.

An observation at a survey habitat reveals the species there, an observed count, quality, and that species' preferred phase. Counts can be low when phase, weather, role, fatigue, or recent disturbance are unfavorable. A `high` quality observation carries the reliable count. Repeated observations can improve quality, while crowding and repeated work increase disturbance. Filed reports are locked and cannot be revised.

The four explorers begin at base as two natural pairs. The wildlife spotter is strongest with mammals, the ornithologist with birds, the tracker reads routes efficiently, and the ranger reduces field risk. `conditions` and `forecast` publish phase and weather. Fatigue is public and rest lowers it.

The census can be submitted after `limits.finish_floor` once every survey habitat has one report. It fails at the turn limit. The scoreboard rewards filed and accurate counts, distinct species, reliable sightings, assessed routes, paired safe crossings, low-risk crossings, reports filed ahead of the submission floor, remaining field time, a clean safety record, and final submission. Turns, commands, high-load turns, unsupported risk, safety incidents, high-risk crossings, disturbance, invalid commands, and inaccurate reports reduce the score.
