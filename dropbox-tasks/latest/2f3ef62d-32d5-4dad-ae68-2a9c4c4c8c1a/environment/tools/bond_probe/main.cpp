#include "vx_types.hpp"

#include <utility>

extern std::pair<std::string, bool> emit_lane_view(const std::string& report_json);

#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: bond_probe <report.json>\n";
        return 2;
    }
    std::ifstream in(argv[1]);
    if (!in) {
        std::cerr << "bond_probe: cannot open " << argv[1] << "\n";
        return 3;
    }
    std::ostringstream oss;
    oss << in.rdbuf();
    auto view = emit_lane_view(oss.str());
    std::cout << "label=" << view.first << " converged=" << (view.second ? 1 : 0) << "\n";
    return 0;
}
