import os

WHITE = "w"
BLACK = "b"

KNIGHT_DELTAS = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_DELTAS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def sq(file_, rank_):
    return rank_ * 8 + file_


def file_of(s):
    return s % 8


def rank_of(s):
    return s // 8


def in_bounds(f, r):
    return 0 <= f < 8 and 0 <= r < 8


class Position:
    __slots__ = ("board", "side", "rook_files", "ep_square", "halfmove", "fullmove")

    def __init__(self, board, side, rook_files, ep_square, halfmove, fullmove):
        self.board = board
        self.side = side
        self.rook_files = rook_files
        self.ep_square = ep_square
        self.halfmove = halfmove
        self.fullmove = fullmove

    def copy(self):
        return Position(
            list(self.board),
            self.side,
            {WHITE: set(self.rook_files[WHITE]), BLACK: set(self.rook_files[BLACK])},
            self.ep_square,
            self.halfmove,
            self.fullmove,
        )


def parse_fen(fen):
    parts = fen.strip().split()
    placement, side, castling, ep, halfmove, fullmove = parts
    board = [None] * 64
    rank_ = 7
    file_ = 0
    for ch in placement:
        if ch == "/":
            rank_ -= 1
            file_ = 0
        elif ch.isdigit():
            file_ += int(ch)
        else:
            board[sq(file_, rank_)] = ch
            file_ += 1
    rook_files = {WHITE: set(), BLACK: set()}
    if castling != "-":
        for ch in castling:
            if ch.isupper():
                rook_files[WHITE].add(ord(ch) - ord("A"))
            else:
                rook_files[BLACK].add(ord(ch) - ord("a"))
    ep_square = None
    if ep != "-":
        f = ord(ep[0]) - ord("a")
        r = int(ep[1]) - 1
        ep_square = sq(f, r)
    return Position(board, side, rook_files, ep_square, int(halfmove), int(fullmove))


def king_square(pos, side):
    target = "K" if side == WHITE else "k"
    for s in range(64):
        if pos.board[s] == target:
            return s
    return None


def side_of(p):
    if p is None:
        return None
    return WHITE if p.isupper() else BLACK


def opponent(side):
    return BLACK if side == WHITE else WHITE


def attacked_by(pos, target_sq, by_side):
    tf, tr = file_of(target_sq), rank_of(target_sq)
    pawn_rank_dir = 1 if by_side == WHITE else -1
    for df in (-1, 1):
        f = tf + df
        r = tr - pawn_rank_dir
        if in_bounds(f, r):
            p = pos.board[sq(f, r)]
            if p is not None and side_of(p) == by_side and p.upper() == "P":
                return True
    for df, dr in KNIGHT_DELTAS:
        f, r = tf + df, tr + dr
        if in_bounds(f, r):
            p = pos.board[sq(f, r)]
            if p is not None and side_of(p) == by_side and p.upper() == "N":
                return True
    for df, dr in KING_DELTAS:
        f, r = tf + df, tr + dr
        if in_bounds(f, r):
            p = pos.board[sq(f, r)]
            if p is not None and side_of(p) == by_side and p.upper() == "K":
                return True
    for df, dr in BISHOP_DIRS:
        f, r = tf + df, tr + dr
        while in_bounds(f, r):
            p = pos.board[sq(f, r)]
            if p is not None:
                if side_of(p) == by_side and p.upper() in ("B", "Q"):
                    return True
                break
            f += df
            r += dr
    for df, dr in ROOK_DIRS:
        f, r = tf + df, tr + dr
        while in_bounds(f, r):
            p = pos.board[sq(f, r)]
            if p is not None:
                if side_of(p) == by_side and p.upper() in ("R", "Q"):
                    return True
                break
            f += df
            r += dr
    return False


