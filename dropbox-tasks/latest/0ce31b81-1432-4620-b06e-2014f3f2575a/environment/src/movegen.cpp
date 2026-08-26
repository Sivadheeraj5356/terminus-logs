#include "movegen.hpp"

bool attacked_by(const Position &pos, int target_sq, char by_side) {
    (void)pos;
    (void)target_sq;
    (void)by_side;
    return false;
}

std::vector<Move> gen_pseudo_moves(const Position &pos) {
    (void)pos;
    return {};
}

std::vector<Move> gen_castle_moves(const Position &pos, char side, int king_from) {
    return {};
}

Position make_move(const Position &pos, const Move &m) {
    (void)m;
    return pos;
}

std::vector<Move> gen_legal_moves(const Position &pos) {
    (void)pos;
    return {};
}

long long perft(const Position &pos, int depth) {
    (void)pos;
    (void)depth;
    return 0;
}
