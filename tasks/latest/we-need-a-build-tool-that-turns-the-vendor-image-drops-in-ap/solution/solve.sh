#!/bin/bash
# Reference solution: implements the derive tool in C++, builds it via
# the provided CMake project, and runs the resulting binary once.
set -euo pipefail

cat > /app/src/derive.cpp << 'CPPEOF'
#include "derive.hpp"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <unistd.h>
#include <sys/wait.h>
#include <openssl/evp.h>

namespace fs = std::filesystem;

namespace {

// ---------------------------------------------------------------------
// Exact rational arithmetic (avoids float rounding error for tie detection)
// ---------------------------------------------------------------------
struct Fraction {
    long long num;
    long long den;

    static Fraction of(long long n, long long d) {
        if (d < 0) { n = -n; d = -d; }
        long long g = std::gcd(n < 0 ? -n : n, d);
        if (g == 0) g = 1;
        return Fraction{n / g, d / g};
    }

    bool greaterThan(long long other) const { return num > other * den; }
};

Fraction fmax(const Fraction& a, const Fraction& b) {
    // a >= b  <=>  a.num * b.den >= b.num * a.den  (dens are positive)
    return (a.num * b.den >= b.num * a.den) ? a : b;
}

Fraction fmin(const Fraction& a, const Fraction& b) {
    return (a.num * b.den <= b.num * a.den) ? a : b;
}

// floor-with-tie: floor(value * scale), except an exact .5 remainder rounds up
long long scaledRound(long long value, const Fraction& scale) {
    long long n = value * scale.num;
    long long d = scale.den;
    long long floorVal = n / d;
    if (n < 0 && n % d != 0) floorVal -= 1; // true floor for negative (not expected here)
    long long remainderNum = n - floorVal * d;
    // remainder == 1/2  <=>  remainderNum * 2 == d
    if (remainderNum * 2 == d) {
        return floorVal + 1;
    }
    return floorVal;
}

// ---------------------------------------------------------------------
// Subprocess execution without a shell (argv passed directly, no quoting
// hazards), capturing stdout.
// ---------------------------------------------------------------------
struct ProcResult {
    int exitCode;
    std::string stdoutData;
};

ProcResult runCapture(const std::vector<std::string>& argv) {
    int pipefd[2];
    if (pipe(pipefd) != 0) throw std::runtime_error("pipe failed");

    pid_t pid = fork();
    if (pid < 0) throw std::runtime_error("fork failed");

    if (pid == 0) {
        // child
        close(pipefd[0]);
        dup2(pipefd[1], STDOUT_FILENO);
        int devnull = open("/dev/null", O_WRONLY);
        if (devnull >= 0) dup2(devnull, STDERR_FILENO);
        close(pipefd[1]);

        std::vector<char*> cargv;
        for (auto& s : argv) cargv.push_back(const_cast<char*>(s.c_str()));
        cargv.push_back(nullptr);
        execvp(cargv[0], cargv.data());
        _exit(127);
    }

    // parent
    close(pipefd[1]);
    std::string output;
    char buf[4096];
    ssize_t n;
    while ((n = read(pipefd[0], buf, sizeof(buf))) > 0) {
        output.append(buf, n);
    }
    close(pipefd[0]);

    int status = 0;
    waitpid(pid, &status, 0);
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
    return ProcResult{code, output};
}

int runSilent(const std::vector<std::string>& argv) {
    return runCapture(argv).exitCode;
}

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

// ---------------------------------------------------------------------
// ImageMagick metadata reads
// ---------------------------------------------------------------------
std::pair<int, int> readDims(const std::string& path) {
    auto r = runCapture({"identify", "-format", "%w %h", path + "[0]"});
    std::istringstream iss(r.stdoutData);
    int w = 0, h = 0;
    iss >> w >> h;
    return {w, h};
}

const std::unordered_map<std::string, int>& orientationTable() {
    static const std::unordered_map<std::string, int> table = {
        {"Undefined", 0}, {"TopLeft", 1}, {"TopRight", 2}, {"BottomRight", 3},
        {"BottomLeft", 4}, {"LeftTop", 5}, {"RightTop", 6}, {"RightBottom", 7},
        {"LeftBottom", 8},
    };
    return table;
}

// returns 0 for "no orientation / normal", else 2-8
int readOrientation(const std::string& path) {
    auto r = runCapture({"identify", "-format", "%[orientation]", path + "[0]"});
    std::string name = trim(r.stdoutData);
    const auto& table = orientationTable();
    auto it = table.find(name);
    if (it == table.end()) return 0;
    return it->second == 1 ? 0 : it->second;
}

bool hasIccProfile(const std::string& path) {
    auto r = runCapture({"identify", "-format", "%[profile:icc]", path + "[0]"});
    return !trim(r.stdoutData).empty();
}

bool isSwapOrientation(int o) {
    return o == 5 || o == 6 || o == 7 || o == 8;
}

// ---------------------------------------------------------------------
// Naming template byte transform
// ---------------------------------------------------------------------
std::string stemTransform(const std::string& stem) {
    std::string out;
    out.reserve(stem.size());
    for (unsigned char b : stem) {
        if (b >= 'A' && b <= 'Z') {
            out.push_back(static_cast<char>(b - 'A' + 'a'));
        } else if ((b >= 'a' && b <= 'z') || (b >= '0' && b <= '9') || b == '_' || b == '-') {
            out.push_back(static_cast<char>(b));
        } else if (b >= 0x80) {
            out.push_back(static_cast<char>(b));
        } else {
            out.push_back('-');
        }
    }
    std::string collapsed;
    collapsed.reserve(out.size());
    bool prevDash = false;
    for (unsigned char b : out) {
        if (b == '-') {
            if (prevDash) continue;
            prevDash = true;
        } else {
            prevDash = false;
        }
        collapsed.push_back(static_cast<char>(b));
    }
    size_t start = 0;
    while (start < collapsed.size() && collapsed[start] == '-') start++;
    size_t end = collapsed.size();
    while (end > start && collapsed[end - 1] == '-') end--;
    return collapsed.substr(start, end - start);
}

std::string extFor(const std::string& filename) {
    auto pos = filename.find_last_of('.');
    std::string e = filename.substr(pos + 1);
    for (auto& c : e) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    if (e == "jpg" || e == "jpeg") return "jpg";
    if (e == "png") return "png";
    if (e == "tif" || e == "tiff") return "tiff";
    return e;
}

std::string stemOf(const std::string& filename) {
    auto pos = filename.find_last_of('.');
    return pos == std::string::npos ? filename : filename.substr(0, pos);
}

std::string baseName(const std::string& path) {
    auto pos = path.find_last_of('/');
    return pos == std::string::npos ? path : path.substr(pos + 1);
}

// ---------------------------------------------------------------------
// SHA-256 via OpenSSL EVP
// ---------------------------------------------------------------------
std::string sha256File(const std::string& path) {
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);

    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open for hashing: " + path);
    char buf[65536];
    while (f.read(buf, sizeof(buf)) || f.gcount() > 0) {
        EVP_DigestUpdate(ctx, buf, static_cast<size_t>(f.gcount()));
    }

    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digestLen = 0;
    EVP_DigestFinal_ex(ctx, digest, &digestLen);
    EVP_MD_CTX_free(ctx);

