TIDEVAULT PUBLIC CONTRACT
=========================

The root-owned referee holds one live immutable Tidevault game. The participant
is Gold, Gold acts first, and Violet replies synchronously after each accepted
nonterminal Gold action. The public `/app/arena` client is the only supported
participant interface. It talks to the referee through a Unix socket, one
connection carries one request, accepted actions cannot be undone, and a
rejection changes neither native state nor transcript.

The public protocol is `arena-tidevault-v1` and the ruleset is `tidevault-v1`.
Every public state discloses the complete frozen opponent tuple: model ID,
model SHA-256, training-dataset SHA-256, node budget, search width, maximum
depth, seed, selection profile, root temperature in thousandths, root
rank-lapse in thousandths, and move-time ceiling in milliseconds. The protected
checkpoint and root configuration are independently attested by the verifier.
Maximum depth requests the full remaining horizon when set to eighteen; actual
iteration is also bounded by remaining plies and the disclosed node budget.

FROZEN OPPONENT
---------------

The release opponent is first-party checkpoint
`tidevault-linear-s20260720-e0004`, trained on the deterministic corpus attested
by dataset SHA-256
`68966f73c2edf89eca9a518eecca844c9c5d5ab308b584cf1c3a43a42db5d074`.
Its checkpoint SHA-256 is
`68920ae99a568aa74a85c1af3256c06b6590a95643792bcf00e11820dd519f0b`.
It searches at most 4,096 nodes per reply with width 24, full remaining depth
up to eighteen plies, deterministic seed 20260720, selection profile exactly
`beam-rank-lapse-v1`, root temperature exactly zero, root rank lapse exactly
zero, and a 5,000 ms reply ceiling. The live values shown by `status` are
authoritative and are independently checked against the protected
configuration and checkpoint bytes.

BOARD AND OPENING
-----------------

The board has three concentric rings in canonical order:

    I M O

Each ring has six sectors in clockwise canonical order:

    A B C D E F

A slot joins one ring and one sector. The eighteen canonical slot IDs are `IA`
through `IF`, `MA` through `MF`, and `OA` through `OF`, in that ring-major
order. Every slot is empty at the opening. There are no hidden coordinates,
adjacencies, blocked slots, or ring orientations beyond these names.

Gold and Violet each begin with this inventory of one-use pieces:

    P1 3
    P2 3
    P3 3

Both cumulative scores begin at zero, Gold has the turn, ply is zero, and no
tide or transcript record exists. Exactly one piece is placed on every native
ply. Native play therefore lasts exactly eighteen plies and fills the board.

ACTIONS AND CANONICAL ORDER
---------------------------

Every ordinary action has exactly four single-space-separated fields:

    POWER PLACEMENT_SLOT ROTATION_RING DIRECTION

`POWER` is `P1`, `P2`, or `P3`. `PLACEMENT_SLOT` is one canonical two-character
slot. `ROTATION_RING` is `I`, `M`, or `O`. `DIRECTION` is `CW` or `CCW`.
For example:

    P2 IA M CW

The example places a Gold or Violet power-two piece into IA and then rotates
ring M clockwise. The placement ring and rotation ring are independent; they
may be the same or different. Lowercase, extra punctuation, alternate slot
spellings, and omitted fields are malformed rather than aliases.

An action is legal exactly when all three conditions hold:

1. The game is ongoing and the actor has a piece of that power remaining.
2. The named placement slot is empty before rotation.
3. Every field is one exact canonical value above.

Rotation never makes an action illegal. It permutes the six slots of one ring,
so it cannot create a collision. Distinct actions remain distinct even when a
symmetric or empty rotated ring makes their resulting boards coincide. There
is no pass.

Legal actions are ordered first by power P1, P2, P3; then by placement ring I,
M, O; then by placement sector A through F; then by rotation ring I, M, O; and
finally by direction CW before CCW. `legal_actions` always uses this exact
canonical legal-action order.

PLACEMENT AND ROTATION
----------------------

Apply one legal action in this exact order:

1. Put the actor's named power piece into the empty pre-rotation placement
   slot.
2. Rotate every occupant of the selected rotation ring exactly one sector in
   the named direction.
3. Decrease the actor's matching inventory entry by one and increase ply by
   one.
4. If the new ply is nine or eighteen, resolve one tide checkpoint.
5. If ply is eighteen, adjudicate the final cumulative score. Otherwise change
   turn to the other color.

Clockwise rotation maps A to B, B to C, C to D, D to E, E to F, and F to A.
Counterclockwise rotation maps A to F, F to E, E to D, D to C, C to B, and B
to A. Pieces retain owner and power while rotating.

Every accepted placement record includes `placed_slot`, the pre-rotation slot,
and `settled_slot`, the new piece's post-rotation slot. If placement and
rotation rings differ, those slots are equal. If the rings match, the settled
sector is the adjacent sector in the selected direction.

TIDE SCORING
------------

