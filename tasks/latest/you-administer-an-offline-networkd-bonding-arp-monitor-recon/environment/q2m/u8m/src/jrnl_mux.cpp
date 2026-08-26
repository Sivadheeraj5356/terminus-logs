#include "vx_types.hpp"

#include <fstream>
#include <sstream>
#include <string>

std::string HashMaterial(const std::string& notes, const std::string& triple, int seed) {
    return md5_hex16(triple + "|" + notes + "|" + std::to_string(seed));
}

bool ReadField(const std::string& path, const std::string& key, std::string& out) {
    std::ifstream in(path);
    if (!in) return false;
    std::string line;
    std::string prefix = key + "=";
    while (std::getline(in, line)) {
        if (line.rfind(prefix, 0) == 0) {
            out = line.substr(prefix.size());
            while (!out.empty() && (out.back() == ' ' || out.back() == '\r')) out.pop_back();
            return true;
        }
    }
    return false;
}

int FnS5(const std::string& path, const std::string& fp, const std::string& mode, uint64_t epoch,
         const std::string& digest) {
    if (mode == "commit") {
        std::ofstream out(path, std::ios::app);
        out << "epoch=" << epoch << "\ncompile_fp=" << fp << "\nmembership_digest=" << digest
            << "\nreplay_ack=0\n";
        return 0;
    }
    if (mode == "ready") {
        std::string current;
        if (!ReadField(path, "compile_fp", current)) return 1;
        return current.empty() ? 1 : 0;
    }
    if (mode == "ack") {
        std::ifstream probe(path);
        if (!probe) return 1;
        std::ofstream out(path, std::ios::app);
        out << "replay_ack=1\n";
        return 0;
    }
    return 1;
}

uint32_t FnMerge(uint64_t line_epoch, uint64_t state_epoch, const std::string& line_digest,
                 const std::string& state_digest, uint32_t pending_after_decay, uint32_t fixture_max,
                 uint32_t persisted_pending) {
    (void)line_digest;
    (void)state_digest;
    (void)fixture_max;
    if (line_epoch == state_epoch) {
        return pending_after_decay;
    }
    return persisted_pending;
}