    static const char* hexChars = "0123456789abcdef";
    std::string hex;
    hex.reserve(digestLen * 2);
    for (unsigned int i = 0; i < digestLen; i++) {
        hex.push_back(hexChars[(digest[i] >> 4) & 0xF]);
        hex.push_back(hexChars[digest[i] & 0xF]);
    }
    return hex;
}

constexpr const char* kCanonicalIcc = "/app/assets/color_profiles/sRGB.icc";

struct Geometry {
    bool cover;
    int outW, outH;
    int scaledW, scaledH; // only meaningful for cover
    int left, top;        // only meaningful for cover
};

Geometry computeGeometry(const AssetClassRule& rule, int trueW, int trueH) {
    Geometry g{};
    if (rule.mode == "cover") {
        Fraction scale = fmax(Fraction::of(rule.width, trueW), Fraction::of(rule.height, trueH));
        int scaledW = static_cast<int>(scaledRound(trueW, scale));
        int scaledH = static_cast<int>(scaledRound(trueH, scale));
        g.cover = true;
        g.outW = rule.width;
        g.outH = rule.height;
        g.scaledW = scaledW;
        g.scaledH = scaledH;
        g.left = (scaledW - rule.width) / 2;
        g.top = (scaledH - rule.height) / 2;
    } else {
        Fraction scale = fmin(Fraction::of(rule.width, trueW), Fraction::of(rule.height, trueH));
        if (!rule.shrink_only) {
            // no clamp
        } else if (scale.num > scale.den) {
            scale = Fraction::of(1, 1);
        }
        g.cover = false;
        g.outW = static_cast<int>(scaledRound(trueW, scale));
        g.outH = static_cast<int>(scaledRound(trueH, scale));
    }
    return g;
}

} // namespace