Tides resolve after plies nine and eighteen, after that ply's rotation. These
are respectively the half-full and full board snapshots. At one tide, evaluate
sectors A through F in order. For each sector, sum the powers of Gold pieces
occupying that sector across rings I, M, and O, and separately sum Violet's
powers across the same three slots.

If Gold's weight is higher, Gold gains one cumulative point. If Violet's
weight is higher, Violet gains one cumulative point. Equal weights award no
point. A tide can therefore award from zero through six points total. Pieces
are not removed, changed, or marked by scoring, and a later tide scores the
then-current board again. Scores only increase and are the sum of all completed
tides.

Each tide object records its one-based tide number, ply, points newly awarded
to each color, and all six spoke comparisons. A spoke records its sector,
Gold weight, Violet weight, and `point_owner`, which is `gold`, `violet`, or
null for a tie. `tide_history` retains every completed tide in order. The
action record at a scoring ply contains that same tide object; other placement
records contain null.

At ply eighteen, the second tide resolves before adjudication. A higher
cumulative Gold score is a Gold win, a higher Violet score is a Violet win, and
equal scores are a draw. Native termination is `complete`. The native terminal
`turn` remains the color that placed the final piece.

RESIGNATION
-----------

Resignation is a terminal public overlay, not a native action. An accepted Gold
resignation reports `violet_win`, winner `violet`, and termination
`resignation`. It adds no piece or ply, rotates no ring, scores no tide, changes
no inventory or cumulative score, and does not change native turn, previous
native action, canonical native serialization, or native state hash. It adds
one transcript record whose action, placed slot, settled slot, and tide are
null and whose before and after hashes are identical. Public legal actions
become empty.

SYNCHRONOUS PUBLIC TURN
-----------------------

At every ongoing public command boundary Gold has the turn. One accepted
`move` first applies Gold's action. If that reaches ply eighteen, the terminal
response is returned without a Violet action. Otherwise the protected opponent
chooses and applies one legal Violet action, and the response contains either
that terminal state or the next Gold position. A normal public move therefore
appends two records and two plies.

Gold's action and the required Violet response are one atomic referee
transaction. If the protected opponent times out, fails, or returns an illegal
action, neither action, board, rotation, tide, score, inventory change, hash,
nor record from that request is committed. The unchanged state is returned
with `internal_error`.

COMMANDS
--------

The supported commands are:

    /app/arena status
    /app/arena move P2 IA M CW
    /app/arena transcript
    /app/arena resign
    /app/arena ping
    /app/arena --json status
    /app/arena --wire transcript
    /app/arena --json ping

The optional output selector is absent, `--json`, or `--wire`, and may occur
only as the first argument. `status`, `transcript`, `resign`, and `ping` take no
arguments. `move` takes exactly four action arguments. `status`, `transcript`,
and `ping` are observational while play is ongoing. There is no reset, undo,
rewind, load, seed, model, difficulty, or configuration command.

REQUEST FRAMING
---------------

The Unix request is one ASCII line terminated by LF, with one optional CR
immediately before LF. The 8,192-byte maximum includes the terminator. NUL,
non-ASCII input, an empty or incomplete line, more than one LF, embedded CR,
or an over-limit request is malformed. The provided client sends fields with
tabs; a raw request without tabs is split on ASCII whitespace. Tab-separated
fields must be nonempty and contain no leading or trailing whitespace.

One connection carries one request and one complete response. After writing
the request, the requester must close or half-close its write side so framing
can be validated before execution. `/app/arena` does this automatically.
Pipelining and concurrent mutations are unsupported. The public client writes
one complete response to standard output and returns zero for success, one for
a referee rejection, or two for a local usage or transport failure.

Issue one command at a time and wait for its full response before choosing the
next command. When any response reports a win, loss, draw, or resignation,
issue no later arena request and end your turn immediately.

HUMAN OUTPUT
------------

Successful human state output begins `TIDEVAULT HUMAN V1` and uses these
readable headings in order:

    PROTOCOL:
    RULESET:
    PLAYER:
    SETTINGS:
    STATE:
    SCORES:
    INVENTORY:
    BOARD:
    TIDES (COUNT):
    LATEST_RECORD:
    LEGAL_ACTIONS (COUNT):
    POSTGAME_PLAYER_REQUESTS:
    STATE_HASH:

Board cells are printed in canonical ring-major order. Tide output includes
every spoke weight and point owner. Latest record includes actor, color, action
or resignation, placement and settled slots, optional tide, and both hashes.
Legal actions are printed in canonical order. Human `transcript` adds
`TRANSCRIPT (COUNT):` and prints every record. A human rejection begins
`ERROR CODE: MESSAGE`, then prints the complete unchanged state. Human ping is
exactly:

    TIDEVAULT READY

JSON SUCCESS STATE
------------------

