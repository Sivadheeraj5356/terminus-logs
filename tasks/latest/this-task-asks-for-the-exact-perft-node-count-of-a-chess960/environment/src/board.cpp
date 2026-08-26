#include "board.hpp"

#include <cctype>
#include <sstream>
#include <vector>

int sq(int file_, int rank_) {
    return rank_ * 8 + file_;
}

int file_of(int s) {
    return s % 8;
}

int rank_of(int s) {
    return s / 8;
}

bool in_bounds(int f, int r) {
    return f >= 0 && f < 8 && r >= 0 && r < 8;
}

char side_of(char p) {
    if (p == 0) {
        return 0;
    }
    return std::isupper(static_cast<unsigned char>(p)) ? 'w' : 'b';
}

char opponent(char side) {
    return side == 'w' ? 'b' : 'w';
}

static std::vector<std::string> split_ws(const std::string &s) {
    std::vector<std::string> out;
    std::istringstream iss(s);
    std::string tok;
    while (iss >> tok) {
        out.push_back(tok);
    }
    return out;
}

Position parse_fen(const std::string &fen) {
    std::vector<std::string> parts = split_ws(fen);
    Position pos;
    pos.board.fill(0);
    const std::string &placement = parts[0];
    int rank_ = 7;
    int file_ = 0;
    for (char ch : placement) {
        if (ch == '/') {
            rank_ -= 1;
            file_ = 0;
        } else if (std::isdigit(static_cast<unsigned char>(ch))) {
            file_ += ch - '0';
        } else {
            pos.board[sq(file_, rank_)] = ch;
            file_ += 1;
        }
    }
    pos.side = parts[1][0];
    const std::string &castling = parts[2];
    if (castling != "-") {
        for (char ch : castling) {
            if (std::isupper(static_cast<unsigned char>(ch))) {
                pos.rook_files_w.insert(ch - 'A');
            } else {
                pos.rook_files_b.insert(ch - 'a');
            }
        }
    }
    const std::string &ep = parts[3];
    if (ep != "-") {
        int f = ep[0] - 'a';
        int r = ep[1] - '1';
        pos.ep_square = sq(f, r);
    } else {
        pos.ep_square = -1;
    }
    pos.halfmove = std::stoi(parts[4]);
    pos.fullmove = std::stoi(parts[5]);
    return pos;
}

int king_square(const Position &pos, char side) {
    char target = side == 'w' ? 'K' : 'k';
    for (int s = 0; s < 64; s++) {
        if (pos.board[s] == target) {
            return s;
        }
    }
    return -1;
}

const std::set<int> &rook_files_of(const Position &pos, char side) {
    return side == 'w' ? pos.rook_files_w : pos.rook_files_b;
}

void set_rook_files(Position &pos, char side, const std::set<int> &files) {
    if (side == 'w') {
        pos.rook_files_w = files;
    } else {
        pos.rook_files_b = files;
    }
}
