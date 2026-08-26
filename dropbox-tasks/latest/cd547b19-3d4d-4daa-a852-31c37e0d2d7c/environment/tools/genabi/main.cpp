#include <cstring>
#include <iostream>
#include <string>

#include "common.hpp"
#include "digest.hpp"
#include "layout.hpp"
#include "parse.hpp"
#include "render.hpp"

namespace {

const char *next_arg(int &i, int argc, char **argv) {
    if (i + 1 >= argc) {
        return nullptr;
    }
    return argv[++i];
}

}  // namespace

int main(int argc, char **argv) {
    std::string idl_dir;
    std::string lane_file;
    std::string label;
    std::string out_header;
    std::string out_layout;

    for (int i = 1; i < argc; ++i) {
        const char *flag = argv[i];
        if (std::strcmp(flag, "--idl-dir") == 0) {
            const char *v = next_arg(i, argc, argv);
            if (v) idl_dir = v;
        } else if (std::strcmp(flag, "--lane-file") == 0) {
            const char *v = next_arg(i, argc, argv);
            if (v) lane_file = v;
        } else if (std::strcmp(flag, "--label") == 0) {
            const char *v = next_arg(i, argc, argv);
            if (v) label = v;
        } else if (std::strcmp(flag, "--out-header") == 0) {
            const char *v = next_arg(i, argc, argv);
            if (v) out_header = v;
        } else if (std::strcmp(flag, "--out-layout") == 0) {
            const char *v = next_arg(i, argc, argv);
            if (v) out_layout = v;
        } else {
            std::cerr << "genabi: unknown argument " << flag << "\n";
            return 2;
        }
    }

    if (idl_dir.empty() || lane_file.empty() || out_header.empty() || out_layout.empty()) {
        std::cerr << "usage: genabi --idl-dir DIR --lane-file FILE --label NAME "
                     "--out-header PATH --out-layout PATH\n";
        return 2;
    }

    LaneModel model;
    if (!build_model(idl_dir, lane_file, label, model)) {
        return 1;
    }
    compute_layout(model);
    model.digest = idl_digest(idl_dir, model.lane);

    if (!render_header(out_header, model)) {
        return 1;
    }
    if (!render_layout(out_layout, model)) {
        return 1;
    }
    return 0;
}
