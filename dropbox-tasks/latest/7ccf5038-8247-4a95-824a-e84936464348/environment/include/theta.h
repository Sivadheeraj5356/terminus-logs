#ifndef THETA_H
#define THETA_H

/* Weighted sum S = sum_i c[i] * theta3(z[i], q[i]), where
 * theta3(z, q) = 1 + 2 * sum_{k>=1} q^(k^2) * cos(2 k z).
 *
 * The coefficients c, angles z, and nomes q are passed as the decimal strings
 * read from the input file. The single result S is returned through out[0].
 */
void theta3(int n, const char *const *c, const char *const *z,
            const char *const *q, double *out);

#endif
