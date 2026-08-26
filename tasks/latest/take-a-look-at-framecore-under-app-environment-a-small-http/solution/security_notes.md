# Security Notes, cpp-http2-header-budget-audit

Inspired by Node.js (nodejs/node) CVE-2019-9516 / GHSA-6gw7-c226-vg73, fix
commit dc51a633dc430d0184642f717b1020deb3df19c8 (MIT licensed). The codebase
under /app/environment/ is an original C++ implementation of an HTTP/2-style
transport library that reproduces the same CWE-770 resource-exhaustion class
in its session and stream header-memory accounting, plus a CWE-841 header-
phase ordering gap in the same subsystem; it is not a copy of the upstream
Node.js source.

- **Missing charge-avoidance for empty-name headers** (CWE-770), in
  src/transport/stream.cc, Stream::AddHeader. The unpatched method charged
  and stored a header even when its name was empty, and an empty name can be
  encoded far more cheaply on the wire than the flat per-header overhead it
  was being charged, letting an attacker inflate the session's accounted
  memory much faster than legitimate traffic. The fix returns an ignored
  status before any charge or store when the name is empty, leaving a
  non-empty name with an empty value charged and stored exactly as before.

- **Missing session refund on header-block delivery** (CWE-770), in
  src/transport/stream.cc, Stream::FlushHeaders. The unpatched method moved
  the accumulated header block out to the caller but never released the
  matching charge back to the session's byte and count totals, so the
  session's accounted memory only ever grew across ordinary request
  handling. The fix decrements both session totals by the block's exact
  charge and zeroes the stream's local accumulator in the same operation
  that delivers the block.

- **Missing session refund on stream teardown** (CWE-770), in
  src/transport/stream.cc, the Stream destructor. The unpatched destructor
  did nothing, so a stream torn down while still holding a not-yet-delivered
  header block leaked that charge against the session forever. The fix
  releases any outstanding charge back to the session before the stream
  object is freed, guarded so nothing is released when nothing is
  outstanding.

- **Missing session refund on header-phase restart** (CWE-770), in
  src/transport/stream.cc, Stream::StartHeaders. The unpatched method reset
  the stream's local accumulator for a new header phase (informational,
  main, or trailers) without first releasing the outgoing phase's charge
  back to the session, so every additional phase on a long-lived stream
  permanently burned budget that was never coming back. The fix releases the
  outgoing phase's outstanding charge, guarded the same way as the
  destructor, before local state resets for the new phase.

- **Missing independent header-count cap** (CWE-770), in
  src/transport/session.cc, Session::IsAvailableHeaderCount. The unpatched
  method compared the session's byte total against the byte maximum again
  instead of the header count against the header-count maximum, so a flood
  of minimally-sized headers could pass the byte budget while still costing
  far more real allocation and bookkeeping overhead per header than the
  nominal charge accounted for, and the count maximum was never actually
  enforced. The fix compares the session's current header count plus the
  candidate against the configured header-count maximum, independently of
  the byte budget check.

- **Missing header-phase order enforcement** (CWE-841), in
  src/transport/stream.cc, Stream::StartHeaders. The unpatched method
  accepted a request to begin any phase after any other phase with no
  validation at all, so a stream could be driven from the main headers
  phase back to an informational phase, or into another phase after
  trailers, states the rest of the protocol layer is not built to handle.
  The fix rejects a phase request that does not follow the required order,
  informational phases only before the one main headers phase and trailers
  only as the terminal phase, leaving the stream's category and
  accumulated header block completely untouched when a request is
  rejected; the very first phase a stream ever begins is always admitted.

Every refund site reads the stream's live current_headers_length_ rather
than a cached amount and, in the destructor and StartHeaders, only refunds
when something is actually outstanding, so a stream flushed cleanly and then
destroyed refunds nothing a second time; the session counters are unsigned,
so a blanket double-refund would otherwise underflow to a large value
instead of failing loudly.
