#include "io.hpp"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;

std::string trim(const std::string& s) {
    size_t begin = 0;
    while (begin < s.size() && std::isspace(static_cast<unsigned char>(s[begin]))) begin++;
    size_t end = s.size();
    while (end > begin && std::isspace(static_cast<unsigned char>(s[end - 1]))) end--;
    return s.substr(begin, end - begin);
}

std::vector<std::string> split_ws(const std::string& s) {
    std::istringstream in(s);
    std::vector<std::string> out;
    std::string token;
    while (in >> token) out.push_back(token);
    return out;
}

std::vector<std::string> split_tab(const std::string& s) {
    std::vector<std::string> out;
    std::string current;
    std::istringstream in(s);
    while (std::getline(in, current, '\t')) out.push_back(current);
    return out;
}

Lines read_lines(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot open " + path);
    Lines lines;
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        lines.push_back(line);
    }
    return lines;
}

void write_text(const std::string& path, const std::string& text) {
    fs::path p(path);
    if (!p.parent_path().empty()) fs::create_directories(p.parent_path());
    std::ofstream out(path);
    if (!out) throw std::runtime_error("cannot write " + path);
    out << text;
}

bool path_exists(const std::string& path) {
    return fs::exists(path);
}

void ensure_dir(const std::string& path) {
    fs::create_directories(path);
}

static std::vector<std::map<std::string, std::string>> read_tsv(const std::string& path) {
    auto lines = read_lines(path);
    std::vector<std::string> header;
    std::vector<std::map<std::string, std::string>> rows;
    for (const auto& raw : lines) {
        std::string line = trim(raw);
        if (line.empty() || line[0] == '#') continue;
        if (header.empty()) {
            header = split_tab(line);
            continue;
        }
        auto cells = split_tab(line);
        std::map<std::string, std::string> row;
        for (size_t i = 0; i < header.size() && i < cells.size(); ++i) row[header[i]] = cells[i];
        rows.push_back(row);
    }
    return rows;
}

RuntimeConfig parse_run_config(const std::string& path) {
    RuntimeConfig cfg;
    std::map<std::string, std::string> kv;
    for (const auto& row : read_tsv(path)) kv[row.at("key")] = row.at("value");
    cfg.profile = kv.at("profile");
    cfg.epoch = kv.at("epoch");
    cfg.width = std::stoi(kv.at("width"));
    cfg.height = std::stoi(kv.at("height"));
    cfg.crval = {std::stod(kv.at("crval1")), std::stod(kv.at("crval2"))};
    cfg.cdelt = {std::stod(kv.at("cdelt1")), std::stod(kv.at("cdelt2"))};
    return cfg;
}

std::vector<OrderEntry> parse_order(const std::string& path) {
    std::vector<OrderEntry> out;
    for (const auto& row : read_tsv(path)) {
        out.push_back({std::stoi(row.at("order_index")), row.at("tile_id"), row.at("phase")});
    }
    std::sort(out.begin(), out.end(), [](const OrderEntry& a, const OrderEntry& b) {
        return a.index < b.index;
    });
    return out;
}

std::vector<CalibrationRow> parse_calibration(const std::string& path) {
    std::vector<CalibrationRow> out;
    for (const auto& row : read_tsv(path)) {
        out.push_back({row.at("tile_id"), row.at("profile"), row.at("epoch"), std::stod(row.at("weight"))});
    }
    return out;
}

std::vector<SamplePoint> parse_samples(const std::string& path) {
    std::vector<SamplePoint> out;
    for (const auto& row : read_tsv(path)) {
        out.push_back({row.at("sample_id"), std::stod(row.at("world_x")), std::stod(row.at("world_y"))});
    }
    return out;
}

std::vector<double> parse_thresholds(const std::string& path) {
    std::vector<double> out;
    for (const auto& row : read_tsv(path)) out.push_back(std::stod(row.at("threshold")));
    return out;
}

std::vector<JournalRecord> parse_journal(const std::string& path) {
    std::vector<JournalRecord> out;
    for (const auto& row : read_tsv(path)) {
        out.push_back({std::stoi(row.at("seq")), row.at("event"), row.at("tile_id"), row.at("generation"), row.at("artifact")});
    }
    std::sort(out.begin(), out.end(), [](const JournalRecord& a, const JournalRecord& b) {
        return a.seq < b.seq;
    });
    return out;
}

std::vector<std::string> read_manifest(const std::string& path) {
    std::vector<std::string> out;
    if (!path_exists(path)) return out;
    for (const auto& raw : read_lines(path)) {
        std::string line = trim(raw);
        if (!line.empty() && line[0] != '#') out.push_back(line);
    }
    return out;
}

static double optional_double(const std::map<std::string, std::string>& fields, const std::string& key, double fallback) {
    auto it = fields.find(key);
    return it == fields.end() ? fallback : std::stod(it->second);
}

