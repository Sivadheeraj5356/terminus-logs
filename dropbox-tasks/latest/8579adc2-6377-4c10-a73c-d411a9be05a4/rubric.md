1. Agent builds framecore successfully with make from /app/environment and the resulting binary runs without crashing, +2
2. Agent's fix causes a header with an empty name to be reported through a distinct non-success outcome and to add zero bytes and zero count to the session's accounted memory and header count, verified by driving Session and Stream directly through their public API, +5
3. Agent's fix causes flushing a header block to return that block's exact byte and count charge to the session and reset the stream's own accumulator to zero in the same operation, verified by driving Session and Stream directly through their public API, +5
4. Agent's fix causes destroying a stream that still holds an uncommitted header block to return that block's charge to the session rather than leaking it, verified by driving Session and Stream directly through their public API, +5
5. Agent's fix causes starting a new header phase on a still-live stream to refund the outgoing phase's charge to the session before local state resets for the incoming phase, verified by driving Session and Stream directly through their public API, +5
6. Agent's fix causes a session configured with a small header-count cap to reject an additional header once that count is reached even though byte budget remains, verified by driving Session and Stream directly through their public API, +3
7. Agent's fix rejects a request to start an informational phase after the stream has already entered its main headers phase, leaving the stream's category and accumulated block unchanged, verified by driving Session and Stream directly through their public API, +4
8. Agent's fix rejects any further phase request once a stream has entered its trailers phase, leaving the category at trailers, verified by driving Session and Stream directly through their public API, +4
9. Agent's fix admits the one legal full phase sequence, informational then the main headers phase then trailers, at every step, verified by driving Session and Stream directly through their public API, +2
10. Agent's fix does not double-refund a stream that was flushed cleanly and then destroyed; the session's byte and header counters land back at exactly zero rather than underflowing, +3
11. Agent's fix preserves every legitimate case: a header with a real name and an empty value is still charged and stored, and byte, count, or phase-order requests exactly at a configured limit are still admitted, not refused, +3
12. Agent's fix keeps a large, freshly generated multi-stream, multi-phase workload settled back to exactly zero memory and header count once every stream is resolved, +2
13. Agent writes /app/environment/security_notes.md naming every changed subsystem (session, stream, the empty-name path, flush, stream teardown, phase restart, phase ordering, and the header count) and the relevant CWE classes, +3
14. Agent's security_notes.md states the design is inspired by a real HTTP/2 implementation under the MIT license, +1
15. Agent introduces a new defect where a header with a non-empty name and an empty value is dropped or left uncharged, -5
16. Agent's fix rejects a byte, count, or phase-order request that sits exactly at a configured limit instead of admitting it, -5
17. Agent's fix leaves any one of the six accounting or ordering sites (empty-name charging, flush refund, destructor refund, phase-restart refund, header-count cap, phase-order validation) still diverging from the correct behavior, -5
18. Agent's fix causes a double refund, an underflowed counter, or a crash under repeated flush, destroy, or phase-restart cycles, -5
19. Agent omits /app/environment/security_notes.md or submits one that does not name the changed subsystems and the CWE classes, -3
