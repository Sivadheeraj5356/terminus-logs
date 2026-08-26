#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "network.hpp"
#include "policy.hpp"
#include "systems.hpp"
#include "tableau.hpp"

namespace {

const char *DEFAULT_TABLE_PATH = "/app/bench/stage_weights.tsv";

std::string table_path() {
    const char *override_path = std::getenv("HALVARD_STAGE_TABLE");
    if (override_path != nullptr && override_path[0] != '\0') return std::string(override_path);
    return std::string(DEFAULT_TABLE_PATH);
}

void usage() {
    std::printf("halvard kinetics bench\n");
    std::printf("  bench list\n");
    std::printf("  bench run --system NAME [--rtol R] [--atol A] [--t1 T] [--trace]\n");
    std::printf("run accepts only a compiled-in calibration system name; it has no network file reader\n");
}

}  // namespace

int main(int argc, char **argv) {
    if (argc < 2) {
        usage();
        return 2;
    }

    const std::string cmd = argv[1];

    if (cmd == "list") {
        std::vector<std::string> names = calibration_names();
        for (std::size_t i = 0; i < names.size(); ++i) {
            Network net;
            calibration_network(names[i], net);
            std::printf("%s\tspecies=%d\treactions=%d\thorizon=%.17g\trtol=%.17g\tatol=%.17g\n",
                        names[i].c_str(), (int)net.species.size(), (int)net.reactions.size(),
                        net.t1, net.rtol, net.atol);
        }
        return 0;
    }

    if (cmd != "run") {
        usage();
        return 2;
    }

    std::string system_name;
    double rtol = -1.0, atol = -1.0, t1 = -1.0;
    bool trace = false;

    for (int i = 2; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--trace") {
            trace = true;
        } else if (arg == "--system" && i + 1 < argc) {
            system_name = argv[++i];
        } else if (arg == "--rtol" && i + 1 < argc) {
            rtol = std::strtod(argv[++i], nullptr);
        } else if (arg == "--atol" && i + 1 < argc) {
            atol = std::strtod(argv[++i], nullptr);
        } else if (arg == "--t1" && i + 1 < argc) {
            t1 = std::strtod(argv[++i], nullptr);
        } else {
            std::fprintf(stderr, "unrecognised argument: %s\n", arg.c_str());
            return 2;
        }
    }

    Network net;
    if (system_name.empty() || !calibration_network(system_name, net)) {
        std::fprintf(stderr, "no such calibration system: %s\n", system_name.c_str());
        std::fprintf(stderr, "the bench integrates only its compiled-in calibration systems\n");
        return 2;
    }

    if (rtol > 0.0) net.rtol = rtol;
    if (atol > 0.0) net.atol = atol;
    if (t1 > 0.0) net.t1 = t1;

    Tableau tab;
    std::string err;
    if (!load_tableau(table_path(), tab, err)) {
        std::fprintf(stderr, "%s\n", err.c_str());
        return 3;
    }

    RunResult res = integrate(net, tab, trace);

    if (trace) {
        for (std::size_t i = 0; i < res.trace.size(); ++i) {
            const StepRecord &s = res.trace[i];
            std::printf("step\t%ld\t%.17g\t%.17g\t%d\n", s.index, s.t, s.h, s.accepted);
        }
    }

    std::printf("system\t%s\n", net.name.c_str());
    std::printf("verdict\t%s\n", res.verdict.c_str());
    std::printf("stop_time\t%.17g\n", res.stop_time);
    std::printf("accepted\t%ld\n", res.accepted);
    std::printf("rejected\t%ld\n", res.rejected);
    std::printf("derivative_evals\t%ld\n", res.derivative_evals);
    for (std::size_t i = 0; i < net.species.size(); ++i) {
        std::printf("final\t%s\t%.17g\n", net.species[i].c_str(), res.final_state[i]);
    }
    return 0;
}
