# Sender Authorization Policy: specification

The engine under `/app/environment/engine/` evaluates a **Sender Authorization
Policy** (SAP): a bespoke, SPF-like anti-spoofing check that decides whether a
connecting client IP is authorized to send mail for a domain, by evaluating that
domain's published policy over a frozen DNS-like zone.

**Part 1 is the intended semantics** — what the policy is supposed to mean, and
the whole of it. **Part 2** fixes the case-file and certificate shapes. The engine
as deployed does not fully honour Part 1. What it does instead is written down
nowhere: the sources under `engine/` are the only account of it.

## Part 1 — Policy semantics

### The zone and a query

The **zone** is a fixed map from domain name to a record set. A record set may
carry a `sap` policy string, a list of `a` records (IPv4 address strings), and a
list of `mx` records (host names whose own `a` records are looked up). A domain
absent from the zone, or present with no `sap`, has no policy.

A **query** asks whether one client IP is authorized to send mail for one domain.
Evaluating it yields one of the exact results `PASS`, `FAIL`, `SOFTFAIL`,
`NEUTRAL`, `NONE`, `PERMERROR`. `PASS` is the only result that authorizes the
sender.

The **request domain** is the domain named in the query. It is fixed for the
whole evaluation of that query.

### The policy string

A policy is `v=sap1` followed by whitespace-separated **terms**. A term is either
a **directive** or the **redirect modifier**.

A directive is an optional one-character qualifier followed by a mechanism:

- Qualifier: `+` (Pass), `-` (Fail), `~` (SoftFail), `?` (Neutral). A directive
  with no qualifier defaults to `+`.
- Mechanism, one of:
  - `all` — matches every query.
  - `ip4:<addr>` or `ip4:<addr>/<prefix>` — an IPv4 CIDR block. It matches iff
    the client IP agrees with `<addr>` in the leading `<prefix>` bits, for the
    exact value of `<prefix>` written in the policy. A bare address is `/32`.
    `<prefix>` is a decimal in `0..=32`. Unlike an address octet, `<prefix>` may
    carry leading zeros: `/08` and `/8` are the same prefix, and a leading-zero
    prefix is not malformed.
  - `a` or `a:<domain>` — matches iff the client IP is one of the target
    domain's `a` records.
  - `mx` or `mx:<domain>` — matches iff the client IP is an `a` record of any
    `mx` host of the target domain.
  - `include:<domain>` — evaluate `<domain>`'s policy (see below).

  A mechanism written bare (`a`, `mx`) takes the request domain as its target;
  written with an argument (`a:<d>`, `mx:<d>`) it takes `<d>`.

The modifier is `redirect=<domain>` (at most one per policy).

An address octet is `0` or a non-zero-leading decimal in `0..=255`. A policy that
does not begin with `v=sap1`, names an unknown mechanism, carries a malformed
`ip4` CIDR, has an empty `include:`/`redirect=` target, or repeats `redirect=` is
invalid; evaluating it yields `PERMERROR`.

### Evaluation

To evaluate a domain's policy:

1. If the domain has no policy → result `NONE`.
2. Parse the policy; on any syntax error → `PERMERROR`.
3. Scan the **directives left to right**. The **first** mechanism that matches
   settles the result: the matching directive's qualifier mapped to
   `PASS` / `FAIL` / `SOFTFAIL` / `NEUTRAL`. Directives after it are not
   considered.
   - `all` always matches.
   - `ip4` matches by CIDR containment.
   - `a` / `mx` match by the zone lookup above.
   - `include:<d>` matches **iff** evaluating `<d>`'s policy yields `PASS`; any
     other result (`FAIL`, `SOFTFAIL`, `NEUTRAL`, `NONE`) is **not** a match and
     the scan continues. If evaluating `<d>` yields `PERMERROR`, the whole
     evaluation is `PERMERROR` immediately.
4. If no directive matched: if a `redirect=<d>` is present **and the policy has no
   `all` directive**, the result is the result of evaluating `<d>`'s policy (and
   if `<d>` has no policy, `PERMERROR`). Otherwise the result is `NEUTRAL`.

### Limits

Evaluating a query may perform at most **8** lookup terms. Each `a`, `mx`,
`include`, and `redirect` term consumes one unit of the budget, counted across the
entire evaluation. The unit is charged when the term is reached, before its
lookup. If a term would push the count above 8, evaluation halts with
`PERMERROR`. `all` and `ip4` never consume budget.

Independently of that budget, an evaluation follows policies into other domains
at most **32** levels deep; a 33rd yields `PERMERROR`. This bound exists only so
that a zone whose policies delegate in a cycle terminates.

## Part 2 — The differential certificate

The analyzer under `/app/environment/analyzer/` reads a **case file** (JSON)
whose path is its single argument:

```
{ "zone": { "<domain>": { "sap"?: "<policy>", "a"?: ["<ip>",...], "mx"?: ["<host>",...] }, ... },
  "queries": [ { "id": "<string>", "domain": "<domain>", "ip": "<dotted-quad>" }, ... ] }
```

Every `ip` is a well-formed dotted-quad. It prints one certificate per query, in
the order the queries appear:

```
{ "queries": [ { "id": "<string>", "deployed": "<result>", "intended": "<result>",
                 "divergent": <bool>, "witness": <string|null> }, ... ] }
```

- **`deployed`** — the result the frozen engine actually produces for the query.
- **`intended`** — the result Part 1 requires for the query.
- **`divergent`** — `true` iff `deployed` and `intended` differ.
- **`witness`** — for a divergent query, the **settling token** (below) of one
  side; `null` for a non-divergent query.

### The settling token

A result is **settled by a directive** when that directive's qualifier produced
it; the token is the directive exactly as it appears in the policy string,
qualifier included (`"-all"`, `"+ip4:203.0.113.0/25"`, `"a"`). Where a
`redirect=` supplies the result, the settling directive is the one inside the
policy that supplied it, not the modifier. A `NEUTRAL` reached because nothing
matched and no `redirect=` applied, a `NONE`, and a `PERMERROR` are settled by no
directive.

For a divergent query the witness is drawn from the **authorizing side**: the
`deployed` side when `deployed` is `PASS`; otherwise the `intended` side when
`intended` is `PASS`; otherwise the `deployed` side. If the chosen side's result
is settled by no directive, the witness is the string `"-"`.
