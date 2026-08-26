Trickfall Matchbook Protocol, version 1

The analyst is invoked from `/app/matchbook` as `./matchbook solve FILE`.
FILE is UTF-8 text. Success emits one JSON object per input case and exits
zero. Failure emits a diagnostic on stderr, exits nonzero, and emits nothing
on stdout. The entire file is accepted or rejected as one unit.

File format

Blank lines are ignored. Comments are not recognized. The first nonblank line
is exactly `matchbook 1`. It is followed by one or more case blocks with this
line order:

    case ID
    trump SUIT
    broken BOOLEAN
    leader SEAT
    maximize TEAM
    tricks COUNT
    table [CARD ...]
    hand 0 [CARD ...]
    hand 1 [CARD ...]
    hand 2 [CARD ...]
    hand 3 [CARD ...]
    end

Tokens are separated by ASCII whitespace. No line accepts trailing tokens
other than the card lists on `table` and `hand`. ID is 1 to 32 characters
from ASCII letters, digits, underscore, and hyphen, and is unique within the
file. SUIT is one of `S`, `H`, `D`, `C`. BOOLEAN is `true` or `false`. SEAT is
0 through 3, TEAM is 0 or 1, and COUNT is 1 through 5.

Cards use a suit followed by a rank. Suits are `S H D C`; ranks are
`7 8 9 T J Q K A`. Every listed card is unique across the table and all four
hands. A table contains zero through three cards. Its first card was played
by the leader and subsequent cards were played clockwise. The current seat is
`(leader + table length) mod 4`.

COUNT is the number of tricks still to be completed, including the current
partial trick. A seat already represented on the table holds COUNT-1 cards;
each other seat holds COUNT cards. Table cards must describe legal play from
the declared hands immediately before the current trick. The `broken` value
is the trump state at the beginning of that trick.

Play rules

Seats play clockwise. A follower holding the led suit must play that suit; a
void follower may play any card. On an empty table, trump may not be led while
unbroken if the leader holds a non-trump card. A leader holding only trump may
lead trump. Trump becomes broken as soon as any trump card is played.

After four plays, the highest-ranked trump wins if the trick contains trump.
Otherwise, the highest-ranked card of the led suit wins. Discards cannot win.
The winner leads the next trick. Rank strength from low to high is
`7 8 9 T J Q K A`.

Seats 0 and 2 form team 0; seats 1 and 3 form team 1. At every turn, a seat on
the maximizing team chooses a continuation that maximizes that team's number
of won tricks across the COUNT remaining tricks. An opposing seat minimizes
that number. Both sides have complete knowledge of all hands.

Canonical choice order from low to high compares rank first, then suit in
`S H D C` order. Whenever several choices have the same optimal value, the
lowest choice in this order is canonical. This tie rule applies at every turn.

Output

Each case produces one JSON object with these fields:

    {"case":"ID","turn":SEAT,"moves":[{"card":"CARD","value":N}],"best":"CARD","value":N,"line":["CARD"]}

`moves` contains every legal current card in canonical order and its optimal
value for the maximizing team. `best` is the canonical optimal current card,
and `value` is its value. `line` is the complete canonical principal line,
starting with `best` and ending with the last card of the position. Its length
equals the total number of cards initially held in the four hands. Values are
integers from zero through COUNT. Case responses retain input order.

Invalid invocation, unreadable input, invalid UTF-8, missing or extra blocks,
wrong line order, malformed or duplicate values, inconsistent hand sizes,
illegal table play, or any other protocol violation is an error.
