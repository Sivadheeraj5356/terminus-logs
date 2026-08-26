#include "board.hpp"
#include "io.hpp"
#include "movegen.hpp"

#include <iostream>

int main() {
    std::string position_path = env_or_default("POSITION_PATH", "/app/data/position.txt");
    std::string output_path = env_or_default("OUTPUT_PATH", "/app/output.json");

    PositionFile pf = read_position_file(position_path);
    Position pos = parse_fen(pf.fen);
    long long nodes = perft(pos, pf.depth);
    write_output_json(output_path, nodes);

    std::cout << nodes << std::endl;
    return 0;
}
