# Tidevault runtime boundary

The final image exposes only the Tidevault participant documentation and
`/app/arena` client under `/app`. The root-owned referee, rule implementation,
learned opponent, checkpoint, difficulty configuration, healthcheck, and
private logs live below mode-`0700` `/opt/arena-private`. The checkpoint and
configuration are mode `0600`. The Unix socket is the sole
participant-to-referee path.

The solution-side reference player and its distinct checkpoint are never
copied by the environment Dockerfile. Bootstrap owns the private service
lifecycle and creates only the socket and logs needed for one immutable live
match. The participant runs as UID 65534, while referee and verifier inspection
run as UID 0. Peer credentials make postgame participant accounting independent
of command syntax, framing validity, or client behavior. Each successful public
move is one atomic Gold-placement-plus-Violet-reply transaction; a protected
opponent failure commits neither half.