JSON is one compact ASCII object followed by LF. A successful `status`, `move`,
or `resign` has exactly these keys:

    ok
    protocol ruleset rings sectors player_color
    opponent_model_id opponent_model_sha256 opponent_dataset_sha256
    opponent_node_budget opponent_search_width opponent_max_depth
    opponent_seed opponent_selection_profile
    opponent_root_temperature_milli opponent_root_rank_lapse_permille
    opponent_move_time_limit_ms
    turn result winner termination ply_count previous_action
    gold_score violet_score gold_inventory violet_inventory
    board tide_history legal_actions postgame_player_requests
    state_hash latest_record

`ok` is true. `protocol` and `ruleset` are the frozen identifiers above.
`rings` is exactly `["I","M","O"]`, `sectors` is exactly
`["A","B","C","D","E","F"]`, and `player_color` is `gold`. The model
identifier is a lowercase letter-or-digit string that may also contain `.`,
`_`, or `-`, and selection profile is exactly `beam-rank-lapse-v1`; both
digest fields are lowercase 64-character SHA-256 strings. All budgets, width,
maximum depth, seed, and move ceiling are positive integers. Root temperature
is exactly zero and root rank-lapse is an integer from 0 through 1000.

`turn` is `gold` or `violet`. `result` is `ongoing`, `gold_win`,
`violet_win`, or `draw`. While ongoing, winner and termination are null. At a
native terminal, winner is `gold`, `violet`, or null for a draw and termination
is `complete`. Resignation uses the overlay fields specified above. Ply is an
integer from zero through eighteen. `previous_action` is null at the opening or
the latest native canonical placement; resignation does not replace it. Scores
are nonnegative integers.

Each inventory is an object with exactly `P1`, `P2`, and `P3`, each an integer
from zero through three. The board is an array of eighteen objects in canonical
slot order. Each board object has exactly:

    slot ring sector occupant power

`slot` is its canonical two-character ID, with matching one-character `ring`
and `sector`. An empty cell has null occupant and power. An occupied cell has
occupant `gold` or `violet` and integer power one, two, or three.

`tide_history` is an array of zero through two objects. Each has exactly:

    tide ply gold_points violet_points spokes

Tide is one or two and its ply is nine times that number. New point
counts are integers from zero through six. `spokes` contains six objects in
sector order, each with exactly:

    sector gold_weight violet_weight point_owner

Weights are nonnegative integers. Point owner is `gold`, `violet`, or null and
must agree with the weight comparison.

`legal_actions` is an array of canonical action strings in the order defined
above and is empty at every public terminal. `postgame_player_requests` is a
nonnegative integer counting connections begun by participant UID 65534 after
play ended. It is counted before framing, so malformed or unsupported
postgame traffic also counts. Root verifier requests do not count.
`state_hash` is a lowercase SHA-256 digest of the canonical native state and is
unchanged by resignation. `latest_record` is null at the opening or the final
transcript record.

The canonical native hash payload has exactly the sorted keys `board`,
`inventories`, `moves`, `ply`, `ruleset`, `scores`, `tides`, and `turn`.
Board entries are null or `{owner,power,stone_id}` objects in ring-major order;
inventories and scores are Gold then Violet; moves include canonical action,
owner, placed slot, settled slot, and sequential stone ID; tides contain the
objects defined above. The payload is compact sorted-key ASCII JSON with no
trailing newline. `state_hash` is the lowercase SHA-256 of those ASCII bytes.
Outcome fields are derived and excluded; the resignation overlay is likewise
excluded.

JSON TRANSCRIPT AND RECORDS
---------------------------

A successful JSON `transcript` has exactly the success-state keys plus
`actions`. `actions` is the complete record array and `latest_record` equals
its final entry, or both are empty/null at the opening. Every record has
exactly:

    record actor color action placed_slot settled_slot
    state_hash_before state_hash_after tide

`record` is one-based and sequential. Actor is `player` or `opponent`; color is
`gold` or `violet` and follows native turn order. An ordinary record contains
one canonical action and its canonical pre-rotation and post-rotation slots.
Both hashes are lowercase SHA-256 digests of the native states immediately
before and after that action. Tide is the matching tide object at plies nine
and eighteen, otherwise null. A resignation record has the null fields and
identical hashes described earlier.

JSON REJECTIONS AND PING
------------------------

A server rejection has exactly:

    ok error state

`ok` is false. `error` has exactly string fields `code` and `message`. `state`
is the complete unchanged success-state payload without `ok`. Public codes are
`bad_request`, `unknown_command`, `invalid_action`, `illegal_action`,
`wrong_turn`, `game_over`, `request_too_large`, and `internal_error`.

Successful JSON ping is exactly:

    {"ok":true,"ready":true}

WIRE OUTPUT
-----------

Wire output is bounded ASCII. State success is:

    TIDEVAULT_WIRE_V1
    OK
    JSON<TAB>COMPACT_JSON_OBJECT
    END

A rejection changes `OK` to `FAIL` and carries the exact rejection object.
Wire ping is exactly:

    TIDEVAULT_WIRE_V1
    READY<TAB>1
    END

The JSON payload occupies one line and is the same object emitted by `--json`.
