#include "n5.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    EmitX emit;
    emit.root = "/app/environment/r01";
    emit.seed = 314159;
    emit.out = "/app/output/moderation_ledger.json";

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--data-root" && i + 1 < argc) {
            emit.root = argv[++i];
        } else if (arg == "--seed" && i + 1 < argc) {
            emit.seed = std::atoi(argv[++i]);
        } else if (arg == "--out" && i + 1 < argc) {
            emit.out = argv[++i];
        } else {
            std::cerr << "unknown or incomplete argument: " << arg << "\n";
            return 2;
        }
    }

    ReportX report = p91_cast({}, emit);
    z3_drop(emit.out, report.json);
    return 0;
}
