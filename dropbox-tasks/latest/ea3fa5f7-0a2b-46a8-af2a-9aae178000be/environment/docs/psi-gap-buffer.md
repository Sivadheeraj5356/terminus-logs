# psi gap buffer

During berth assignment, consecutive loads on the same berth may require a time buffer when pressure ratings are close.

For each candidate berth:

1. Check act psi is within berth psi_min and psi_max inclusive
2. gap_used = previous psi on berth is not null AND abs(act psi - previous psi) < psi_gap
3. start = act berth_start for normal cargo
4. When gap_used is true and cargo is not surge: start = max(berth_start, previous end + berth_gap_min)
5. For surge cargo (surge_cargo_id): start = max(previous end + berth_gap_min, computed start) and gap_used = true
6. end = start + transfer_min

## strict boundary on psi_gap

Step 2 uses a strict less-than comparison against habitat psi_gap. It is not less-or-equal.

- When abs(act psi - previous psi) is strictly less than psi_gap, gap_used is true (for non-surge rows with a previous psi).
- When abs(act psi - previous psi) is exactly equal to psi_gap, gap_used is false.
- When abs(act psi - previous psi) is greater than psi_gap, gap_used is false.

Do not treat equality as a gap. Using <= instead of < flips gap_used on the equality boundary and changes staging_hash.

Berth selection among valid options minimizes (assignment count on berth, start time, berth_id lex).

Record gap_used as boolean on each assignment row.

See berth-staging.md for assignment object schema.