DerivativeResult produce_derivative(
    const std::string& source_path,
    const AssetClassRule& rule,
    const std::string& out_dir
) {
    std::string filename = baseName(source_path);

    auto [storedW, storedH] = readDims(source_path);
    int orientation = readOrientation(source_path);
    bool hasIcc = hasIccProfile(source_path);

    bool swap = isSwapOrientation(orientation);
    int trueW = swap ? storedH : storedW;
    int trueH = swap ? storedW : storedH;

    Geometry geom = computeGeometry(rule, trueW, trueH);

    bool orientationNormalized = (orientation != 0);
    bool dimsMatch = (trueW == geom.outW) && (trueH == geom.outH);
    bool conformant = dimsMatch && !orientationNormalized && hasIcc;

    std::string stem = stemTransform(stemOf(filename));
    std::string ext = extFor(filename);
    std::string outFilename = rule.name + "__" + stem + "__" +
        std::to_string(geom.outW) + "x" + std::to_string(geom.outH) + "." + ext;

    fs::path derivDir = fs::path(out_dir) / "derivatives";
    fs::create_directories(derivDir);
    fs::path outPath = derivDir / outFilename;

    if (conformant) {
        fs::copy_file(source_path, outPath, fs::copy_options::overwrite_existing);
    } else {
        std::vector<std::string> cmd = {"convert", source_path, "-auto-orient", "-filter", "Lanczos"};
        if (geom.cover) {
            cmd.push_back("-resize");
            cmd.push_back(std::to_string(geom.scaledW) + "x" + std::to_string(geom.scaledH) + "!");
            cmd.push_back("-gravity");
            cmd.push_back("NorthWest");
            cmd.push_back("-extent");
            cmd.push_back(std::to_string(geom.outW) + "x" + std::to_string(geom.outH) +
                           "+" + std::to_string(geom.left) + "+" + std::to_string(geom.top));
        } else {
            cmd.push_back("-resize");
            cmd.push_back(std::to_string(geom.outW) + "x" + std::to_string(geom.outH) + "!");
        }
        if (!hasIcc) {
            cmd.push_back("-profile");
            cmd.push_back(kCanonicalIcc);
        }
        if (ext == "png") {
            cmd.push_back("-define");
            cmd.push_back("png:compression-level=9");
            cmd.push_back("-define");
            cmd.push_back("png:exclude-chunk=date,time");
        } else if (ext == "jpg") {
            cmd.push_back("-quality");
            cmd.push_back("85");
            cmd.push_back("-sampling-factor");
            cmd.push_back("4:2:0");
        } else if (ext == "tiff") {
            cmd.push_back("-compress");
            cmd.push_back("lzw");
        }
        cmd.push_back(outPath.string());

        int rc = runSilent(cmd);
        if (rc != 0) {
            throw std::runtime_error("convert failed for " + source_path);
        }
    }

    DerivativeResult result;
    result.source_file = filename;
    result.asset_class = rule.name;
    result.output_path = outPath.string();
    result.width = geom.outW;
    result.height = geom.outH;
    result.icc_policy = hasIcc ? "preserved" : "assumed_srgb";
    result.orientation_normalized = orientationNormalized;
    result.sha256 = sha256File(outPath.string());
    return result;
}
CPPEOF

