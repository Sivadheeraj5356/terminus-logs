#include <dirent.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "netfile.hpp"
#include "network.hpp"
#include "policy.hpp"
#include "tableau.hpp"

// Held-out grading reference: applies the certified Halvard protocol to any
// reaction network file. Lives only under tests/ and is never COPYd into the
// agent image.
int main(int argc, char **argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: kinref <assay_dir> <stage_table> <out_jsonl>\n");
        return 2;
    }
    const std::string dir = argv[1];
    const std::string table = argv[2];
    const std::string out_path = argv[3];

    Tableau tab;
    std::string err;
    if (!load_tableau(table, tab, err)) {
        std::fprintf(stderr, "%s\n", err.c_str());
        return 3;
    }

    std::vector<std::string> files;
    DIR *d = opendir(dir.c_str());
    if (d == nullptr) {
        std::fprintf(stderr, "cannot open assay directory: %s\n", dir.c_str());
        return 3;
    }
    struct dirent *ent;
    while ((ent = readdir(d)) != nullptr) {
        const std::string nm = ent->d_name;
        if (nm.size() > 4 && nm.compare(nm.size() - 4, 4, ".net") == 0) files.push_back(nm);
    }
    closedir(d);
    std::sort(files.begin(), files.end());

    FILE *out = std::fopen(out_path.c_str(), "w");
    if (out == nullptr) {
        std::fprintf(stderr, "cannot write: %s\n", out_path.c_str());
        return 3;
    }

    for (std::size_t i = 0; i < files.size(); ++i) {
        Network net;
        if (!load_network(dir + "/" + files[i], net, err)) {
            std::fprintf(stderr, "%s\n", err.c_str());
            std::fclose(out);
            return 3;
        }
        RunResult res = integrate(net, tab, false);
        std::fprintf(out, "{\"network\": \"%s\", \"verdict\": \"%s\", \"stop_time\": %.17g, "
                          "\"accepted\": %ld, \"rejected\": %ld, \"derivative_evals\": %ld, \"final\": {",
                     net.name.c_str(), res.verdict.c_str(), res.stop_time,
                     res.accepted, res.rejected, res.derivative_evals);
        for (std::size_t s = 0; s < net.species.size(); ++s) {
            if (s) std::fprintf(out, ", ");
            std::fprintf(out, "\"%s\": %.17g", net.species[s].c_str(), res.final_state[s]);
        }
        std::fprintf(out, "}}\n");
    }
    std::fclose(out);
    return 0;
}
