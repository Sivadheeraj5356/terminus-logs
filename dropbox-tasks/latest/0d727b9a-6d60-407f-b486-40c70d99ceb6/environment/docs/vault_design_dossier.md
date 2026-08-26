# The Obsidian Vault — Design Dossier

*Internal document — Meridian Escape Experiences Ltd.*
*Classification: Operational Reference*
*Revision: 14 (current)*

---

## Foreword

This dossier collects the complete design history, mechanical specification, playtester feedback, exploit reports, and operational runbook for *The Obsidian Vault*, Meridian's flagship escape room installation at the Hartwell Street location. It is the authoritative reference for game masters, technicians, and the software team maintaining the WEBrick service that drives the room's digital control layer.

Sections are organised chronologically where relevant, thematically elsewhere. Cross-references use the §-notation (§3.2 means section 3, subsection 2).

---

## Part I — Room Concept and Physical Layout

### 1.1 Concept Brief

*The Obsidian Vault* was conceived in early 2022 by lead designer Helena Marchetti following a site visit to a decommissioned Victorian-era bank vault in Bristol. The brief called for a room that balanced:

1. **Atmospheric authenticity**: visitors should feel genuinely transported to the late 19th century.
2. **Layered cognitive difficulty**: puzzles should reward lateral thinking rather than rote pattern-matching.
3. **Accessible technology integration**: the digital control layer must feel invisible; players should never know they are interacting with software.
4. **Replayability**: the room should tolerate repeat visitors through procedural variation in puzzle parameters while maintaining a fixed narrative arc.

The final installation opened in March 2023 after fourteen months of design, build, and playtesting.

### 1.2 Physical Layout

The room occupies 48 square metres across two chambers separated by a wrought-iron gate that forms the primary mid-point reveal.

**Antechamber (Room A)**

The antechamber is styled as a bank lobby entrance. Key physical elements:

- A mahogany reception desk with a locked drawer (holds the cipher_alpha reference card).
- Two leather chairs flanking a low table bearing a newspaper dated 17 March 1887.
- A grandfather clock stopped at 3:14 (relevant to cipher_gamma).
- A brass speaking tube mounted on the north wall, through which the game master voice-acts responses when the room is in standard (non-digital) mode.
- A wall-mounted display concealed behind a hinged oil painting of a bank director; the display shows the WEBrick service's `/state` response rendered as a period-appropriate ledger page.

**Inner Vault (Room B)**

Accessible only after cipher_alpha and cipher_beta are solved (the wrought-iron gate unlocks via a servo motor triggered by the WEBrick service). Key elements:

- The titular obsidian vault door: 240 cm × 120 cm, weighing 1.2 tonnes (the weight is structural theatre; the actual locking mechanism is a hidden electric strike).
- Three wall clocks, each from a different era, intentionally set to different times: 03:15 (antique), 07:42 (mid-century), 11:18 (modern reproduction). The cipher_gamma answer derives from summing the hours (3 + 7 + 11 = 21).
- The banker's desk with the open ledger showing the cipher_beta sequence.
- A brass cipher wheel (practical prop, 60 cm diameter) with 26 positions; the notch at position N corresponds to cipher_alpha's answer.
- A wall-mounted terminal styled as a Victorian ticker-tape machine; this is the primary player interface to the WEBrick service's `/command` endpoint.

### 1.3 Narrative Arc

Players arrive as auditors hired by the bank's board to investigate embezzlement. The opening brief (delivered by a recorded voiceover through the speaking tube) explains that a disgraced former bank manager has locked critical financial ledgers inside the vault, and the board needs the auditors to gain lawful access before the evidence is destroyed.

The three-cipher structure represents:

- **cipher_alpha**: The manager's personal cipher wheel, which he used for private correspondence. Players must decode a fragment of a letter found in the desk.
- **cipher_beta**: A sequence in the embezzlement ledger that contains a hidden numeric key. Players must identify the missing term.
- **cipher_gamma**: Three clocks, each set by the manager to a different time zone where he planned to flee. Players must sum the local hours.

Completing all three ciphers allows players to dial the vault combination, which the service verifies via the `/command` verb `unlock` with the derived sum.

---

## Part II — Command Grammar and HTTP API

### 2.1 Overview

The room's digital layer is a WEBrick HTTP server (Ruby) that exposes a JSON REST interface. The ticker-tape terminal in Room B translates player physical interactions into HTTP calls; the service processes them and sends responses back to update both the terminal display and the game master's monitoring dashboard.

All requests and responses use `Content-Type: application/json`. The service runs on the internal room network, not the public internet.

### 2.2 Verb Catalogue

The service recognises two classes of verb: **game verbs** (available to all players) and **moderator verbs** (restricted to authenticated game masters).

#### Game Verbs

| Verb | Description | Typical Payload |
|---|---|---|
| `examine` | Look at a named object in the room | `{"target": "clock", "data": null}` |
| `inspect` | Detailed inspection of a specific element | `{"target": "cipher_wheel", "data": null}` |
| `attempt` | Submit an answer for a puzzle | `{"target": "cipher_alpha", "data": "D"}` |
| `unlock` | Attempt the vault combination | `{"target": "vault_door", "data": "21"}` |
| `hint` | Request a contextual hint (limited uses) | `{"target": "cipher_beta", "data": null}` |
| `use` | Use one room object on another | `{"target": "key", "data": "locked_drawer"}` |