cat > /app/src/manifest.cpp << 'CPPEOF'
#include "manifest.hpp"
#include <algorithm>
#include <fstream>
#include <stdexcept>

namespace {

std::string baseName(const std::string& path) {
    auto pos = path.find_last_of('/');
    return pos == std::string::npos ? path : path.substr(pos + 1);
}

// naming template is {asset_class}__{transformed_stem}__{WxH}.{ext}; the
// transformed stem is the middle "__"-delimited segment of the filename.
std::string sortStemOf(const std::string& outputFile) {
    auto first = outputFile.find("__");
    if (first == std::string::npos) return outputFile;
    auto second = outputFile.find("__", first + 2);
    if (second == std::string::npos) return outputFile.substr(first + 2);
    return outputFile.substr(first + 2, second - (first + 2));
}

std::string jsonEscape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out.push_back(static_cast<char>(c));
                }
        }
    }
    return out;
}

} // namespace

void write_manifest(
    const std::string& manifest_path,
    const std::vector<DerivativeResult>& derivatives
) {
    std::vector<DerivativeResult> sorted = derivatives;
    std::sort(sorted.begin(), sorted.end(), [](const DerivativeResult& a, const DerivativeResult& b) {
        if (a.asset_class != b.asset_class) return a.asset_class < b.asset_class;
        return sortStemOf(baseName(a.output_path)) < sortStemOf(baseName(b.output_path));
    });

    std::ofstream out(manifest_path);
    if (!out) throw std::runtime_error("cannot open manifest path: " + manifest_path);

    out << "{\n  \"derivatives\": [\n";
    for (size_t i = 0; i < sorted.size(); i++) {
        const auto& d = sorted[i];
        out << "    {\n";
        out << "      \"source_file\": \"" << jsonEscape(d.source_file) << "\",\n";
        out << "      \"asset_class\": \"" << jsonEscape(d.asset_class) << "\",\n";
        out << "      \"output_file\": \"" << jsonEscape(baseName(d.output_path)) << "\",\n";
        out << "      \"width\": " << d.width << ",\n";
        out << "      \"height\": " << d.height << ",\n";
        out << "      \"icc_policy\": \"" << jsonEscape(d.icc_policy) << "\",\n";
        out << "      \"orientation_normalized\": " << (d.orientation_normalized ? "true" : "false") << ",\n";
        out << "      \"sha256\": \"" << jsonEscape(d.sha256) << "\"\n";
        out << "    }" << (i + 1 < sorted.size() ? "," : "") << "\n";
    }
    out << "  ]\n}\n";
}
CPPEOF

cat > /app/src/spec_loader.cpp << 'CPPEOF'
#include "spec_loader.hpp"

// The spec document (Section 16) does not require the tool to literally
// parse the markdown file at runtime, only to implement the rules it
// defines. The five asset classes and their fixed constants are defined
// in Sections 4-8 of the spec.
std::vector<AssetClassRule> load_spec(const std::string& spec_path) {
    (void)spec_path;
    return {
        {"thumbnail", "cover", 320, 320, false},
        {"card",      "cover", 640, 400, false},
        {"avatar",    "cover", 200, 200, false},
        {"hero",      "fit",   1920, 1080, true},
        {"banner",    "fit",   1200, 300, false},
    };
}
CPPEOF

