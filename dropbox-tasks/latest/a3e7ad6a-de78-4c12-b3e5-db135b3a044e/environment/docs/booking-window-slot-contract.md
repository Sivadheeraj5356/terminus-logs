# Booking window slot digests

Fleet rollout plans bind decision windows and resource booking intervals so daemon schedulers can refuse drifted timelines.

## Plan export fields

Every plan at /app/output/decision_impact_plan.json must include:

- window_digest — witness over staged lattice decision windows and exclusive flags
- booking_digest — witness over staged lattice resource bookings

## window_digest formula

Collect every decision id present in the lattice windows map. Sort ids lexicographically. For each id emit one UTF-8 line:

decision_id | start | end | exclusive_bit

where start and end are decimal integers from the window, exclusive_bit is the character 1 when the exclusive map marks that decision exclusive otherwise 0, and | is a single ASCII pipe with no spaces.

Join lines with a single newline between them (no trailing newline after the last line). window_digest is the lowercase hex SHA-256 of that payload. An empty windows map yields the digest of the empty string.

## booking_digest formula

For each resource booking emit one UTF-8 line:

pool | decision_id | start | end

Sort those lines lexicographically as whole strings. Join with newlines the same way as window_digest. booking_digest is the lowercase hex SHA-256 of that payload.

## Journal row

Successful plan appends must copy window_digest and booking_digest onto the journal JSON line together with the existing seal fields.

## Additional pack

Scenario pack /opt/verifier-fixtures/odip-holdout-slot exercises exclusive-bit ordering independently from bundled scenarios.
