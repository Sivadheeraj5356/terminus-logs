# Ruleset format

The ruleset is a single JSON array of rule objects. Order in the file matters
only as a tie-breaker; the real evaluation order is derived from priority (see
`evaluation.md`). Rule indices are 0-based and count every rule in the file,
including malformed ones, because the diagnostics point back at them by index.

A rule looks like this:

    {"id":"allow-ssh","action":"allow","src":"10.0.0.0/8","dst":"192.168.0.0/16",
     "port_min":22,"port_max":22,"protocol":"tcp","direction":"inbound","priority":400}

Fields:

- `id` - a non-empty string naming the rule. Ids must be unique across the file.
  A decision reports the id of the rule that decided it.
- `action` - `allow`, `deny`, or `log`. `allow` and `deny` are terminal: the
  first one that matches decides the flow. `log` is non-terminal: a matching log
  rule is recorded and evaluation keeps going (see `evaluation.md`).
- `src` / `dst` - the source and destination address blocks in CIDR notation
  `A.B.C.D/P`, prefix `P` an integer 0 to 32. Both must match. See
  `cidr-math.md`.
- `port_min` / `port_max` - an inclusive destination port range, both integers 0
  to 65535, `port_min` no greater than `port_max`. A single port is the same
  value twice.
- `protocol` - `tcp`, `udp`, `icmp`, or `any`. `any` matches any transport.
- `direction` - `inbound`, `outbound`, or `any`. `any` matches either.
- `priority` - an integer 0 to 1000. Higher priority is consulted first.

## Rules we reject at load time

These checks happen while loading, before any flow is evaluated. A rule that
trips any of them is recorded as a warning and is NOT loaded, but its original
file index is kept so the warning can name it. A rule that trips more than one
check produces more than one warning, all on that same index. The reason codes:

- `bad_id` - `id` is missing or empty. Detail is the literal `(empty)`.
- `dup_id` - `id` repeats an id already used by an earlier rule in the file. The
  first rule to use an id claims it, whether or not that earlier rule was itself
  dropped for some other reason; a later rule repeating it is `dup_id`. Detail is
  the repeated id.
- `bad_action` - `action` is not one of `allow`, `deny`, `log`. Detail is the
  offending action string.
- `bad_proto` - `protocol` is not one of `tcp`, `udp`, `icmp`, `any`. Detail is
  the offending protocol string.
- `bad_direction` - `direction` is not one of `inbound`, `outbound`, `any`.
  Detail is the offending direction string.
- `bad_cidr` - `src` or `dst` is not a valid `A.B.C.D/P`: a missing prefix, a
  prefix outside 0 to 32, or an octet outside 0 to 255. `src` is checked before
  `dst`; a rule with both fields bad produces two `bad_cidr` warnings. Detail is
  the offending block string exactly as written.
- `bad_port` - the port range is malformed: `port_min` below 0, `port_max` above
  65535, or `port_min` greater than `port_max`. Detail is the range as
  `min-max`.
- `bad_priority` - `priority` is below 0 or above 1000. Detail is the value.

Dropping a rule shifts nothing: the surviving rules keep their original file
indices, so a ruleset whose second rule is dropped still has a rule at index 2
and index 3.

## Canonicalization note

A rule that passes every check is loaded, but first its `src` and `dst` blocks
are canonicalized (host bits cleared, see `cidr-math.md`) and the rule matches
by those canonical blocks. If a block was not already canonical, an
informational `normalized` warning is recorded on that rule's index with the
canonical block string as its detail (`src` before `dst`; a rule with both
non-canonical produces two `normalized` warnings). A `normalized` warning does
NOT drop the rule and does NOT count as a dropped rule; the rule still loads and
evaluates. It is the only reason code that is informational rather than fatal.
