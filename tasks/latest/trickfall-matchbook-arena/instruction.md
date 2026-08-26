Trickfall Matchbook Arena

Create `/app/matchbook/matchbook`, an offline Rust command-line analyst for
adversarial Trickfall endgames. Its interface is `./matchbook solve FILE`,
where FILE follows the matchbook protocol at `/app/matchbook/spec.md` and may
contain several independent cases.

For every case, validate the declared trump state, partial trick, remaining
hands, turn order, and card ownership. Determine every card legally available
to the current player. Evaluate each legal choice under optimal partnership
play through the final trick: seats 0 and 2 act together, seats 1 and 3 act
together, and the partnership named by the case is the maximizing side.

Return one JSON record per case in input order. Each record must report the
case identifier, current seat, complete canonical root-move valuations,
canonical best card and value, and the complete canonical principal line.
All legality, winner, optimization, ordering, and response rules are defined
by the protocol.

The command must handle positions with one through five remaining tricks,
including partially played tricks and broken or unbroken trump. Results must
be deterministic and independent across cases. Any malformed or impossible
input must reject the whole file: exit nonzero, write a diagnostic to stderr,
and leave stdout empty. The finished analyst must work for arbitrary
conforming positions without network access or fixture-specific answers.
