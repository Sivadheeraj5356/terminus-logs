#include "ph_iface.hpp"

#include <cstdint>
#include <string>

extern std::string HashMaterial(const std::string& notes, const std::string& triple, int seed);
extern int FnS5(const std::string& path, const std::string& fp, const std::string& mode, uint64_t epoch,
                const std::string& digest);
extern bool ReadField(const std::string& path, const std::string& key, std::string& out);

std::string compile_fingerprint(const std::string& notes, const std::string& triple, int seed) {
    return HashMaterial(notes, triple, seed);
}

bool journal_commit(const std::string& path, const std::string& fp, uint64_t epoch,
                    const std::string& digest) {
    return FnS5(path, fp, "commit", epoch, digest) == 0;
}

bool journal_ready(const std::string& path, const std::string& fp) {
    return FnS5(path, fp, "ready", 0, "") == 0;
}

bool journal_ack(const std::string& path, const std::string& fp) {
    return FnS5(path, fp, "ack", 0, "") == 0;
}

bool journal_acked(const std::string& path) {
    std::string v;
    return ReadField(path, "replay_ack", v) && v == "1";
}
