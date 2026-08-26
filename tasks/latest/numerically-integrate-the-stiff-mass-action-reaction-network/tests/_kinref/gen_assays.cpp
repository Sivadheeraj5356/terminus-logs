#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

// Held-out workload synthesiser. The verifier runs this at grade time from a
// private seed; the networks it emits exist nowhere in the agent image.
namespace {

struct Rng {
    std::uint64_t s;
    explicit Rng(std::uint64_t seed) : s(seed) {}
    std::uint64_t next() {
        s += 0x9E3779B97F4A7C15ULL;
        std::uint64_t z = s;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
    double unit() { return (double)(next() >> 11) / 9007199254740992.0; }
    int range(int lo, int hi) { return lo + (int)(next() % (std::uint64_t)(hi - lo + 1)); }
    double loguniform(double a, double b) { return std::pow(10.0, a + (b - a) * unit()); }
};

const char *SPECIES[6] = {"A", "B", "C", "D", "E", "F"};

}  // namespace

int main(int argc, char **argv) {
    if (argc < 5) {
        std::fprintf(stderr, "usage: genassays <seed> <count> <out_dir> <prefix>\n");
        return 2;
    }
    const std::uint64_t seed = std::strtoull(argv[1], nullptr, 10);
    const int count = std::atoi(argv[2]);
    const std::string dir = argv[3];
    const std::string prefix = argv[4];

    Rng rng(seed);

    for (int n = 0; n < count; ++n) {
        const int ns = rng.range(3, 6);
        const int nr = rng.range(3, 6);
        // Every third network is driven into the stiff regime.
        const bool stiff = (n % 3 == 0);

        char suffix[32];
        std::snprintf(suffix, sizeof(suffix), "_%02d", n);
        const std::string name = prefix + suffix;
        const std::string path = dir + "/" + name + ".net";
        FILE *f = std::fopen(path.c_str(), "w");
        if (f == nullptr) return 3;

        std::fprintf(f, "network\t%s\n", name.c_str());
        std::fprintf(f, "species");
        for (int i = 0; i < ns; ++i) std::fprintf(f, "\t%s", SPECIES[i]);
        std::fprintf(f, "\n");

        // Mass lives on the first species; a second species may seed a catalyst.
        std::vector<double> init(ns, 0.0);
        init[0] = 1.0;
        if (rng.unit() < 0.5) init[1] = 0.1 + 0.4 * rng.unit();
        for (int i = 0; i < ns; ++i) std::fprintf(f, "initial\t%s\t%.17g\n", SPECIES[i], init[i]);

        // Reactions conserve the total species count (1->1 and 2->2 only), so
        // the trajectory stays bounded and total concentration is invariant.
        for (int r = 0; r < nr; ++r) {
            const bool bimolecular = (rng.unit() < 0.55);
            double rate;
            if (stiff && r < 2) {
                rate = rng.loguniform(5.5, 7.8);
            } else {
                rate = rng.loguniform(-0.5, 3.0);
            }
            if (!bimolecular) {
                int a = rng.range(0, ns - 1);
                int b = rng.range(0, ns - 1);
                while (b == a) b = rng.range(0, ns - 1);
                std::fprintf(f, "reaction\t%.17g\t%s -> %s\n", rate, SPECIES[a], SPECIES[b]);
            } else {
                int a = rng.range(0, ns - 1);
                int b = rng.range(0, ns - 1);
                int c = rng.range(0, ns - 1);
                int d = rng.range(0, ns - 1);
                while (c == a && d == b) { c = rng.range(0, ns - 1); d = rng.range(0, ns - 1); }
                std::fprintf(f, "reaction\t%.17g\t%s + %s -> %s + %s\n", rate,
                             SPECIES[a], SPECIES[b], SPECIES[c], SPECIES[d]);
            }
        }

        const double t1 = 6.0 + 40.0 * rng.unit();
        std::fprintf(f, "horizon\t0\t%.17g\n", t1);
        const double rtol = rng.loguniform(-9.0, -7.0);
        std::fprintf(f, "rtol\t%.17g\n", rtol);
        std::fprintf(f, "atol\t%.17g\n", rtol * 1.0e-3);
        std::fclose(f);
    }
    return 0;
}
