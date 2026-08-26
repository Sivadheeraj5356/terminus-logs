#ifndef TELEGRAPH_CSVOUT_H
#define TELEGRAPH_CSVOUT_H

#include <stdio.h>

/* Snapshot writer for the field.csv output. The file carries the header t,x,u,v
 * followed by one row per snapshot time and grid point, all N points in
 * increasing x with snapshots in the order they are written. Each row lists the
 * time, the coordinate, the displacement u, and its time derivative v = u_t. The
 * evolving state is one array of length 2N: displacement in state[0 .. N-1] and
 * velocity in state[N .. 2N-1]. */

FILE *csv_open(const char *path);

/* Write the header line "t,x,u,v". */
void csv_header(FILE *o);

/* Write one snapshot block: N rows (ts, x[i], state[i], state[N+i]) in
 * increasing x. */
void csv_write_snapshot(FILE *o, double ts, const double *x, const double *state,
                        int N);

#endif /* TELEGRAPH_CSVOUT_H */