def gen_pseudo_moves(pos, buggy=False):
    moves = []
    side = pos.side
    opp = opponent(side)
    for s in range(64):
        p = pos.board[s]
        if p is None or side_of(p) != side:
            continue
        kind = p.upper()
        f, r = file_of(s), rank_of(s)
        if kind == "P":
            direction = 1 if side == WHITE else -1
            start_rank = 1 if side == WHITE else 6
            promo_rank = 7 if side == WHITE else 0
            one = sq(f, r + direction) if in_bounds(f, r + direction) else None
            if one is not None and pos.board[one] is None:
                if rank_of(one) == promo_rank:
                    for promo in ("Q", "R", "B", "N"):
                        moves.append(_mk(s, one, p, None, promo, False, False, None))
                else:
                    moves.append(_mk(s, one, p, None, None, False, False, None))
                if r == start_rank:
                    two = sq(f, r + 2 * direction)
                    if pos.board[two] is None:
                        moves.append(
                            _mk(s, two, p, None, None, False, False, None, double=True)
                        )
            for df in (-1, 1):
                nf = f + df
                nr = r + direction
                if not in_bounds(nf, nr):
                    continue
                ts = sq(nf, nr)
                tp = pos.board[ts]
                if tp is not None and side_of(tp) == opp:
                    if rank_of(ts) == promo_rank:
                        for promo in ("Q", "R", "B", "N"):
                            moves.append(_mk(s, ts, p, tp, promo, False, False, None))
                    else:
                        moves.append(_mk(s, ts, p, tp, None, False, False, None))
                elif pos.ep_square is not None and ts == pos.ep_square:
                    moves.append(_mk(s, ts, p, "ep", None, True, False, None))
        elif kind == "N":
            for df, dr in KNIGHT_DELTAS:
                nf, nr = f + df, r + dr
                if not in_bounds(nf, nr):
                    continue
                ts = sq(nf, nr)
                tp = pos.board[ts]
                if tp is None or side_of(tp) == opp:
                    moves.append(_mk(s, ts, p, tp, None, False, False, None))
        elif kind == "K":
            for df, dr in KING_DELTAS:
                nf, nr = f + df, r + dr
                if not in_bounds(nf, nr):
                    continue
                ts = sq(nf, nr)
                tp = pos.board[ts]
                if tp is None or side_of(tp) == opp:
                    moves.append(_mk(s, ts, p, tp, None, False, False, None))
            moves.extend(gen_castle_moves(pos, side, s, buggy=buggy))
        else:
            dirs = (
                BISHOP_DIRS
                if kind == "B"
                else ROOK_DIRS
                if kind == "R"
                else BISHOP_DIRS + ROOK_DIRS
            )
            for df, dr in dirs:
                nf, nr = f + df, r + dr
                while in_bounds(nf, nr):
                    ts = sq(nf, nr)
                    tp = pos.board[ts]
                    if tp is None:
                        moves.append(_mk(s, ts, p, None, None, False, False, None))
                    else:
                        if side_of(tp) == opp:
                            moves.append(_mk(s, ts, p, tp, None, False, False, None))
                        break
                    nf += df
                    nr += dr
    return moves


def _mk(frm, to, piece, captured, promo, is_ep, is_castle, castle_side, double=False):
    return {
        "from": frm,
        "to": to,
        "piece": piece,
        "captured": captured,
        "promo": promo,
        "is_ep": is_ep,
        "is_castle": is_castle,
        "castle_side": castle_side,
        "double": double,
    }


def gen_castle_moves(pos, side, king_from, buggy=False):
    out = []
    rank_ = 0 if side == WHITE else 7
    for rook_file in sorted(pos.rook_files[side]):
        rook_from = sq(rook_file, rank_)
        king_file = file_of(king_from)
        is_kingside = rook_file > king_file
        king_to_file = 6 if is_kingside else 2
        rook_to_file = 5 if is_kingside else 3
        king_to = sq(king_to_file, rank_)
        rook_to = sq(rook_to_file, rank_)

        rook_piece = "R" if side == WHITE else "r"
        if not buggy:
            if pos.board[rook_from] != rook_piece:
                continue

        king_span = _closed_range(king_from, king_to)
        rook_span = _closed_range(rook_from, rook_to)
        if buggy:
            must_be_empty = set(king_span) - {king_from}
        else:
            must_be_empty = (set(king_span) | set(rook_span)) - {king_from, rook_from}

        blocked = False
        for s in must_be_empty:
            if pos.board[s] is not None:
                blocked = True
                break
        if blocked:
            continue

        opp = opponent(side)
        if attacked_by(pos, king_from, opp):
            continue
        transit = _closed_range(king_from, king_to)
        attacked = False
        for s in transit:
            if attacked_by(pos, s, opp):
                attacked = True
                break
        if attacked:
            continue

        out.append(
            _mk(
                king_from,
                king_to,
                "K" if side == WHITE else "k",
                None,
                None,
                False,
                True,
                "K" if is_kingside else "Q",
            )
        )
        out[-1]["rook_from"] = rook_from
        out[-1]["rook_to"] = rook_to
    return out


