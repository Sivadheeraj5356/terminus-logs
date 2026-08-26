#pragma once

#include "board.hpp"
#include <vector>

struct Move {
    int from;
    int to;
    char piece;
    char captured;
    char promo;
    bool is_ep;
    bool is_castle;
    char castle_side;
    bool is_double;
    int rook_from;
    int rook_to;
};

bool attacked_by(const Position &pos, int target_sq, char by_side);
std::vector<Move> gen_pseudo_moves(const Position &pos);
std::vector<Move> gen_castle_moves(const Position &pos, char side, int king_from);
Position make_move(const Position &pos, const Move &m);
std::vector<Move> gen_legal_moves(const Position &pos);
long long perft(const Position &pos, int depth);
