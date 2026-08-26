#!/bin/bash
set -euo pipefail
cd /app

cat > /app/src/movegen.cpp <<'CPPEOF'
#include "movegen.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <map>
#include <tuple>

static const int KNIGHT_DELTAS[8][2] = {
    {1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
static const int KING_DELTAS[8][2] = {
    {1, 0}, {1, 1}, {0, 1}, {-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, -1}};
static const int BISHOP_DIRS[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
static const int ROOK_DIRS[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};

static Move make_basic(int frm, int to, char piece, char captured, char promo, bool is_ep) {
    Move m;
    m.from = frm;
    m.to = to;
    m.piece = piece;
    m.captured = captured;
    m.promo = promo;
    m.is_ep = is_ep;
    m.is_castle = false;
    m.castle_side = 0;
    m.is_double = false;
    m.rook_from = -1;
    m.rook_to = -1;
    return m;
}

bool attacked_by(const Position &pos, int target_sq, char by_side) {
    int tf = file_of(target_sq);
    int tr = rank_of(target_sq);
    int pawn_rank_dir = by_side == 'w' ? 1 : -1;
    for (int df : {-1, 1}) {
        int f = tf + df;
        int r = tr - pawn_rank_dir;
        if (in_bounds(f, r)) {
            char p = pos.board[sq(f, r)];
            if (p != 0 && side_of(p) == by_side && std::toupper(p) == 'P') {
                return true;
            }
        }
    }
    for (auto &d : KNIGHT_DELTAS) {
        int f = tf + d[0];
        int r = tr + d[1];
        if (in_bounds(f, r)) {
            char p = pos.board[sq(f, r)];
            if (p != 0 && side_of(p) == by_side && std::toupper(p) == 'N') {
                return true;
            }
        }
    }
    for (auto &d : KING_DELTAS) {
        int f = tf + d[0];
        int r = tr + d[1];
        if (in_bounds(f, r)) {
            char p = pos.board[sq(f, r)];
            if (p != 0 && side_of(p) == by_side && std::toupper(p) == 'K') {
                return true;
            }
        }
    }
    for (auto &d : BISHOP_DIRS) {
        int f = tf + d[0];
        int r = tr + d[1];
        while (in_bounds(f, r)) {
            char p = pos.board[sq(f, r)];
            if (p != 0) {
                if (side_of(p) == by_side && (std::toupper(p) == 'B' || std::toupper(p) == 'Q')) {
                    return true;
                }
                break;
            }
            f += d[0];
            r += d[1];
        }
    }
    for (auto &d : ROOK_DIRS) {
        int f = tf + d[0];
        int r = tr + d[1];
        while (in_bounds(f, r)) {
            char p = pos.board[sq(f, r)];
            if (p != 0) {
                if (side_of(p) == by_side && (std::toupper(p) == 'R' || std::toupper(p) == 'Q')) {
                    return true;
                }
                break;
            }
            f += d[0];
            r += d[1];
        }
    }
    return false;
}

static std::vector<int> closed_range(int a, int b) {
    int fa = file_of(a);
    int fb = file_of(b);
    int rank_ = rank_of(a);
    int lo = std::min(fa, fb);
    int hi = std::max(fa, fb);
    std::vector<int> out;
    for (int f = lo; f <= hi; f++) {
        out.push_back(sq(f, rank_));
    }
    return out;
}

std::vector<Move> gen_castle_moves(const Position &pos, char side, int king_from) {
    std::vector<Move> out;
    int rank_ = side == 'w' ? 0 : 7;
    const std::set<int> &files = rook_files_of(pos, side);
    for (int rook_file : files) {
        int rook_from = sq(rook_file, rank_);
        int king_file = file_of(king_from);
        bool is_kingside = rook_file > king_file;
        int king_to_file = is_kingside ? 6 : 2;
        int rook_to_file = is_kingside ? 5 : 3;
        int king_to = sq(king_to_file, rank_);
        int rook_to = sq(rook_to_file, rank_);

        char rook_piece = side == 'w' ? 'R' : 'r';
        if (pos.board[rook_from] != rook_piece) {
            continue;
        }

        std::vector<int> king_span = closed_range(king_from, king_to);
        std::vector<int> rook_span = closed_range(rook_from, rook_to);
        std::set<int> must_be_empty(king_span.begin(), king_span.end());
        must_be_empty.insert(rook_span.begin(), rook_span.end());
        must_be_empty.erase(king_from);
        must_be_empty.erase(rook_from);

        bool blocked = false;
        for (int s : must_be_empty) {
            if (pos.board[s] != 0) {
                blocked = true;
                break;
            }
        }
        if (blocked) {
            continue;
        }

        char opp = opponent(side);
        if (attacked_by(pos, king_from, opp)) {
            continue;
        }
        std::vector<int> transit = closed_range(king_from, king_to);
        bool attacked = false;
        for (int s : transit) {
            if (attacked_by(pos, s, opp)) {
                attacked = true;
                break;
            }
        }
        if (attacked) {
            continue;
        }

        Move m = make_basic(king_from, king_to, side == 'w' ? 'K' : 'k', 0, 0, false);
        m.is_castle = true;
        m.castle_side = is_kingside ? 'K' : 'Q';
        m.rook_from = rook_from;
        m.rook_to = rook_to;
        out.push_back(m);
    }
    return out;
}

std::vector<Move> gen_pseudo_moves(const Position &pos) {
    std::vector<Move> moves;
    char side = pos.side;
    char opp = opponent(side);
    for (int s = 0; s < 64; s++) {
        char p = pos.board[s];
        if (p == 0 || side_of(p) != side) {
            continue;
        }
        char kind = std::toupper(p);
        int f = file_of(s);
        int r = rank_of(s);
        if (kind == 'P') {
            int direction = side == 'w' ? 1 : -1;
            int start_rank = side == 'w' ? 1 : 6;
            int promo_rank = side == 'w' ? 7 : 0;
            if (in_bounds(f, r + direction)) {
                int one = sq(f, r + direction);
                if (pos.board[one] == 0) {
                    if (rank_of(one) == promo_rank) {
                        for (char promo : {'Q', 'R', 'B', 'N'}) {
                            moves.push_back(make_basic(s, one, p, 0, promo, false));
                        }
                    } else {
                        moves.push_back(make_basic(s, one, p, 0, 0, false));
                    }
                    if (r == start_rank) {
                        int two = sq(f, r + 2 * direction);
                        if (pos.board[two] == 0) {
                            Move m = make_basic(s, two, p, 0, 0, false);
                            m.is_double = true;
                            moves.push_back(m);
                        }
                    }
                }
            }
            for (int df : {-1, 1}) {
                int nf = f + df;
                int nr = r + direction;
                if (!in_bounds(nf, nr)) {
                    continue;
                }
                int ts = sq(nf, nr);
                char tp = pos.board[ts];
                if (tp != 0 && side_of(tp) == opp) {
                    if (rank_of(ts) == promo_rank) {
                        for (char promo : {'Q', 'R', 'B', 'N'}) {
                            moves.push_back(make_basic(s, ts, p, tp, promo, false));
                        }
                    } else {
                        moves.push_back(make_basic(s, ts, p, tp, 0, false));
                    }
                } else if (pos.ep_square >= 0 && ts == pos.ep_square) {
                    moves.push_back(make_basic(s, ts, p, 0, 0, true));
                }
            }
        } else if (kind == 'N') {
            for (auto &d : KNIGHT_DELTAS) {
                int nf = f + d[0];
                int nr = r + d[1];
                if (!in_bounds(nf, nr)) {
                    continue;
                }
                int ts = sq(nf, nr);
                char tp = pos.board[ts];
                if (tp == 0 || side_of(tp) == opp) {
                    moves.push_back(make_basic(s, ts, p, tp, 0, false));
                }
            }
        } else if (kind == 'K') {
            for (auto &d : KING_DELTAS) {
                int nf = f + d[0];
                int nr = r + d[1];
                if (!in_bounds(nf, nr)) {
                    continue;
                }
                int ts = sq(nf, nr);
                char tp = pos.board[ts];
                if (tp == 0 || side_of(tp) == opp) {
                    moves.push_back(make_basic(s, ts, p, tp, 0, false));
                }
            }
            std::vector<Move> castles = gen_castle_moves(pos, side, s);
            moves.insert(moves.end(), castles.begin(), castles.end());
        } else {
            bool is_bishop = kind == 'B';
            bool is_rook = kind == 'R';
            std::vector<std::array<int, 2>> dirs;
            if (is_bishop) {
                for (auto &d : BISHOP_DIRS) dirs.push_back({d[0], d[1]});
            } else if (is_rook) {
                for (auto &d : ROOK_DIRS) dirs.push_back({d[0], d[1]});
            } else {
                for (auto &d : BISHOP_DIRS) dirs.push_back({d[0], d[1]});
                for (auto &d : ROOK_DIRS) dirs.push_back({d[0], d[1]});
            }
            for (auto &d : dirs) {
                int nf = f + d[0];
                int nr = r + d[1];
                while (in_bounds(nf, nr)) {
                    int ts = sq(nf, nr);
                    char tp = pos.board[ts];
                    if (tp == 0) {
                        moves.push_back(make_basic(s, ts, p, 0, 0, false));
                    } else {
                        if (side_of(tp) == opp) {
                            moves.push_back(make_basic(s, ts, p, tp, 0, false));
                        }
                        break;
                    }
                    nf += d[0];
                    nr += d[1];
                }
            }
        }
    }
    return moves;
}

Position make_move(const Position &pos, const Move &m) {
    Position np = pos;
    char side = pos.side;
    char opp = opponent(side);
    np.ep_square = -1;

    if (m.is_castle) {
        char moving_rook = np.board[m.rook_from];
        np.board[m.from] = 0;
        np.board[m.rook_from] = 0;
        np.board[m.to] = m.piece;
        np.board[m.rook_to] = moving_rook != 0 ? moving_rook : (side == 'w' ? 'R' : 'r');
        set_rook_files(np, side, {});
    } else if (m.is_ep) {
        np.board[m.to] = m.piece;
        np.board[m.from] = 0;
        int cap_sq = sq(file_of(m.to), rank_of(m.from));
        np.board[cap_sq] = 0;
    } else {
        char piece = m.piece;
        if (m.promo != 0) {
            piece = side == 'w' ? m.promo : static_cast<char>(std::tolower(m.promo));
        }
        np.board[m.to] = piece;
        np.board[m.from] = 0;
        if (m.is_double) {
            np.ep_square = sq(file_of(m.from), (rank_of(m.from) + rank_of(m.to)) / 2);
        }
    }

    if (!m.is_castle) {
        if (std::toupper(m.piece) == 'K') {
            set_rook_files(np, side, {});
        }
        if (std::toupper(m.piece) == 'R') {
            const std::set<int> &files = rook_files_of(pos, side);
            int mover_rank = side == 'w' ? 0 : 7;
            if (rank_of(m.from) == mover_rank && files.count(file_of(m.from))) {
                std::set<int> updated = rook_files_of(np, side);
                updated.erase(file_of(m.from));
                set_rook_files(np, side, updated);
            }
        }
        if (m.captured != 0 && !m.is_ep) {
            const std::set<int> &opp_files = rook_files_of(pos, opp);
            int opp_rank = opp == 'w' ? 0 : 7;
            if (rank_of(m.to) == opp_rank && opp_files.count(file_of(m.to))) {
                std::set<int> updated = rook_files_of(np, opp);
                updated.erase(file_of(m.to));
                set_rook_files(np, opp, updated);
            }
        }
    }

    np.side = opp;
    return np;
}

std::vector<Move> gen_legal_moves(const Position &pos) {
    char side = pos.side;
    char opp = opponent(side);
    std::vector<Move> legal;
    for (const Move &m : gen_pseudo_moves(pos)) {
        Position np = make_move(pos, m);
        int ks = king_square(np, side);
        if (ks < 0) {
            continue;
        }
        if (attacked_by(np, ks, opp)) {
            continue;
        }
        legal.push_back(m);
    }
    return legal;
}

// A position, side to move, en-passant square, and remaining depth fully
// determine the perft count from there; unlike a fresh board every ply, a
// long-sliding king/rook endgame revisits the same (position, depth) pair
// through many different move orders, so a transposition cache turns a
// search that would otherwise re-expand billions of duplicate subtrees into
// one that only ever computes each distinct state once.
using PerftKey = std::tuple<std::array<char, 64>, char, int, int, int, int>;

static PerftKey make_perft_key(const Position &pos, int depth) {
    int rw = 0;
    for (int f : rook_files_of(pos, 'w')) {
        rw |= (1 << f);
    }
    int rb = 0;
    for (int f : rook_files_of(pos, 'b')) {
        rb |= (1 << f);
    }
    return std::make_tuple(pos.board, pos.side, pos.ep_square, rw, rb, depth);
}

static long long perft_inner(const Position &pos, int depth, std::map<PerftKey, long long> &memo) {
    if (depth == 0) {
        return 1;
    }
    PerftKey key = make_perft_key(pos, depth);
    auto it = memo.find(key);
    if (it != memo.end()) {
        return it->second;
    }
    long long total = 0;
    for (const Move &m : gen_legal_moves(pos)) {
        Position np = make_move(pos, m);
        total += perft_inner(np, depth - 1, memo);
    }
    memo[key] = total;
    return total;
}

long long perft(const Position &pos, int depth) {
    std::map<PerftKey, long long> memo;
    return perft_inner(pos, depth, memo);
}
CPPEOF

if ! grep -q "must_be_empty.erase(rook_from)" /app/src/movegen.cpp; then
  echo "patch did not apply to movegen.cpp" >&2
  exit 1
fi
if ! grep -q "opp_files.count(file_of(m.to))" /app/src/movegen.cpp; then
  echo "patch did not apply to movegen.cpp" >&2
  exit 1
fi

make

if [ ! -x /app/build/chess960_perft ]; then
  echo "build failed" >&2
  exit 1
fi

/app/build/chess960_perft
cat /app/output.json