Tile parse_tile(const std::string& path) {
    Tile tile;
    std::map<std::string, std::string> fields;
    bool in_pixels = false;
    for (const auto& raw : read_lines(path)) {
        std::string line = trim(raw);
        if (line.empty()) continue;
        if (line == "PIXELS") {
            in_pixels = true;
            continue;
        }
        if (line == "END_PIXELS") {
            in_pixels = false;
            continue;
        }
        if (in_pixels) {
            std::vector<double> row;
            for (const auto& value : split_ws(line)) row.push_back(std::stod(value));
            tile.pixels.push_back(row);
            continue;
        }
        auto pos = line.find('=');
        if (pos != std::string::npos) fields[line.substr(0, pos)] = line.substr(pos + 1);
    }
    tile.id = fields.at("TILE_ID");
    tile.mode = fields.at("WCS_MODE");
    tile.width = std::stoi(fields.at("WIDTH"));
    tile.height = std::stoi(fields.at("HEIGHT"));
    tile.primary_crval = {optional_double(fields, "CRVAL1", optional_double(fields, "LEGACY_PRIMARY_CRVAL1", 0.0)),
                          optional_double(fields, "CRVAL2", optional_double(fields, "LEGACY_PRIMARY_CRVAL2", 0.0))};
    tile.primary_cdelt = {optional_double(fields, "CDELT1", 0.1), optional_double(fields, "CDELT2", 0.1)};
    tile.alt_crval = {optional_double(fields, "ALT_CRVAL1", tile.primary_crval.x), optional_double(fields, "ALT_CRVAL2", tile.primary_crval.y)};
    tile.alt_cdelt = {optional_double(fields, "ALT_CDELT1", tile.primary_cdelt.x), optional_double(fields, "ALT_CDELT2", tile.primary_cdelt.y)};
    if (static_cast<int>(tile.pixels.size()) != tile.height) throw std::runtime_error("tile height mismatch " + tile.id);
    for (const auto& row : tile.pixels) {
        if (static_cast<int>(row.size()) != tile.width) throw std::runtime_error("tile width mismatch " + tile.id);
    }
    return tile;
}

std::map<std::string, Lines> parse_hdus(const Lines& lines) {
    if (lines.empty() || lines[0] != "FITS-LITE 2") throw std::runtime_error("missing FITS-LITE 2 header");
    std::map<std::string, Lines> hdus;
    std::string current;
    Lines chunk;
    for (size_t i = 1; i < lines.size(); ++i) {
        const std::string& line = lines[i];
        if (line.rfind("HDU ", 0) == 0) {
            if (!current.empty()) throw std::runtime_error("nested HDU");
            current = line.substr(4);
            chunk = {line};
        } else if (line == "END_HDU") {
            if (current.empty()) throw std::runtime_error("END_HDU without HDU");
            chunk.push_back(line);
            hdus[current] = chunk;
            current.clear();
            chunk.clear();
        } else {
            if (current.empty()) throw std::runtime_error("line outside HDU: " + line);
            chunk.push_back(line);
        }
    }
    if (!current.empty()) throw std::runtime_error("unterminated HDU");
    return hdus;
}

std::vector<std::vector<double>> parse_primary_image(const std::map<std::string, Lines>& hdus) {
    auto it = hdus.find("PRIMARY_IMAGE");
    if (it == hdus.end()) throw std::runtime_error("missing PRIMARY_IMAGE");
    bool data = false;
    std::vector<std::vector<double>> out;
    for (const auto& line : it->second) {
        if (line == "DATA") {
            data = true;
            continue;
        }
        if (line == "END_HDU") break;
        if (!data) continue;
        std::vector<double> row;
        for (const auto& value : split_ws(line)) row.push_back(std::stod(value));
        if (!row.empty()) out.push_back(row);
    }
    return out;
}

std::map<std::string, std::string> hdu_key_values(const Lines& hdu) {
    std::map<std::string, std::string> out;
    for (const auto& line : hdu) {
        if (line.rfind("HDU ", 0) == 0 || line == "END_HDU" || line == "DATA") continue;
        auto pos = line.find(' ');
        if (pos != std::string::npos) out[line.substr(0, pos)] = line.substr(pos + 1);
    }
    return out;
}

std::string fnv64_hex(const Lines& lines) {
    uint64_t value = 1469598103934665603ULL;
    std::ostringstream text;
    for (const auto& line : lines) text << line << '\n';
    std::string payload = text.str();
    for (unsigned char ch : payload) {
        value ^= static_cast<uint64_t>(ch);
        value *= 1099511628211ULL;
    }
    std::ostringstream out;
    out << std::hex << std::setfill('0') << std::setw(16) << value;
    return out.str();
}

std::string join_csv(const std::vector<std::string>& values) {
    std::ostringstream out;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i) out << ",";
        out << values[i];
    }
    return out.str();
}

std::string fixed6(double value) {
    std::ostringstream out;
    out << std::fixed << std::setprecision(6) << value;
    return out.str();
}
