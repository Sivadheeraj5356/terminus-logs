#include <stdio.h>
#include <stdlib.h>

#include "config.h"
#include "csvout.h"
#include "field.h"
#include "grid.h"
#include "model.h"
#include "profile.h"
#include "scheme.h"

/* Command-line driver for the damped wave solver.
 *
 *   solver <input.json> <output.csv>
 *
 * Reads the run description, samples the initial displacement onto the pinned
 * grid x_i = i/N, and starts the field from rest (velocity zero). The evolving
 * state is one array of length 2N: displacement in the first N entries and its
 * time derivative u_t in the second N. The driver advances the state snapshot by
 * snapshot through the integrator in scheme.c and writes one CSV block per
 * snapshot time. The first snapshot at t = 0 records the initial data. */
int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: solver <input.json> <output.csv>\n");
        return 1;
    }

    Model m;
    if (config_load(argv[1], &m) != 0) {
        fprintf(stderr, "cannot open input\n");
        return 1;
    }

    double *x = field_alloc(m.N);
    double *state = field_alloc(2 * m.N); /* [0..N-1] displacement, [N..2N-1] velocity */
    grid_points(x, m.N);
    profile_sample(&m.profile, x, state, m.N); /* velocity stays 0: released from rest */

    FILE *o = csv_open(argv[2]);
    if (!o) {
        fprintf(stderr, "cannot open output\n");
        return 1;
    }
    csv_header(o);

    double t = 0.0;
    for (int k = 0; k < m.nsnap; k++) {
        double ts = m.snaps[k];
        scheme_advance(&m, state, t, ts);
        t = ts;
        csv_write_snapshot(o, ts, x, state, m.N);
    }

    fclose(o);
    free(state);
    free(x);
    return 0;
}
