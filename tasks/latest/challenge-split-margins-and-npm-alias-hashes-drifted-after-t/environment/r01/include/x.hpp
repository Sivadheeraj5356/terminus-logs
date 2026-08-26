#pragma once

#include <map>
#include <string>
#include <vector>

struct UnitX {
    std::string cid;
    std::string pid;
    std::string split;
    std::string lang;
    std::string text;
    std::string comp;
    std::string raw_pkg;
    std::string norm;
    bool take = false;
};

struct RuleX {
};

struct TableX {
    std::vector<std::string> bad;
    std::vector<std::string> good;
};

struct ItemX {
    std::string raw_pkg;
    std::string canon_pkg;
    std::string comp;
};

struct GraphX {
    std::vector<ItemX> items;
    std::map<std::string, std::string> sig;
};

struct NodeX {
    std::string canon_pkg;
    std::string comp;
    std::string sig;
    std::vector<std::string> aliases;
};

struct ScoreX {
    std::string cid;
    std::string pid;
    std::string split;
    std::string lang;
    std::string comp;
    std::string raw_pkg;
    int margin = 0;
    std::string label;
};

struct GroupX {
    std::string pid;
    std::string canon_pkg;
    std::string comp;
    std::string sig;
    int variant_count = 0;
    int mean_margin_milli = 0;
    int deficit_count = 0;
    std::vector<std::string> langs;
    std::vector<std::string> cases;
};

struct ReportX {
    std::string json;
};

struct EmitX {
    int seed = 0;
    std::string root;
    std::string out;
};

std::vector<UnitX> z1_pull(const std::string& root);
GraphX z2_pull(const std::string& root);
std::string z3_text(const std::string& s);
void z3_drop(const std::string& path, const std::string& body);
