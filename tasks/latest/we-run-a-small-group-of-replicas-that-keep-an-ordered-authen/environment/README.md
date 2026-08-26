# Authenticated replicated log group

This module is a small group of replicas that keep an ordered, authenticated log
of client operations consistent while leadership moves between them and the
network actively works against them. One replica at a time acts as the primary
for a view, assigns each operation its position in the log, and copies it to the
others. An operation is acknowledged to the client once a majority of replicas
have stored it. When replicas stop trusting the primary the group moves to the
next view and a different replica takes over.

Every replica shares one cluster authentication key. The transport is the
adversary: it drops, reorders, and duplicates messages, opens and heals
partitions, replays messages it captured earlier, and injects messages that no
replica ever sent. Replicas also stop and come back, and nothing survives a stop:
a replica that comes back has no memory of anything it did before.

## Interface

You implement only `LogReplica` against the `Replica` interface in `/app/src`.
The message types, the `MsgKind` constants, the `AuthCode` authentication
primitive, the `Secret` cluster key, and the rest of the source are fixed
infrastructure.
You may add your own message kinds and carry your own integers in the message
extension field as long as the existing types and fields stay intact.

- `clientRequest(op)` injects a client operation.
- `deliver(m)` delivers one message from a peer.
- `tick(now)` advances the replica's logical clock.
- `suspect()` tells the replica to stop trusting the current primary.
- `restarted()` tells a freshly constructed replica that it is replacing one that
  stopped, rather than booting for the first time.
- `drain()` returns and clears outgoing messages.
- `committed()` returns the committed operations in order.
- `takeAcks()` returns operations acknowledged committed since the last call.

Construct a replica with `ReplicaFactory.create(id, n)` where `n` is the group
size. The message, envelope, and authentication types are defined alongside the
interface and `/app/docs/interface.md` describes each field, the message
extension field, and the timing model. `/app/docs/contract.md` states the full
set of guarantees the group keeps.

## What the group must guarantee

A replica acts only on genuinely authenticated messages that belong to the
exchange they are used in, so a forged, altered, or replayed message can never
drop a committed operation or slip in a fabricated one. An acknowledgement a
replica sent before it came back empty carries no weight, so a message resurfaced
from a replica's earlier life cannot complete a fresh majority. Once an operation
has been acknowledged committed it stays present and committed through every later
view and through any replica stopping and coming back empty, no two replicas act
as primary in one view, and while a majority of replicas can reach each other new
operations keep committing.

## Building

    bash /app/build.sh
    bash /app/smoke.sh

The seeds in `/app/harness` put the group through nine schedules: a steady
primary, a clean handover, a minority partition, a schedule in which the
transport injects a message that no replica sent, a stop and return of a
replica, a replay of a genuine captured message, a returning replica whose
acknowledgement from an earlier life is replayed to the primary, a replica that
stops and returns more than once across a view change, and a schedule that
reorders, duplicates, and transiently partitions traffic. Each run shows whether
every acknowledged operation survived, whether an operation no client submitted
was accepted, and whether the group kept committing. These nine seeds are only
examples: the group holds its guarantees on schedules well beyond them, under
the same fault model.