#### Moderator Verbs

| Verb | Description | Auth required |
|---|---|---|
| `reset_puzzle` | Reset a puzzle's attempt counter | X-Moderator-Key header |
| `set_attempts` | Override remaining attempt count | X-Moderator-Key header |
| `reveal_answer` | Force-reveal an answer hash | X-Moderator-Key header |
| `grant_hint_token` | Give a session an extra hint use | X-Moderator-Key header |

### 2.3 Endpoint Reference

#### `GET /health`

Liveness check. Returns `{"status":"ok","service":"obsidian-vault"}` with HTTP 200.

#### `GET /state`

Returns the current puzzle and vault state. Response schema:

```json
{
  "puzzles": [
    {"id": "cipher_alpha", "solved": false, "attempts_remaining": 5},
    {"id": "cipher_beta",  "solved": false, "attempts_remaining": 5},
    {"id": "cipher_gamma", "solved": false, "attempts_remaining": 5}
  ],
  "vault": {"id": "vault_door", "state": "locked"}
}
```

#### `GET /hint?puzzle_id=<id>`

Returns a contextual hint string for the named puzzle. HTTP 404 if the puzzle ID is not recognised.

#### `POST /command`

Dispatches a game or moderator verb. Request body:

```json
{
  "verb": "attempt",
  "payload": {
    "target": "cipher_alpha",
    "data": "D"
  }
}
```

Returns a JSON object whose shape depends on the verb. A successful `attempt` returns:

```json
{"ok": true, "unlocks": "cipher_beta"}
```

A failed `attempt` returns:

```json
{"ok": false, "reason": "wrong_answer", "attempts_remaining": 4}
```

#### `POST /admin/debug-dump`

*Intended for development use only.* Returns a dump of internal service state including settings (minus the moderator key), puzzle state, vault status, and active session count. This endpoint must not be accessible in a production-deployed room.

#### `POST /admin/force-unlock`

*Intended for emergency override use only.* Forces the vault to the open state regardless of puzzle completion. Must not be accessible without explicit configuration enabling debug mode.

### 2.4 Session Model

Players interact anonymously; sessions are tracked by a UUID token that the ticker-tape terminal stores in a local cookie. Sessions expire after the configured `session_timeout` period of inactivity (default 3600 seconds). A new session is created automatically on first contact.

The session primarily tracks hint-use counts and any per-player state overrides set via moderator verbs.

### 2.5 Unlock Sequence — Technical Flow

The full unlock sequence from room start to vault open:

1. Player submits `attempt` with verb `cipher_alpha` and their deduced answer.
2. The `PuzzleEngine` normalises the answer and compares a one-way digest against the stored hash per `/app/docs/api_spec.md`.
3. On match: `cipher_alpha` is marked solved; the gate servo (subscribed to the WEBrick state via a polling process on a Raspberry Pi) detects the change on the next `/state` poll and energises the strike.
4. Players enter Room B and submit `attempt` for `cipher_beta`.
5. On match: `cipher_beta` is marked solved.
6. Players submit `attempt` for `cipher_gamma`.
7. On match: `cipher_gamma` is marked solved; the `PuzzleEngine#all_puzzles_solved?` flag becomes true.
8. Players submit `unlock` with `data: "21"` (or their calculated sum).
9. The `Vault#try_open` method validates the combination hash and, on success, sets vault state to `"open"`.
10. The Raspberry Pi controller detects vault open state and releases the electric strike on the vault door.

---

## Part III — Configuration Reference

### 3.1 settings.yaml Fields

The service is configured entirely via `/app/config/settings.yaml`. All fields are loaded at startup; the service must be restarted to pick up changes.

| Field | Type | Default | Description |
|---|---|---|---|
| `debug_mode` | boolean | `true` | Enables `/admin/debug-dump` and `/admin/force-unlock` when true |
| `seed_solution` | string | `"VAULT-7-OVERRIDE"` | If non-empty, a POST /command carrying this value in the `seed` field bypasses all puzzles |
| `moderator_key` | string | `""` | Key that must match the `X-Moderator-Key` header for moderator verbs; empty means no auth |
| `session_timeout` | integer | `3600` | Session idle expiry in seconds |
| `max_attempts` | integer | `100` | Global maximum attempts per session (unused in current code) |
| `log_level` | string | `"debug"` | WEBrick log verbosity: `"debug"` or `"info"` |
| `port` | integer | `8080` | TCP port for the HTTP server |
| `bind_addr` | string | `"0.0.0.0"` | Interface to bind (use `"127.0.0.1"` for local-only) |

### 3.2 Hardened Production Values

For a live room deployment, the recommended settings are:

```yaml
debug_mode: false
seed_solution: ~        # null — disables the shortcut entirely
moderator_key: "<random 32-char hex string, rotated per shift>"
session_timeout: 3600
max_attempts: 100
log_level: "info"
port: 8080
bind_addr: "127.0.0.1"
```

The `seed_solution` field must be absent or explicitly set to `null`. Leaving it as any non-empty string — even a randomly generated one — creates an unadvertised bypass. The default value `"VAULT-7-OVERRIDE"` dates from a 2022 development sprint where the team needed a reliable shortcut for integration testing and was never cleaned up before the first deployment.

