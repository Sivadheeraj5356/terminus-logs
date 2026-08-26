#ifndef TRANSPORT_GRID_H
#define TRANSPORT_GRID_H

/* The pinned periodic grid: x_i = i / N for i = 0 .. N-1, spacing dx = 1/N. */

double grid_dx(int N);

/* Fill x[0..N-1] with the grid coordinates x_i = i / N. */
void grid_points(double *x, int N);

#endif /* TRANSPORT_GRID_H */
