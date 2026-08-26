#include "vx_api.hpp"

#include <cstdlib>
#include <cstring>
#include <string>
#include <unistd.h>
#include <vector>

namespace {

std::string env_root() {
    const char* r = std::getenv("VX_ENV_ROOT");
    return r ? r : "/app/environment";
}

void refresh_live_from_q2m(const std::string& root) {
    static const char* mods[] = {"p3k", "q7n", "t2w", "u8m", "v5r", "x1h", "w4z", "n9p", "g6k",
                                 "k7r", nullptr};
    for (const char** m = mods; *m; ++m) {
        std::string cmd = "mkdir -p \"" + root + "/" + *m + "/src\" && "
                          "if [ -d \"" + root + "/q2m/" + *m + "/src\" ]; then "
                          "cp -a \"" + root + "/q2m/" + *m + "/src/.\" \"" + root + "/" + *m +
                          "/src/\"; fi";
        std::system(cmd.c_str());
    }
}

void rebuild(const std::string& root) {
    // Touch refreshed mux sources so incremental builds cannot keep a stale .o.
    std::string touch =
        "cd \"" + root + "\" && for m in p3k q7n t2w u8m v5r x1h w4z n9p g6k k7r; do "
        "if [ -d \"$m/src\" ]; then touch \"$m/src\"/*; fi; done";
    std::system(touch.c_str());
    std::string cmd = "cd \"" + root + "\" && cmake -B build -DCMAKE_BUILD_TYPE=Release >/dev/null "
                      "&& cmake --build build >/dev/null";
    std::system(cmd.c_str());
}

}  // namespace

int main(int argc, char** argv) {
    PipelineInput in;
    in.env_root = env_root();
    std::string profile = "prep";
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--profile" && i + 1 < argc) {
            profile = argv[++i];
        } else if (a == "--out" && i + 1 < argc) {
            in.out_path = argv[++i];
        } else if (a == "--hook" && i + 1 < argc && std::string(argv[i + 1]) == "replay") {
            in.hook_replay = true;
            ++i;
        } else if (a == "--variant-seed" && i + 1 < argc) {
            in.seed = std::atoi(argv[++i]);
        }
    }
    if (profile == "verify" || profile == "seal") {
        in.profile = Profile::Seal;
        in.hook_replay = true;
    } else {
        // prep / compile
        in.profile = Profile::Prep;
    }

    if (!std::getenv("VX_REFRESHED")) {
        refresh_live_from_q2m(in.env_root);
        rebuild(in.env_root);
        setenv("VX_REFRESHED", "1", 1);
        std::string bin = in.env_root + "/build/vx_bond";
        std::vector<char*> args;
        args.push_back(const_cast<char*>(bin.c_str()));
        for (int i = 1; i < argc; ++i) args.push_back(argv[i]);
        args.push_back(nullptr);
        execv(bin.c_str(), args.data());
        // fall through if exec fails
    }

    return run_pipeline(in);
}
