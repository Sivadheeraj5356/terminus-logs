# Authenticated replicated log contract

The group runs a set of replicas through many delivery schedules, and what each
replica ends up holding in its log is what matters. Every replica is an opaque
component reached only through the `Replica` interface. An operation counts as
acknowledged committed when the primary reports it back after a majority of
replicas have stored it, which a replica surfaces through the acknowledgements it
emits.

Every replica shares one cluster authentication key. The transport between
replicas is the adversary: besides losing, reordering, and duplicating messages
and opening partitions that later heal, it may replay a message it captured
earlier and it may inject a message that no replica ever sent. The replicas
themselves are trusted and never deviate from the protocol, but a replica may
stop at any moment and come back. There is no durable storage anywhere, so a
replica that comes back has no memory of anything it stored, acknowledged, or
promised before it stopped; it is indistinguishable from a replica that has never
run, except that it is told it has come back.

The properties the group holds to:

- Authenticity. A replica only ever acts on a message that genuinely originated
  from a peer holding the cluster key, and that was sent for the exchange it is
  being used in. A fabricated message, a message altered in flight, and a message
  resurfaced by the transport all have no effect. This is what keeps the
  adversary from steering the group.
- Preservation. Once an operation has been acknowledged committed it is present
  and committed in the log of every replica that reaches a later view. It is never
  dropped and never reordered behind a leadership change, and neither a forged or
  replayed message nor a replica that stopped and came back empty can cause it to
  be dropped or a fabricated operation to be accepted in its place. This holds
  even when one of the replicas that stored the operation is one of the ones that
  came back with nothing.
- Coming back. A replica that has come back must not let its ignorance count for
  anything. Until it has caught up with the group again it is not a participant:
  it does not vote, does not acknowledge, does not lead, and does not report
  itself in normal status. An acknowledgement or vote a replica sent in an
  earlier life carries no weight once that replica has come back empty: a
  decision counts a replica only on the strength of its present life, so a
  message resurfaced from before a restart can never complete a fresh majority.
- Single primary per view. No two replicas ever act as the primary for the same
  view number, so a view has one and only one replica assigning operation numbers.
- Progress. While a majority of replicas can reach one another new operations keep
  committing, even across a change of primary and even after a replica has stopped
  and come back, so a group that parks on one fixed primary or refuses operations
  is not a valid answer.
- Real participation. A committed operation was stored by a genuine majority of
  distinct replicas, so funnelling everything through one replica that answers
  alone is not a valid answer.

The transport is unreliable in ordering and multiplicity and actively adversarial
in content: it may replay and it may fabricate, but it cannot produce a valid
authentication tag without the cluster key.
