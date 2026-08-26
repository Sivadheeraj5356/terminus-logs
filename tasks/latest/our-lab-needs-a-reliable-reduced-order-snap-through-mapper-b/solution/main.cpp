#include "mini_json.hpp"
#include "model.hpp"
#include "solver.hpp"

#include <cerrno>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <unistd.h>

namespace fs = std::filesystem;

std::string read_file(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open input");
    std::ostringstream buffer;
    buffer << in.rdbuf();
    if (!in.good() && !in.eof()) throw std::runtime_error("cannot read input");
    return buffer.str();
}

bool is_same_or_below(const fs::path& candidate, const fs::path& base) {
    auto candidate_it = candidate.begin();
    auto base_it = base.begin();
    for (; base_it != base.end(); ++base_it, ++candidate_it) {
        if (candidate_it == candidate.end() || *candidate_it != *base_it) return false;
    }
    return true;
}

void validate_output_policy(const fs::path& output) {
    std::error_code ec;
    const fs::path resolved = fs::weakly_canonical(output, ec);
    if (ec) throw std::runtime_error("cannot resolve output path");

    const fs::path docs = fs::canonical("/app/docs", ec);
    if (ec) throw std::runtime_error("cannot resolve protected directory");
    const fs::path cases = fs::canonical("/app/cases", ec);
    if (ec) throw std::runtime_error("cannot resolve protected directory");

    if (is_same_or_below(resolved, docs) || is_same_or_below(resolved, cases)) {
        throw std::invalid_argument("output path is protected");
    }
}

void atomic_write(const fs::path& output, const std::string& content) {
    const fs::path parent = output.parent_path();
    if (parent.empty() || !fs::is_directory(parent)) throw std::runtime_error("output parent does not exist");
    const fs::path temp = parent / ("." + output.filename().string() + ".tmp." + std::to_string(static_cast<long long>(getpid())));
    try {
        {
            std::ofstream out(temp, std::ios::binary | std::ios::trunc);
            if (!out) throw std::runtime_error("cannot create temporary output");
            out.write(content.data(), static_cast<std::streamsize>(content.size()));
            out.flush();
            if (!out) throw std::runtime_error("cannot write temporary output");
        }
        fs::rename(temp, output);
    } catch (...) {
        std::error_code ec;
        fs::remove(temp, ec);
        throw;
    }
}

int main(int argc, char** argv) {
    fs::path input;
    fs::path output;
    bool seen_input = false;
    bool seen_output = false;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if ((arg == "--input" || arg == "--output") && i + 1 < argc) {
            if (arg == "--input") {
                if (seen_input) return 2;
                seen_input = true;
                input = argv[++i];
            } else {
                if (seen_output) return 2;
                seen_output = true;
                output = argv[++i];
            }
        } else {
            return 2;
        }
    }
    if (input.empty() || output.empty() || !input.is_absolute() || !output.is_absolute()) return 2;

    try {
        validate_output_policy(output);
        const mj::Value parsed = mj::parse(read_file(input));
        const Campaign campaign = parse_campaign(parsed);
        const mj::Value report = build_report(campaign);
        atomic_write(output, mj::dump(report));
        return 0;
    } catch (const std::invalid_argument&) {
        return 2;
    } catch (const std::runtime_error& e) {
        const std::string message = e.what();
        const bool campaign_error = message.find("cannot open input") == std::string::npos &&
                                    message.find("cannot read input") == std::string::npos &&
                                    message.find("output parent") == std::string::npos &&
                                    message.find("temporary output") == std::string::npos;
        if (campaign_error) return 2;
        std::cerr << message << '\n';
        return 3;
    } catch (...) {
        return 3;
    }
}
