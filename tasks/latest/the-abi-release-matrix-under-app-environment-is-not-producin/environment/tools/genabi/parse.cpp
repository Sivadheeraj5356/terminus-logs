#include "parse.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>

namespace {

std::string strip(const std::string &raw) {
    std::string s;
    for (char c : raw) {
        if (c != '\r') {
            s.push_back(c);
        }
    }
    std::size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) {
        return "";
    }
    std::size_t b = s.find_last_not_of(" \t");
    return s.substr(a, b - a + 1);
}

std::vector<std::string> split(const std::string &s, char sep) {
    std::vector<std::string> parts;
    std::string cur;
    std::istringstream ss(s);
    while (std::getline(ss, cur, sep)) {
        parts.push_back(cur);
    }
    return parts;
}

std::vector<std::string> read_order(const std::string &idl_dir) {
    std::vector<std::string> order;
    std::ifstream in(idl_dir + "/pack.order");
    std::string line;
    while (std::getline(in, line)) {
        std::string token = strip(line);
        if (token.empty() || token[0] == '#') {
            continue;
        }
        order.push_back(token);
    }
    return order;
}

bool kind_of(const std::string &token, Kind &out) {
    if (token == "uint32_t") {
        out = Kind::U32;
    } else if (token == "uint64_t") {
        out = Kind::U64;
    } else if (token == "ptr") {
        out = Kind::PTR;
    } else if (token == "cstr") {
        out = Kind::CSTR;
    } else {
        return false;
    }
    return true;
}

bool read_fragment(const std::string &path, LaneModel &model) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "genabi: cannot open fragment " << path << "\n";
        return false;
    }
    std::string line;
    while (std::getline(in, line)) {
        std::string body = strip(line);
        if (body.empty() || body[0] == '#') {
            continue;
        }
        std::istringstream fields(body);
        std::string name;
        std::string type_token;
        if (!(fields >> name >> type_token)) {
            std::cerr << "genabi: malformed fragment row: " << body << "\n";
            return false;
        }
        Kind kind;
        if (!kind_of(type_token, kind)) {
            std::cerr << "genabi: unknown ctype '" << type_token << "'\n";
            return false;
        }
        Slot slot;
        slot.name = name;
        slot.kind = kind;
        slot.size = width_of(kind);
        model.slots.push_back(slot);
    }
    return true;
}

}  // namespace

bool build_model(const std::string &idl_dir, const std::string &lane_file,
                 const std::string &label, LaneModel &model) {
    std::ifstream in(lane_file);
    if (!in) {
        std::cerr << "genabi: cannot open lane file " << lane_file << "\n";
        return false;
    }
    std::vector<std::string> selected;
    std::string name_field;
    std::string line;
    while (std::getline(in, line)) {
        std::string body = strip(line);
        if (body.empty() || body[0] == '#') {
            continue;
        }
        std::size_t eq = body.find('=');
        if (eq == std::string::npos) {
            std::cerr << "genabi: malformed lane row: " << body << "\n";
            return false;
        }
        std::string key = strip(body.substr(0, eq));
        std::string value = strip(body.substr(eq + 1));
        if (key == "name") {
            name_field = value;
        } else if (key == "fragments") {
            selected = split(value, ',');
        }
    }

    model.lane = label.empty() ? name_field : label;

    std::vector<std::string> order = read_order(idl_dir);
    for (const std::string &frag : order) {
        if (std::find(selected.begin(), selected.end(), frag) == selected.end()) {
            continue;
        }
        if (frag == "18_observability.sdk") {
            model.has_observability = true;
        } else if (frag == "20_diagnostics.sdk") {
            model.has_diagnostics = true;
        } else if (frag == "30_recovery.sdk") {
            model.has_recovery = true;
        }
        if (!read_fragment(idl_dir + "/fragments/" + frag, model)) {
            return false;
        }
    }

    for (std::size_t i = 0; i < model.slots.size(); ++i) {
        model.slots[i].index = static_cast<int>(i);
    }
    return true;
}