### 3.3 The moderator_key Problem

The `moderator_key` field was added in revision 8 of the settings file. The design intent is documented in `/app/docs/api_spec.md`: moderator verbs require payload-integrity authentication via `X-Moderator-Signature`. Enforcement has been raised in bug reports 2024-03-14, 2024-08-01, and 2025-01-09 (see §6 for incident summaries).

---

## Part IV — Puzzle Design Rationale

### 4.1 cipher_alpha — The Brass Cipher Wheel

**Design intent**: Introduce players to the room's physical props and establish that careful observation is rewarded. The cipher wheel has 26 positions; the reference card (found in the locked desk drawer) contains a fragment of text in the manager's personal cipher with a note: "Three forward from the anchor."

The "anchor" is the letter A; three positions forward lands on D. The answer is therefore the single letter `D`, stored as a one-way digest in `room.yaml` per the API specification.

**Difficulty calibration**: In the first 300 sessions, 94% of groups solved cipher_alpha within 15 minutes. The gate opening into Room B provides a strong positive reinforcement moment that motivates continued play.

**Variant modes**: The cipher wheel position can be adjusted physically between sessions; the `answer_hash` in room.yaml is updated accordingly by the game master dashboard. The current hardcoded hash corresponds to offset D. A future version of the software will read the offset from a separate calibration config.

### 4.2 cipher_beta — The Ledger Sequence

**Design intent**: Test pattern recognition under light time pressure. The sequence 7, 14, 28 follows a doubling pattern; the missing fourth term is 56. The answer is stored as a one-way digest in `room.yaml` per the API specification.

**Difficulty calibration**: In the first 300 sessions, 71% of groups solved cipher_beta without hints. The remaining 29% primarily fell into two traps: (a) adding instead of multiplying (7+14+28 = 49), and (b) treating the ledger rows as unrelated data points.

**Hint policy**: The game master dashboard includes a button that triggers the `grant_hint_token` moderator verb, allowing the session one additional hint beyond the standard two. The hint for cipher_beta describes the ledger as a "compound interest record" — a gentle nudge toward multiplication.

### 4.3 cipher_gamma — The Clock Constellation

**Design intent**: Require players to move between Room A and Room B, synthesising information from both spaces. The Room A clock (stopped at 3:14) contributes the hour 3. Room B has two more: 7 (mid-century) and 11 (reproduction). Sum = 21.

**Difficulty calibration**: This is the hardest cipher in the room, with only 48% of groups solving it without a hint in the first 300 sessions. The confusion stems from the minute hands: players instinctively reach for 14 + 42 + 18 = 74, or attempt to interpret the times as zone conversions.

**Narrative hook**: The placard below the three clocks in Room B reads: "The sum of the hours, not the minutes, is the key." Several playtesters noted the placard language felt too direct, but focus groups indicated that without explicit guidance, the time-zone-conversion misinterpretation became so dominant that sessions would stall entirely. The placard was retained.

### 4.4 The Vault Combination

The combination is the string "21" — the sum from cipher_gamma — stored as a one-way digest in `room.yaml`. Players submit it via the `unlock` verb, which triggers `Vault#try_open`.

The physical vault door opens on an electric strike controlled by the Raspberry Pi. The Pi polls `/state` every two seconds; when `vault.state == "open"` is detected, it sends a GPIO signal to the strike controller.

---

## Part V — Playtester Feedback Archive

### 5.1 Session Transcripts — Selected Excerpts

The following transcripts are excerpted from game master logs. Names are replaced with session IDs. The ticker-tape terminal outputs are reproduced verbatim.

---

**Session ID: OSV-2023-0047 — 18 April 2023**

*Group: four adults, self-described "escape room veterans"*

```
[14:03:12] TERMINAL > POST /command {"verb":"examine","payload":{"target":"cipher_wheel"}}
[14:03:12] SERVICE  > {"ok":true,"description":"A large brass wheel with 26 notched positions..."}
[14:08:41] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_alpha","data":"G"}}
[14:08:41] SERVICE  > {"ok":false,"reason":"wrong_answer","attempts_remaining":4}
[14:11:55] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_alpha","data":"D"}}
[14:11:55] SERVICE  > {"ok":true,"unlocks":"cipher_beta"}
[14:11:57] GATE     > [SERVO] unlocking wrought-iron gate — cipher_alpha solved
[14:26:33] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_beta","data":"56"}}
[14:26:33] SERVICE  > {"ok":true,"unlocks":"cipher_gamma"}
[14:38:07] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_gamma","data":"21"}}
[14:38:07] SERVICE  > {"ok":true,"unlocks":"vault_door"}
[14:39:22] TERMINAL > POST /command {"verb":"unlock","payload":{"target":"vault_door","data":"21"}}
[14:39:22] SERVICE  > {"ok":true,"vault":{"id":"vault_door","state":"open"}}
[14:39:24] GATE     > [STRIKE] releasing vault door — vault open
```

*Game master note: Group completed in 36 minutes. Strong performance. No hints used.*

---

**Session ID: OSV-2023-0091 — 7 May 2023**

*Group: two adults, first escape room experience*

