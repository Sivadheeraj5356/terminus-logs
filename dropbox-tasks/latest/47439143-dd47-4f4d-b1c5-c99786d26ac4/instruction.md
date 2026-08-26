The Sender Authorization Policy engine under /app/environment/engine is the
decision core of a mail anti-spoofing check: given a domain's published policy and
a frozen DNS-like zone, it decides whether a connecting client IP is authorized to
send mail for that domain. The semantics that policy is intended to have are
written out in /app/environment/docs/sap-spec.md, and a few worked runs of the
engine are in /app/environment/testdata/examples. The engine as deployed does not
fully honour those semantics: on some queries it answers differently from the
specification, authorizing a sender the policy meant to refuse, or refusing one it
meant to admit. How many such places there are, whereabouts in the engine they
sit, and whether they are independent of one another is for you to establish;
assume nothing about their number or their shape, and note that on a given query
more than one of them may bear on the answer at once.

Your job is to implement the analyzer's decision, at
/app/environment/analyzer/src/analyze.rs, so that for each query in a case file it
reports three things: the result the deployed engine actually produces, the result
the specification requires, and whether the two diverge. When they diverge, it
also names the single settling token, as Part 2 defines. The exact case-file and
certificate shapes are in the specification under Part 2.

The deployed behaviour is not documented anywhere; recover it by reading the
engine under /app/environment/engine, whose sources are the ground truth for what
it does — its comments and its naming are not, so trust what the code computes.
You may build and run the engine as much as you like while working it out. The
intended behaviour is exactly Part 1 of the specification and nothing else, so a
divergence is a place where the engine and the specification disagree, not a place
where either disagrees with real SPF. Everything under /app/environment/engine is
read-only evidence; do not change it. Implement only the analyzer's decision.

The finished analyzer must reach its results on its own, from the zone and the
query. It may not shell out, run the engine, or read anything under
/app/environment/engine at run time: your model of the deployed behaviour has to be
in the analyzer itself, and it is exercised with the engine out of reach. Build it
with rustc from /app/environment/analyzer/src/main.rs. The Rust toolchain is
preinstalled and there is no network access, so do not try to install anything.
JSON reading, zone loading, policy parsing, and certificate writing are already
wired in the scaffold under analyzer/src (json, model, parse, io, main); put your
decision logic in analyzer/src/analyze.rs, whose analyze_query receives the parsed
zone and one query. Do not special-case any domain, address, or byte sequence; the
behaviour must come from the specification and the engine.
