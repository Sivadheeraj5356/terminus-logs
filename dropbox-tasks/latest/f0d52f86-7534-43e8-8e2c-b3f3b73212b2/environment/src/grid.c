#include "grid.h"

double grid_dx(int N) {
    return 1.0 / (double)N;
}

void grid_points(double *x, int N) {
    double dx = grid_dx(N);
    for (int i = 0; i < N; i++) {
        x[i] = (double)i * dx;
    }
}