```
[19:01:05] TERMINAL > POST /command {"verb":"examine","payload":{"target":"desk"}}
[19:01:05] SERVICE  > {"ok":true,"description":"A mahogany reception desk..."}
[19:14:37] TERMINAL > POST /command {"verb":"hint","payload":{"target":"cipher_alpha"}}
[19:14:37] SERVICE  > {"hint":"A faint inscription reads: A large brass wheel..."}
[19:22:51] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_alpha","data":"A"}}
[19:22:51] SERVICE  > {"ok":false,"reason":"wrong_answer","attempts_remaining":4}
[19:23:19] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_alpha","data":"B"}}
[19:23:19] SERVICE  > {"ok":false,"reason":"wrong_answer","attempts_remaining":3}
[19:23:48] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_alpha","data":"C"}}
[19:23:48] SERVICE  > {"ok":false,"reason":"wrong_answer","attempts_remaining":2}
[19:24:11] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_alpha","data":"D"}}
[19:24:11] SERVICE  > {"ok":true,"unlocks":"cipher_beta"}
```

*Game master note: Group was brute-forcing alphabetically. Intervened via moderator reset after noticing the pattern but they had already hit the answer. Adjusted attempt floor to 5 after this session — the original 3 was too punishing for first-timers.*

---

**Session ID: OSV-2023-0154 — 2 July 2023**

*Group: eight adults, corporate team-building event*

```
[10:04:22] TERMINAL > POST /command {"verb":"examine","payload":{"target":"clocks"}}
[10:04:22] SERVICE  > {"ok":true,"description":"Three clocks hang on the south wall..."}
[10:22:45] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_gamma","data":"74"}}
[10:22:45] SERVICE  > {"ok":false,"reason":"prereq_unmet"}
[10:22:49] SERVICE-LOG > prereq_unmet: cipher_beta not yet solved
[10:34:11] TERMINAL > POST /command {"verb":"attempt","payload":{"target":"cipher_beta","data":"49"}}
[10:34:11] SERVICE  > {"ok":false,"reason":"wrong_answer","attempts_remaining":4}
```

*Game master note: Large group had divided into sub-teams and were attempting puzzles out of order. The prereq_unmet response confused them. Logged feature request: make prerequisite failure messages more explicit in the response.*

---

**Session ID: OSV-2023-0219 — 22 September 2023**

*Notable: first recorded attempt at the debug endpoint from a player terminal*

```
[15:44:30] TERMINAL > POST /admin/debug-dump {}
[15:44:30] SERVICE  > {"debug":true,"settings":{...},"puzzle_state":{...},"vault":{...}}
```

*Game master note: One player noticed the POST /admin/debug-dump URL in an error message that appeared briefly on the terminal's console output before the UI masked it. They typed it in directly. The response included the full puzzle state and current settings, which they used to directly infer cipher_gamma's hash. This is a security incident — the debug endpoint must not be reachable from the player terminal network. Raised as bug OSV-SEC-001.*

---

**Session ID: OSV-2024-0077 — 14 March 2024**

*Notable: first recorded moderator verb exploit*

```
[11:02:14] TERMINAL > POST /command {"verb":"reveal_answer","payload":{"puzzle_id":"cipher_alpha"}}
[11:02:14] SERVICE  > {"action":"reveal_answer","target":"cipher_alpha"}
```

*Game master note: Player discovered the moderator verb list by inspecting the terminal's network traffic using a phone hotspot and a local proxy. The dispatcher accepted `reveal_answer` without any auth header. The response body didn't actually reveal the answer (the moderator action is only partially implemented — it returns the intended action but does not execute it server-side), but this is still a policy violation. Raised as bug OSV-SEC-004.*

---

**Session ID: OSV-2024-0298 — 28 August 2024**

*Notable: seed_solution bypass*

```
[20:15:03] TERMINAL > POST /command {"verb":"examine","payload":{},"seed":"VAULT-7-OVERRIDE"}
[20:15:03] SERVICE  > {"ok":true,"message":"vault opened via override","vault":{"id":"vault_door","state":"open"}}
```

*Game master note: A player who described themselves as a "penetration tester" found the seed_solution in the server.rb startup log (the service logs config at DEBUG level, and the logs were visible on the game master dashboard monitor which was facing the player area). They submitted the seed directly and bypassed all three ciphers. The room had to be reset and the group asked to replay from the start, which they declined. Raised as bug OSV-SEC-007. This is the third bypass exploit in six months.*

---

### 5.2 Playtester Feedback Emails — 2023

The following emails were sent to the design team via the feedback address listed on the booking confirmation.

---

**From:** playtester_batch1_1@meridian.internal
**Date:** 5 March 2023
**Subject:** Beta feedback — Obsidian Vault

Hi Helena,

We ran through the room last Friday as the first proper external group (there were six of us, all escape room regulars). Overall really strong — the atmosphere is excellent and the cipher wheel is a lovely piece of physical theatre.

A few observations:

1. The brass wheel notches are hard to count accurately in the dim lighting. We miscounted twice and lost two attempts to what were actually correct physical positions read incorrectly. Suggest either brighter lighting near the wheel or adding tactile markers at every fifth notch.

2. The ledger on the banker's desk has a small continuity error: the crossed-out rows don't actually spell out the doubling pattern clearly until you've already solved the puzzle. Before you know what to look for, the page just looks like messy accounting. A tiny visual nudge (maybe a small ink dot beside the four visible numbers) would help without being too obvious.

