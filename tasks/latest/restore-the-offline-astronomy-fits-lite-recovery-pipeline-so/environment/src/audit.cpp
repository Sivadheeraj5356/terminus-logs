#include "audit.hpp"

#include "io.hpp"
#include "render.hpp"

#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>

static std::map<std::string, std::string> checksum_map(const Lines& hdu) {
    std::map<std::string, std::string> out;
    for (const auto& line : hdu) {
        if (line.rfind("HDU ", 0) == 0 || line == "END_HDU") continue;
        auto parts = split_ws(line);
        if (parts.size() == 2) out[parts[0]] = parts[1];
    }
    return out;
}

int audit_fits(const std::string& path) {
    auto hdus = parse_hdus(read_lines(path));
    std::set<std::string> required = {"PRIMARY_IMAGE", "COVERAGE", "CHECKPOINT", "PROVENANCE", "CHECKSUMS"};
    for (const auto& name : required) {
        if (!hdus.count(name)) {
            std::cerr << "missing " << name << "\n";
            return 2;
        }
    }
    auto observed = checksum_map(hdus.at("CHECKSUMS"));
    bool ok = true;
    for (const auto& name : {"PRIMARY_IMAGE", "COVERAGE", "CHECKPOINT", "PROVENANCE"}) {
        std::string expected = fnv64_hex(hdus.at(name));
        if (!observed.count(name) || observed[name] != expected) {
            std::cerr << "checksum mismatch " << name << "\n";
            ok = false;
        }
    }
    if (!ok) return 3;
    std::cout << "FITS-LITE audit passed for " << path << "\n";
    return 0;
}

int render_from_fits(const std::string& fits_path, const std::string& svg_path) {
    auto image = parse_primary_image(parse_hdus(read_lines(fits_path)));
    write_text(svg_path, render_svg_text(image, {15.0, 28.0, 38.0}));
    std::cout << "wrote " << svg_path << "\n";
    return 0;
}

int sample_fits(const std::string& fits_path, const std::string& sx, const std::string& sy) {
    auto hdus = parse_hdus(read_lines(fits_path));
    auto image = parse_primary_image(hdus);
    auto kv = hdu_key_values(hdus.at("PRIMARY_IMAGE"));
    auto crval = split_ws(kv.at("GLOBAL_WCS_CRVAL"));
    auto cdelt = split_ws(kv.at("GLOBAL_WCS_CDELT"));
    double wx = std::stod(sx);
    double wy = std::stod(sy);
    int x = static_cast<int>(std::llround((wx - std::stod(crval[0])) / std::stod(cdelt[0])));
    int y = static_cast<int>(std::llround((wy - std::stod(crval[1])) / std::stod(cdelt[1])));
    if (y < 0 || y >= static_cast<int>(image.size()) || x < 0 || x >= static_cast<int>(image[y].size())) {
        std::cerr << "sample outside mosaic\n";
        return 4;
    }
    std::cout << fixed6(image[y][x]) << "\n";
    return 0;
}
