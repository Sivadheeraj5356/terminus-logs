# The Chan referee's handbook

Chan (chan bi tu) is played with the hundred-card To Tom subset: the deck keeps
ranks two through nine in the three suits van (v), van/wen (n) and sach (s), plus
the lone honour chi chi (ci) — twenty-five kinds, four copies of each. A card is
written as its rank digit and suit letter (for example 9v, 3s, 7n) or the bare
token `ci`. Five kinds are printed in red: 9v, 9s, 8v, 8s and ci.

A player is "round" and wins (u) when nineteen concealed cards plus the winning
card fall into ten units. A unit is either a **chan** — two identical cards — or
a **ca** — two cards of the same rank in different suits (never the honour). The
referee keeps a plain account of the finished hand: it confirms the declaration,
names the honours, totals the diem, charges any fines the discard log triggers,
and settles the four seats A, B, C, D.

## The record

The account is derived from one record, all ASCII, one item per line, the whole
record ending in a newline. No line may be empty, hold a leading or trailing
space, a double space, a tab, or a carriage return.

1. `CHAN/1`
2. `win <seat> <role> <source> <streak>` — seat is A, B, C or D; role is `dealer`
   or `nondealer`; source is `deal`, `draw`, `gate` or `stock` (how the winning
   card arrived); streak is `fresh` or `thong`.
3. `uu <card>` — the winning card.
4. `hand <nineteen cards>` — the concealed hand before the winning card.
5. `layout <unit>;<unit>;...` — exactly ten units. The first unit is the winning
   unit and must contain the winning card; the other nine may be given in any
   order.
6. `log`
7. and on — zero or more `toss <seat> <card> <round>` lines, the discards other
   seats let go. Rounds are whole numbers, at least one, and never decrease.

A chan is written `chan(<card>,<card>)` with two identical cards; a ca is written
`ca(<card>,<card>)` with two same-rank, different-suit cards, neither being ci.

## When the record is faulty

If the record breaks a rule above, the whole account is two lines: `Fault =
line:<n> reason:<r>` then `Result = void`. The referee stops at the first fault,
testing in this order:

- `malformed` — any structural or token violation above; `<n>` is the first
  offending line. An incomplete record — one with fewer lines than the fixed
  header and log require — is faulted at the first absent line, before any
  wrong-token check on the lines present, so a record that stops short reports
  the missing line rather than a defect on a line already given; this is why
  the lone `stop` line reports `line:2`, not `line:1`.
- `bad-hand` — some kind would appear more than four times across the twenty
  cards; `<n>` is 4.
- `bad-layout` — the units are not exactly ten, a unit's cards do not match the
  concealed hand plus the winning card as a multiset, or the first unit does not
  contain the winning card; `<n>` is 5.
- `bad-log` — a toss round is below one or below the round before it; `<n>` is
  that toss line.

## The account of a win

A legal record produces these lines in this exact order:

```
Chan = bi-tu 100-card
Winner = <seat>
Source = <role>/<source>/<streak>
Uu = <card>
Wait = <banthu|thuong>
Layout = <winning unit>;<the other nine units, canonical order>
Reds = <count of red cards among the twenty>
Cuoc = <honour tokens joined by commas, or xuong>
Diem = <total>
<a Phat line per fine, or "Phat = none">
Settle A = <net>
Settle B = <net>
Settle C = <net>
Settle D = <net>
Result = uu
```

**Card order.** Cards sort by suit v, then n, then s (each with ranks two to nine
ascending), and finally ci. The two cards inside a unit are printed in that order.

**Canonical layout.** The winning unit is printed first, exactly as declared but
with its two cards in card order. The remaining nine units follow, chan units
before ca units, and within each block by the lower card then the higher card.

**Wait.** `banthu` when the winning unit is a chan and the source is not deal;
otherwise `thuong`.

## Honours (cuoc) and diem

The base win is worth three diem. Each honour that applies adds its diem and its
token to the Cuoc field, listed in the order below. If no honour applies the
Cuoc field is the single token `xuong` and Diem stays three.

- `thienu` (6) — role dealer and source deal.
- `diau` (6) — role nondealer and source deal.
- `thong` (3) — streak thong. Not charged when thienu or diau applies.
- `chi` (3) — source gate. Not charged when thienu or diau applies.
- `banthu` (4) — the winning unit is a chan and the source is not deal.
- `tom` (4) — the twenty cards include 3v, 3s and 7n.
- `leo` (5) — the twenty cards include 9v, 8s and ci.
- `bachdinh` (8) — no red card at all.
- `tamdo` (8) — exactly eight red cards.
- `kinhtuchi` (8) — all four ci.
- `thienkhai` (5 each) — each non-ci kind that appears four times; the token is
  repeated once per such kind and each adds five.

## Fines (phat)

Fines are charged against the losing seats from the discard log. The referee
walks the losers in seat order A, B, C, D (skipping the winner) and, for each
loser, charges in this order:

- `treo-tranh` (2) — once for each toss by that seat whose card is a kind the
  winner holds as a chan.
- `tra-cua` (3) — only when the source is draw, once for each toss by that seat
  whose card equals the winning card.
- `lot-song` (1) — for each kind that seat tossed at least twice, one charge per
  repeat beyond the first, kinds taken in card order.

Each fine is a line `Phat = <type>:<seat>:<points>`, in the order charged. When
nothing is charged the single line is `Phat = none`.

## Settlement

Let D be the total Diem and P the sum of all fine points. The winner's net is
`3*D + P`. Each losing seat's net is `-D` minus the fine points charged against
that seat. The four Settle lines print seats A, B, C, D in that order.