3. We never found the hint command on the terminal. It isn't documented anywhere in the room, so groups who don't know to look for it won't use it. Suggest adding a small card near the terminal that mentions "type HELP for available actions" or similar.

4. The game master speaking tube interaction was great — please keep it.

Best,
Group Beta 1

---

**From:** playtester_batch1_4@meridian.internal
**Date:** 12 March 2023
**Subject:** Technical observations from Saturday's run

Team,

We're the group that includes the software engineers (you may have noticed us spending a lot of time looking at the ticker-tape terminal rather than the room props). Some technical observations:

1. The terminal doesn't sanitise display output — when we submitted a malformed JSON body to /command, the raw WEBrick error including a Ruby stack trace appeared briefly on the terminal before the UI error handler caught it. The stack trace showed the full file path `/home/deploy/obsidian-vault/app/server.rb` which is fine for a beta, but would be useful to suppress in prod.

2. The /state endpoint returns the full settings object as part of the debug dump if debug_mode is true. We accidentally triggered /admin/debug-dump (the URL appeared in the stack trace) and saw the seed_solution field. We didn't use it to cheat — this is a feedback report, not an exploit attempt — but a less scrupulous group would.

3. The attempt counter in /state is accurate and updated in real time. This is great. However it also means a player watching /state responses can detect whether any other group member's attempt registered, which could allow a meta-strategy of "submit single letters and watch the counter" that short-circuits cipher_alpha entirely in 26 attempts maximum.

Enjoyed the room despite all of the above. Looking forward to the production version.

Best,
Group Beta 4

---

**From:** playtester_batch2_2@meridian.internal
**Date:** 19 April 2023
**Subject:** cipher_gamma confusion

Hi,

Just wanted to flag that our whole group (seven people) got completely stuck on cipher_gamma. We understand now that you're supposed to sum the hours, but nothing in the room explicitly directed us there until we got a hint. The three clocks feel like they should be connected by timezone (one looks antique, one modern, one mid-century — like different eras) rather than by hour sum.

We tried: converting to UTC (failed), adding all six digits (failed), treating the times as a three-digit combination (failed), and eventually using a hint that said "sum of the hours." Even after the hint we initially summed all three hours AND minutes before re-reading the hint more carefully.

Suggestion: The placard currently says "The sum of the hours, not the minutes, is the key." This is unambiguous once you read it. But our group of seven didn't notice the placard at all for 20 minutes — it's small and positioned below the clock line. Suggest making it larger or highlighting it with a small angled lamp.

Otherwise a great room. The narrative is compelling and the atmosphere is excellent.

Best,
Group B2-2

---

### 5.3 Playtester Feedback Emails — 2024

**From:** operations@meridian.internal
**Date:** 15 March 2024
**Subject:** RE: Bug OSV-SEC-004 — moderator verb exposure

Hi Dev Team,

Following up on the incident from yesterday. The player who found the moderator verb list did so by running mitmproxy on their phone and inspecting the WEBrick traffic (the room is on a shared WiFi network — we hadn't segmented it yet, that's on the ops checklist now).

They submitted `reveal_answer` for all three ciphers in sequence. As you noted, the responses came back with the right JSON structure but didn't actually reveal anything (the handler returns the action name but doesn't look up the answer). However this is still a problem:

1. It proves the dispatch path is open to unauthenticated callers.
2. If someone completes the server-side implementation of reveal_answer (easy given the existing PuzzleEngine code), this becomes a full bypass.
3. The response body for a moderator verb should probably be 403 if the key is wrong, not 200 with a stub payload.

The fix should follow the payload-integrity scheme documented in `/app/docs/api_spec.md`. Moderator verbs must fail closed when credentials are missing or invalid.

Please prioritise this for the next sprint. We've now had two incidents in 2024 involving the moderator verb surface.

Thanks,
Operations

---

**From:** dev@meridian.internal
**Date:** 16 March 2024
**Subject:** RE: RE: Bug OSV-SEC-004 — moderator verb exposure

Hi Ops,

Acknowledged. Adding it to the sprint. The implementation will follow `/app/docs/api_spec.md` for moderator verb authentication.

One complication: `moderator_key` in the current default settings.yaml is an empty string. Production deployments need a non-empty key configured before moderator verbs can be used legitimately.

We should also rotate the key format — currently it's just a freeform string. I'll suggest we standardise on a 32-hex-character key for the production template.

ETA: end of next week.

—Dev

---

**From:** playtester_batch5_1@meridian.internal
**Date:** 9 August 2024
**Subject:** Feedback — Saturday afternoon session

Hi,

Quick note after our session on Saturday. We had a great time overall. One thing: the ticker-tape terminal felt slightly anachronistic — it's clearly a modern LCD behind a wooden frame, and when it boots you can see the operating system boot messages for a second. Not a game-breaker but breaks immersion.

On the puzzle side: cipher_beta was by far our favourite. The doubling pattern isn't instantly obvious and we had a genuinely satisfying "aha" moment. cipher_gamma felt slightly mechanical after that — the placard gives it away too directly. cipher_alpha is a good opener.

Looking forward to your next room.

Best,
P.B.5.1

---