def _closed_range(a, b):
    fa, fb = file_of(a), file_of(b)
    rank_ = rank_of(a)
    lo, hi = min(fa, fb), max(fa, fb)
    return [sq(f, rank_) for f in range(lo, hi + 1)]


def make_move(pos, move, buggy=False):
    new = pos.copy()
    board = new.board
    side = pos.side
    opp = opponent(side)

    new.ep_square = None

    if move["is_castle"]:
        king_from = move["from"]
        king_to = move["to"]
        rook_from = move["rook_from"]
        rook_to = move["rook_to"]
        moving_rook_piece = board[rook_from]
        board[king_from] = None
        board[rook_from] = None
        board[king_to] = move["piece"]
        board[rook_to] = (
            moving_rook_piece
            if moving_rook_piece is not None
            else ("R" if side == WHITE else "r")
        )
        new.rook_files[side] = set()
    elif move["is_ep"]:
        board[move["to"]] = move["piece"]
        board[move["from"]] = None
        cap_sq = sq(file_of(move["to"]), rank_of(move["from"]))
        board[cap_sq] = None
    else:
        frm, to = move["from"], move["to"]
        piece = move["piece"]
        if move["promo"] is not None:
            piece = move["promo"] if side == WHITE else move["promo"].lower()
        board[to] = piece
        board[frm] = None
        if move["double"]:
            new.ep_square = sq(file_of(frm), (rank_of(frm) + rank_of(to)) // 2)

    if not move["is_castle"]:
        if move["piece"].upper() == "K":
            new.rook_files[side] = set()
        if move["piece"].upper() == "R" and move["from"] in _rank_files_set(pos, side):
            new.rook_files[side].discard(file_of(move["from"]))
        if not buggy and move["captured"] is not None and move["captured"] != "ep":
            cap_side = opp
            if move["to"] in _rank_files_set(pos, cap_side):
                new.rook_files[cap_side].discard(file_of(move["to"]))

    new.side = opp
    return new


def _rank_files_set(pos, side):
    rank_ = 0 if side == WHITE else 7
    return {sq(f, rank_) for f in pos.rook_files[side]}


def gen_legal_moves(pos, buggy=False):
    side = pos.side
    opp = opponent(side)
    legal = []
    for m in gen_pseudo_moves(pos, buggy=buggy):
        new = make_move(pos, m, buggy=buggy)
        ks = king_square(new, side)
        if ks is None:
            continue
        if attacked_by(new, ks, opp):
            continue
        legal.append(m)
    return legal


def _perft_key(pos, depth):
    return (
        tuple(pos.board),
        pos.side,
        pos.ep_square,
        frozenset(pos.rook_files[WHITE]),
        frozenset(pos.rook_files[BLACK]),
        depth,
    )


def perft(pos, depth, buggy=False, memo=None):
    if depth == 0:
        return 1
    if memo is None:
        memo = {}
    # A long-sliding king/rook endgame revisits the same (position, side,
    # en-passant square, castling rights, depth) state through many
    # different move orders; a position/depth alone fully determines the
    # remaining count, so caching it collapses that duplicate re-expansion.
    key = _perft_key(pos, depth)
    if key in memo:
        return memo[key]
    total = 0
    for m in gen_legal_moves(pos, buggy=buggy):
        new = make_move(pos, m, buggy=buggy)
        total += perft(new, depth - 1, buggy=buggy, memo=memo)
    memo[key] = total
    return total


def perft_from_fen(fen, depth, buggy=False):
    return perft(parse_fen(fen), depth, buggy=buggy, memo={})


HIDDEN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "hidden"
)


def read_position_file(path):
    with open(path) as handle:
        lines = [line.strip() for line in handle.readlines() if line.strip() != ""]
    fen = lines[0]
    depth = int(lines[1])
    return fen, depth


def hidden_manifest():
    with open(os.path.join(HIDDEN_DIR, "manifest.txt")) as handle:
        return [line.strip() for line in handle.readlines() if line.strip() != ""]


def hidden_case_names():
    return [name[:-4] for name in hidden_manifest() if name.endswith(".txt")]


def hidden_case_path(name):
    return os.path.join(HIDDEN_DIR, name + ".txt")
