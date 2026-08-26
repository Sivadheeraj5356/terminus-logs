#pragma once

#include <array>
#include <set>
#include <string>

struct Position {
    std::array<char, 64> board;
    char side;
    std::set<int> rook_files_w;
    std::set<int> rook_files_b;
    int ep_square;
    int halfmove;
    int fullmove;
};

int sq(int file_, int rank_);
int file_of(int s);
int rank_of(int s);
bool in_bounds(int f, int r);
Position parse_fen(const std::string &fen);
int king_square(const Position &pos, char side);
char side_of(char p);
char opponent(char side);
const std::set<int> &rook_files_of(const Position &pos, char side);
void set_rook_files(Position &pos, char side, const std::set<int> &files);