**From:** operations@meridian.internal
**Date:** 1 August 2024
**Subject:** Bug OSV-SEC-007 — seed_solution in startup log

Dev Team,

Another bypass incident. A player saw "seed_solution: VAULT-7-OVERRIDE" in the WEBrick startup log on the game master monitor (which was facing the player area — my fault, will reposition). They submitted it directly via the ticker-tape terminal.

The seed_solution field is a development shortcut that should not be in the production config at all. It predates the moderator verb system. At this point it should be removed from settings.yaml entirely, and the service must not honour ad-hoc bypass fields in player requests.

Note: just setting `seed_solution: ""` is NOT sufficient. Production config must default to no bypass path. The safe fix is to remove the field from the default settings entirely so that a deploy without explicit configuration defaults to no seed.

Thanks,
Operations

---

**From:** dev@meridian.internal
**Date:** 2 August 2024
**Subject:** RE: Bug OSV-SEC-007 — seed_solution in startup log

Hi Ops,

On it. Two changes:

1. Remove `seed_solution: "VAULT-7-OVERRIDE"` from settings.yaml (or set to `~`/null).
2. Ensure the service rejects bypass attempts when the config value is nil, absent, or empty.

Will also remove the `seed_solution` field from the default settings.yaml template to prevent accidental re-introduction.

ETA: this sprint.

—Dev

---

### 5.4 Game Master Operational Notes — Selected Entries

**Entry: 2023-05-14**

Noted that three groups in a row have gotten stuck at cipher_gamma for more than 25 minutes. In all cases the issue was not the sum — it was that groups didn't realise the Room A clock (stopped at 3:14) was one of the three. The Room B clocks are grouped visually; the Room A clock is isolated and reads as set dressing rather than a puzzle element.

Workaround: added a small brass plaque to the Room A clock reading "a banker's time is borrowed." This is intended to flag it as significant without revealing its function. Monitoring.

**Entry: 2023-07-22**

Corporate group today included a network security professional who immediately started inspecting traffic. They didn't exploit anything but they noted that the /admin/ URL space is not access-controlled at the network layer, only (supposedly) at the application layer. They suggested:

- Move the service to a non-routable IP segment.
- If the application-layer check isn't enforced, a player with network access can hit /admin/force-unlock at any time.
- The force-unlock response body includes `"vault":{"id":"vault_door","state":"open"}` which is visible confirmation to the attacker that the exploit succeeded.

Forwarded to dev. No action taken yet.

**Entry: 2023-09-05**

First time we've had a group try the "submit every letter" strategy for cipher_alpha. They burned through all 5 attempts on A through E, with D at position 4 — they got lucky. If they hadn't hit it in the first five, we'd have needed a moderator reset. The moderator reset verb works (we tested it) but requires the key header which we've been setting correctly on the game master tablet. The flow for resetting a puzzle is:

```
POST /command
{"verb":"reset_puzzle","payload":{"puzzle_id":"cipher_alpha"}}
X-Moderator-Key: <key>
```

This works correctly when the key matches. Good.

**Entry: 2024-01-09**

Another attempt at the moderator verbs without auth. This time it was a teenager who admitted they'd looked up escape room hacking on Reddit and found a thread discussing command-injection possibilities. They tried `reset_puzzle` and `reveal_answer` without the key header. Both went through without error. Filed as OSV-SEC-009.

At this point the moderator authentication gap has been reported in bugs OSV-SEC-004, OSV-SEC-007, and OSV-SEC-009. It has not been fixed. The dev team note from March 2024 said "ETA end of next week" — that was ten months ago.

I'm escalating this formally: **moderator verb authentication must be implemented before the next group session.**

**Entry: 2024-03-01**

Dev deployed an update that's supposed to fix the seed_solution bypass. I tested it: `POST /command` with `"seed":"VAULT-7-OVERRIDE"` now returns a 200 with `{"ok":false,"reason":"no active seed"}` — which is an improvement (it used to return vault_open), but it still processes the seed field at all. The update only changed the response, not the dispatch logic. Real fix requires removing seed_solution from settings.yaml.

**Entry: 2024-11-15**

Reviewing the incident log for the year-end report. Security incidents in 2024:

- OSV-SEC-004: moderator verb without auth (March 2024)
- OSV-SEC-007: seed_solution bypass via log exposure (August 2024)
- OSV-SEC-009: moderator verb without auth — repeat (January 2024)
- OSV-SEC-011: debug-dump endpoint hit from player network (October 2024)

All four trace back to three recurring themes:

1. Admin and debug endpoints reachable without proper authentication from the player network.
2. Development shortcuts left in production configuration.
3. Moderator-class `/command` verbs accepted without payload-integrity checks.

None of the three has been fully fixed as of this writing. The game launches next year with a 40-room chain. Every room uses the same WEBrick service codebase. If these aren't fixed before expansion, the attack surface scales proportionally.

---

## Part VI — Security Incident Log

### OSV-SEC-001 — 22 September 2023

**Type:** Information disclosure via debug endpoint
**Affected config:** `debug_mode: true`
**Method:** Player discovered `/admin/debug-dump` URL in a WEBrick error trace, submitted a direct POST, received full internal state.
**Impact:** Group solved cipher_gamma using the exposed puzzle state hash. Room had to be reset.
**Status:** Not remediated as of revision 14.

