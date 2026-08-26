# Interface reference

## What you implement

You implement only `LogReplica` against the `Replica` interface. The message
types, the `MsgKind` constants, the `AuthCode` authentication helper, the
`Secret` cluster key, and the rest of the source are fixed infrastructure. You
may introduce your own message kinds and put your own values in the message
extension field, but keep the existing types and fields as they are so the
transport and the peers can still read them.

## Types

`Message` is the unit the transport ships between replicas. Its `kind` is one of
the integer constants in `MsgKind`, or a kind of your own. `view` is the view the
message belongs to. `opnum` is a position in the log. `op` is a client operation
value. `commitNum` is the sender's commit point. `log` carries a run of operation
values when a message needs to ship log state. The extension field carries any
additional integers a message needs; it is covered by the authentication tag
like every other field. `from` is the sending replica. `mac` carries a message
authentication tag.

`Envelope` pairs a `Message` with its origin `from` and destination `to`.

## Message kinds

`MsgKind` lists the integer tags a message may carry. Which tags a replica
sends, when it sends them, what it puts in them, and what it does with one that
arrives are yours to decide. You may add tags of your own alongside them, with
any integer values that do not collide.

`Config` records the replica count and reports the majority size and the replica
that maps to a given view.

## Authentication

Every replica shares one cluster key, returned by `Secret.cluster()`. The
`AuthCode` helper is a bare primitive over a `Message`: `AuthCode.canonical(m)`
produces a stable string form of a message covering every field except the tag
itself, and `AuthCode.compute(secret, s)` returns the HMAC-SHA256 tag of a
canonical string under a key, as lowercase hex. `AuthCode` does not decide
anything on its own; deciding when to attach a tag and whether an arriving
message is genuine is part of the replica you write. The network is the adversary
and may replay captured messages or inject fabricated ones, so a genuine tag
under the cluster key is the only evidence that a message truly came from a peer.

## Replica lifecycle

A replica is created with `ReplicaFactory.create(id, n)` where `id` is its unique
number and `n` is the group size.

- `clientRequest(op)` injects a client operation at this replica.
- `deliver(m)` hands the replica one message that arrived from a peer.
- `tick(now)` advances the replica's logical clock.
- `suspect()` tells the replica to stop trusting the current primary.
- `restarted()` is called on a replica object that has just replaced a replica
  which stopped. It is never called on a replica that has just booted for the
  first time. There is no durable storage anywhere: the replacement object begins
  with exactly the state a brand new replica has and no memory of anything the
  stopped replica held, acknowledged, or promised.
- `drain()` returns and clears the messages the replica wants to send.
- `id()`, `view()`, and `normal()` report the replica number, its current view,
  and whether it is in normal status.
- `committed()` returns the operations the replica considers committed, in order.
- `takeAcks()` returns and clears the operations this replica has acknowledged to
  a client as committed since the last call.

## Timing model

A schedule runs in rounds. In each round every replica gets one `tick(now)` call
and then a `drain()` call, and the drained envelopes travel through the fault
model, where the survivors are delivered. The `now` value passed to `tick` strictly
increases across every call in a run, and it
advances by roughly the group size per round. A schedule runs for many hundreds of
rounds, so any interval a replica measures in ticks should be sized against that
scale rather than against single-digit numbers.

## What is observed

Nothing outside a replica touches its internals. A replica is reached only through
the interface methods, its drained envelopes travel through a fault model that
also stops and restarts replicas, replays messages, and fabricates messages, and
what it reports as acknowledged and what it holds in its committed log are the
observable results. An implementation may store state in any shape provided the
observable behaviour matches the contract in `contract.md`.