cat > /app/src/main.cpp << 'CPPEOF'
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "spec_loader.hpp"
#include "derive.hpp"
#include "manifest.hpp"

namespace fs = std::filesystem;

namespace {

struct Args {
    std::string sources, csv, spec, out;
};

bool parseArgs(int argc, char* argv[], Args& args) {
    std::unordered_map<std::string, std::string*> flags = {
        {"--sources", &args.sources},
        {"--csv", &args.csv},
        {"--spec", &args.spec},
        {"--out", &args.out},
    };
    for (int i = 1; i + 1 < argc; i += 2) {
        auto it = flags.find(argv[i]);
        if (it == flags.end()) return false;
        *(it->second) = argv[i + 1];
    }
    return !args.sources.empty() && !args.csv.empty() &&
           !args.spec.empty() && !args.out.empty();
}

struct CsvRow {
    std::string filename;
    std::string asset_class;
};

std::vector<CsvRow> readCsv(const std::string& path) {
    std::ifstream f(path);
    std::vector<CsvRow> rows;
    std::string line;
    bool first = true;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (first) { first = false; continue; } // skip header
        if (line.empty()) continue;
        auto comma = line.find(',');
        if (comma == std::string::npos) continue;
        rows.push_back({line.substr(0, comma), line.substr(comma + 1)});
    }
    return rows;
}

} // namespace

int main(int argc, char* argv[]) {
    Args args;
    if (!parseArgs(argc, argv, args)) {
        std::cerr << "Usage: derive --sources <dir> --csv <manifest_inputs.csv> "
                     "--spec <asset_processing_spec.md> --out <out_dir>\n";
        return 2;
    }

    if (!fs::is_directory(args.sources) || !fs::is_regular_file(args.csv) ||
        !fs::is_regular_file(args.spec)) {
        std::cerr << "required input path missing\n";
        return 2;
    }

    std::vector<AssetClassRule> rules = load_spec(args.spec);
    std::unordered_map<std::string, AssetClassRule> rulesByName;
    for (auto& r : rules) rulesByName[r.name] = r;

    std::vector<CsvRow> rows = readCsv(args.csv);

    std::vector<DerivativeResult> results;
    for (auto& row : rows) {
        auto ruleIt = rulesByName.find(row.asset_class);
        if (ruleIt == rulesByName.end()) {
            std::cerr << "unknown asset class: " << row.asset_class << "\n";
            return 2;
        }
        fs::path sourcePath = fs::path(args.sources) / row.filename;
        if (!fs::is_regular_file(sourcePath)) {
            std::cerr << "missing source file: " << row.filename << "\n";
            return 2;
        }
        try {
            results.push_back(produce_derivative(sourcePath.string(), ruleIt->second, args.out));
        } catch (const std::exception& e) {
            std::cerr << "failed processing " << row.filename << ": " << e.what() << "\n";
            return 1;
        }
    }

    write_manifest((fs::path(args.out) / "manifest.json").string(), results);
    return 0;
}
CPPEOF

cat > /app/CMakeLists.txt << 'CMEOF'
cmake_minimum_required(VERSION 3.16)
project(derive CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenSSL REQUIRED)

add_executable(derive
    src/main.cpp
    src/spec_loader.cpp
    src/derive.cpp
    src/manifest.cpp
)

target_include_directories(derive PRIVATE src)
target_link_libraries(derive PRIVATE OpenSSL::Crypto)
target_compile_options(derive PRIVATE -Wall -Wextra)
CMEOF

cmake -B /app/build -S /app -DCMAKE_BUILD_TYPE=Release
cmake --build /app/build -j"$(nproc)"

mkdir -p /app/out
/app/build/derive --sources /app/assets/src \
    --csv /app/assets/src/manifest_inputs.csv \
    --spec /app/spec/asset_processing_spec.md \
    --out /app/out