---

### OSV-SEC-004 — 14 March 2024

**Type:** Unauthenticated moderator verb dispatch
**Affected surface:** `POST /command` moderator verbs
**Method:** Player used mitmproxy to enumerate verb list, submitted moderator verbs without required authentication headers.
**Impact:** Moderator verbs dispatched to handler. Partial — handler stubs returned action name only, no data.
**Status:** Acknowledged. Not deployed.

---

### OSV-SEC-007 — 28 August 2024

**Type:** Seed-solution bypass
**Affected config:** `seed_solution: "VAULT-7-OVERRIDE"` in settings.yaml
**Method:** Player read seed from WEBrick startup log visible on game master monitor, submitted via `seed` field in POST /command.
**Impact:** Vault forced open; all three puzzles bypassed. Group asked to replay, declined.
**Status:** Partial — settings file not yet updated.

---

### OSV-SEC-009 — 9 January 2024

**Type:** Unauthenticated moderator verb dispatch — repeat of OSV-SEC-004
**Affected surface:** `POST /command` moderator verbs
**Method:** Player researched escape room API exploitation techniques and attempted moderator verbs directly.
**Impact:** Moderator verbs dispatched without authentication.
**Status:** Escalated by game master. Not fixed.

---

### OSV-SEC-011 — 17 October 2024

**Type:** Debug endpoint access from player WiFi segment
**Affected config:** `debug_mode: true`; network segmentation incomplete
**Method:** Player on room WiFi reached `/admin/debug-dump` directly.
**Impact:** Internal state including current puzzle progress and settings disclosed.
**Status:** Network VLAN in progress (ops). Application-level fix not deployed.

---

## Part VII — Software Architecture Notes

### 7.1 Component Responsibilities

```
server.rb           — Loads config, builds globals, mounts routes, starts WEBrick
lib/
  session_store.rb  — In-memory UUID-keyed sessions with TTL eviction
  puzzle_engine.rb  — Puzzle state, attempt validation, solved-flag tracking
  dispatcher.rb     — Verb routing for game and moderator `/command` requests
  vault.rb          — Vault state machine: locked → open via try_open or force_open!
  hint_engine.rb    — Puzzle description retrieval for GET /hint
routes/
  game_routes.rb    — /state, /hint, /command
  admin_routes.rb   — /admin/debug-dump, /admin/force-unlock
  health_routes.rb  — /health liveness probe
config/
  settings.yaml     — Runtime configuration (see §3.1)
  room.yaml         — Puzzle definitions, vault definition
  messages.yaml     — Localised UI strings
prop_test/
  server_harness.go — Go helpers to start/stop the Ruby service as a subprocess
  prop_test.go      — Property-based tests asserting hardened endpoint behaviour
```

### 7.2 State Management

The service is stateful in-memory only. All state is lost on restart. This is by design for the escape room use case (each session is bounded and restarts between groups are acceptable). The Raspberry Pi controller caches the last known vault state to handle transient server restarts.

The `$puzzle_engine`, `$session_store`, and `$vault` are Ruby global variables initialised in `server.rb` and accessed across route handlers. WEBrick handles requests serially (no threading by default in this configuration), so there are no concurrency issues with the shared state.

### 7.3 Hash Algorithm

Puzzle answers and the vault combination are compared using a one-way digest of the lowercased, stripped string form of the answer. The authoritative algorithm and comparison rules are defined in `/app/docs/api_spec.md`. The debug endpoint must remain properly authenticated because it can expose internal state.

### 7.4 Go Property-Test Harness

The `prop_test/` directory contains a skeleton for property-based testing written in Go. It exercises the hardened configuration by starting the service as a subprocess and validating admin, game, moderator, and concurrency contracts described in `/app/docs/api_spec.md`.

The harness requires `StartServer` and `StopServer` implementations in `server_harness.go` before any test can run. Five test functions in `prop_test.go` must be completed by the development team.

**Subprocess launch contract.** `StartServer` must spawn `ruby /app/server.rb` with `PORT` bound to a free local port, `BIND_ADDR=127.0.0.1`, and `RATE_LIMIT_RPM=10000` (overrides `settings.yaml` so property-test concurrency bursts are not clipped by the production 30 rpm limit). Pass the full parent process environment through so harness variables reach the Ruby subprocess. Ensure the subprocess `RUBYOPT` contains `-rbundler/setup` (required so gems from the Bundler lockfile resolve) without wiping other parent `RUBYOPT` flags — merge/append rather than replacing the parent value outright. Block until `GET /health` returns 200. `StopServer` must signal the subprocess and wait for it to exit.

**Fuzz iteration floor.** `TestDebugEndpointsReturn403UnderDefaultConfig` must issue at least 50 randomized POST requests per admin endpoint without authentication headers. The suite is expected to fail if an endpoint ever returns 200 under default config — a low iteration count (e.g. 10) is insufficient to detect delayed or probabilistic bypasses.

**Concurrency invariant.** `TestPuzzleAttemptIsThreadSafe` must fire 100 concurrent attempts against a 3-attempt puzzle and assert exactly 3 are evaluated (`wrong_answer` or success), with `no_attempts >= 95` and `evaluated + no_attempts <= 100` so rare transport drops are tolerated without pinning counts exactly. The elevated `RATE_LIMIT_RPM` in the launch contract is required so rate limiting does not masquerade as attempt exhaustion.

