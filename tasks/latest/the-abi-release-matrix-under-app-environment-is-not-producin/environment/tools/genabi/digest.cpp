#include "digest.hpp"

#include <cstdio>
#include <fstream>
#include <sstream>
#include <vector>

namespace {

constexpr std::uint64_t kPrime = 1099511628211ULL;

std::string read_file(const std::string &path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

std::vector<std::string> pack_order(const std::string &idl_dir) {
    std::vector<std::string> order;
    std::ifstream in(idl_dir + "/pack.order");
    std::string line;
    while (std::getline(in, line)) {
        std::string trimmed;
        for (char c : line) {
            if (c != '\r') {
                trimmed.push_back(c);
            }
        }
        std::size_t start = trimmed.find_first_not_of(" \t");
        if (start == std::string::npos) {
            continue;
        }
        std::size_t end = trimmed.find_last_not_of(" \t");
        std::string token = trimmed.substr(start, end - start + 1);
        if (token.empty() || token[0] == '#') {
            continue;
        }
        order.push_back(token);
    }
    return order;
}

}  // namespace

void Mixer::mix_u64(const std::string &text) {
    mix_u64(reinterpret_cast<const unsigned char *>(text.data()), text.size());
}

void Mixer::mix_u64(const unsigned char *data, std::size_t len) {
    for (std::size_t i = 0; i < len; ++i) {
        state_ ^= data[i];
        state_ *= kPrime;
    }
}

std::string Mixer::hex() const {
    char buf[17];
    std::snprintf(buf, sizeof(buf), "%016llx", static_cast<unsigned long long>(state_));
    return std::string(buf);
}

std::string idl_digest(const std::string &idl_dir, const std::string &label) {
    Mixer mixer;
    for (const std::string &frag : pack_order(idl_dir)) {
        std::string body = read_file(idl_dir + "/fragments/" + frag);
        mixer.mix_u64(frag);
        mixer.mix_u64(reinterpret_cast<const unsigned char *>(body.data()), body.size());
    }
    mixer.mix_u64(std::string("lane:") + label);
    return mixer.hex();
}
