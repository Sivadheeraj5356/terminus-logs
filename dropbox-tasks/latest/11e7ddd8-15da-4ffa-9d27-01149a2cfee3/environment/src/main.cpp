#include "continuation.hpp"

#include <cstdio>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    if (argc != 3) {
        std::fprintf(stderr, "usage: %s contract.txt output.txt\n", argv[0]);
        return 2;
    }
    std::FILE *fc = std::fopen(argv[1], "r");
    if (!fc) {
        std::fprintf(stderr, "cannot open contract file %s\n", argv[1]);
        return 3;
    }
    char problem[32];
    int k = 0, m = 0;
    if (std::fscanf(fc, "%31s %d %d", problem, &k, &m) != 3 || m <= 0) {
        std::fprintf(stderr, "expected: problem k m s1 .. sm\n");
        std::fclose(fc);
        return 3;
    }
    std::vector<double> arclengths(static_cast<size_t>(m));
    for (int j = 0; j < m; j++) {
        if (std::fscanf(fc, "%lf", &arclengths[static_cast<size_t>(j)]) != 1) {
            std::fprintf(stderr, "expected %d arclengths\n", m);
            std::fclose(fc);
            return 3;
        }
    }
    std::fclose(fc);

    std::vector<CurvePoint> pts = trace_branch(std::string(problem), k, arclengths);

    std::FILE *fo = std::fopen(argv[2], "w");
    if (!fo) {
        std::fprintf(stderr, "cannot open output file %s\n", argv[2]);
        return 3;
    }
    for (size_t j = 0; j < pts.size(); j++) {
        std::fprintf(fo, "%zu %.17g", j + 1, pts[j].lambda);
        for (size_t i = 0; i < pts[j].u.size(); i++) {
            std::fprintf(fo, " %.17g", pts[j].u[i]);
        }
        std::fprintf(fo, "\n");
    }
    std::fclose(fo);
    return 0;
}
