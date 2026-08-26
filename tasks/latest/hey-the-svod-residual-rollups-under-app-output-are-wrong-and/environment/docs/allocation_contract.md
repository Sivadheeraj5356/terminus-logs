# Allocation contract

## Territory-local day

Path: `/app/config/territory_calendar.json` field `iana` per territory.

Convert `capturedAt` UTC to the territory IANA zone.

### DST rules

- **Spring forward gap:** If local time falls in a nonexistent wall-clock hour, advance forward to the next valid local time on the same calendar date when possible; otherwise roll to 00:00:00 on the next calendar date.
- **Fall back ambiguous hour:** When local time is ambiguous, use the offset with the **later** UTC instant (second occurrence).

`dayLocal` = local calendar date `YYYY-MM-DD` after conversion.

Worked examples:

- `2024-03-10T06:30:00Z` in `America/New_York` remains on `2024-03-10` after spring-forward handling.
- `2024-10-27T01:30:00Z` in `Europe/London` is the second occurrence of the ambiguous 01:30 wall-clock hour and maps to `2024-10-27`.

## Weekly week start

`weekStartLocal` = ISO Monday (`YYYY-MM-DD`) of the territory-local week containing `dayLocal`. Compute using the same IANA zone as `dayLocal`.

## Participant split

For each `(workId, territory, periodMonth)` with `netPoolMicroCents > 0`:

1. Load participants for `workId` sorted by ascending `catalogIndex`.
2. `totalWeight = sum(weight)`.
3. For each participant: `floorShare = netPoolMicroCents * weight / totalWeight` (integer division truncating toward zero).
4. `remainder = netPoolMicroCents - sum(floorShare)`.
5. Distribute remainder one micro-cent at a time to participants in **ascending `catalogIndex` order**, cycling from the start until remainder is zero.

Each participant receives one escrow body line with `amountMicroCents = floorShare + remainderUnits`.

Participants with zero total still appear when `netPoolMicroCents > 0` only if they received remainder units; otherwise omit lines with zero amount. For example, with weights `100,0,0` and `netPoolMicroCents = 1`, only the first participant receives an escrow line.

## Sort orders

- Daily rows: `(workId, territory, dayLocal, medium)`
- Weekly rows: `(workId, territory, weekStartLocal)`
- Escrow body lines: `(workId, territory, participantId)`
