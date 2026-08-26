#include "x.hpp"

#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

std::string z3_text(const std::string& s) {
    std::string out = "\"";
    for (char ch : s) {
        if (ch == '"' || ch == '\\') {
            out.push_back('\\');
            out.push_back(ch);
        } else if (ch == '\n') {
            out += "\\n";
        } else {
            out.push_back(ch);
        }
    }
    out.push_back('"');
    return out;
}

void z3_drop(const std::string& path, const std::string& body) {
    std::filesystem::path p(path);
    if (p.has_parent_path()) {
        std::filesystem::create_directories(p.parent_path());
    }
    std::ofstream out(path, std::ios::trunc);
    if (!out) {
        throw std::runtime_error("cannot write " + path);
    }
    out << body;
}