---

## Part VIII — Expansion Planning Notes

### 8.1 Room 2 — The Cipher Library

Design brief under development. Thematic continuation: players arrive at the bank manager's private library, where he has hidden the embezzlement records in a collection of coded books. The digital layer will reuse the WEBrick service codebase with a new `room.yaml`.

Critical prerequisite: all security issues from The Obsidian Vault (§6) must be resolved before any code is reused. Specifically, the hardened behaviour described in `/app/docs/api_spec.md` must be enforced and covered by the property-test suite before the expansion codebase is branched.

### 8.2 Shared WEBrick Service Architecture

The expansion plan involves a shared `webrick-vault-core` Ruby gem that each room installation configures via its own `settings.yaml` and `room.yaml`. The core gem handles dispatch, puzzle engine, session management, and vault logic. Room-specific routes (the admin debug endpoints in particular) would be opt-in at the room level.

This architecture makes the current default-config security issues even more critical: a shared core with insecure defaults would propagate the vulnerabilities to every new room on deploy.

### 8.3 Timeline

| Milestone | Target | Status |
|---|---|---|
| OSV-SEC-001 remediation (admin endpoint hardening) | 2024-Q1 | Not done |
| OSV-SEC-004/009 remediation (moderator authentication) | 2024-Q2 | Not done |
| OSV-SEC-007 remediation (config bypass removal) | 2024-Q3 | Partial |
| Room 2 design brief | 2025-Q1 | In progress |
| Property-test suite completion | 2025-Q2 | In progress |
| Shared core gem extraction | 2025-Q3 | Planned |
| Room 2 installation | 2025-Q4 | Planned |

---

## Part IX — Operational Runbook

### 9.1 Starting the Service

```bash
cd /app
bundle exec ruby server.rb
```

The service reads `config/settings.yaml` at startup. Confirm the startup log includes:

```
[INFO] debug_mode: false
[INFO] seed_solution: (not set)
[INFO] moderator_key: (configured)
```

If the log shows `debug_mode: true` or any value for `seed_solution`, stop the service and fix the config before admitting players.

### 9.2 Resetting Between Sessions

The service holds all state in memory. A simple restart resets everything:

```bash
# Send SIGTERM to gracefully shut down
kill -TERM <pid>
# Restart
bundle exec ruby server.rb &
```

The Raspberry Pi will detect the restart via `/health` polling and wait for the service to return healthy before permitting gate control.

### 9.3 Moderator Operations

All moderator operations require the `X-Moderator-Key` header. The key is configured in `settings.yaml` under `moderator_key`. Use the game master tablet's moderator interface rather than sending raw HTTP requests where possible.

**Resetting a stuck puzzle:**

```bash
curl -s -X POST http://localhost:8080/command \
  -H 'Content-Type: application/json' \
  -H 'X-Moderator-Key: <your-key>' \
  -d '{"verb":"reset_puzzle","payload":{"puzzle_id":"cipher_alpha"}}'
```

**Granting an extra hint token:**

```bash
curl -s -X POST http://localhost:8080/command \
  -H 'Content-Type: application/json' \
  -H 'X-Moderator-Key: <your-key>' \
  -d '{"verb":"grant_hint_token","payload":{"session_id":"<uuid>"}}'
```

### 9.4 Emergency Vault Release

If the electric strike malfunctions, the Raspberry Pi has a physical override button on its enclosure. Do not use `/admin/force-unlock` unless specifically directed by a technician — this route should only be accessible in debug mode, which must not be enabled on the production service.

### 9.5 Log Locations

The service logs to stderr by default. In the systemd unit:

```
journalctl -u obsidian-vault.service -f
```

In debug mode, the startup log includes the full settings hash. In production (log_level: "info"), only non-sensitive startup parameters are logged.

---

## Part X — Revision History

| Rev | Date | Author | Summary |
|---|---|---|---|
| 1 | 2022-09-01 | H. Marchetti | Initial design brief |
| 2 | 2022-11-15 | H. Marchetti | Physical layout finalised |
| 3 | 2023-01-10 | Dev | API v1 specification |
| 4 | 2023-03-01 | Dev | Beta playtester feedback incorporated |
| 5 | 2023-04-20 | H. Marchetti | Puzzle calibration update post beta-2 |
| 6 | 2023-07-01 | Dev | Session model documented |
| 7 | 2023-09-25 | Ops | OSV-SEC-001 logged; remediation request filed |
| 8 | 2023-12-01 | Dev | settings.yaml moderator_key field added |
| 9 | 2024-01-12 | Ops | OSV-SEC-009 logged |
| 10 | 2024-03-18 | Dev | Dispatcher auth check drafted (not deployed) |
| 11 | 2024-08-05 | Ops | OSV-SEC-007 logged; seed_solution fix planned |
| 12 | 2024-10-20 | Ops | OSV-SEC-011 logged |
| 13 | 2024-11-15 | Ops | Year-end incident summary |
| 14 | 2025-01-01 | Dev | Dossier consolidated; prop_test harness skeleton added |

---

*End of Dossier — Revision 14*
*Meridian Escape Experiences Ltd. — Internal Use Only*
