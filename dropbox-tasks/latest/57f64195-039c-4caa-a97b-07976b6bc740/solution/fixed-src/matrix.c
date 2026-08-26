#include "matrix.h"

#include <math.h>
#include <string.h>

void mat3_zero(Mat3 *a) {
    memset(a, 0, sizeof(*a));
}

void mat3_identity(Mat3 *a) {
    mat3_zero(a);
    a->m[0][0] = a->m[1][1] = a->m[2][2] = 1.0;
}

void mat3_copy(Mat3 *dst, const Mat3 *src) {
    *dst = *src;
}

void mat3_add(Mat3 *out, const Mat3 *a, const Mat3 *b) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            out->m[i][j] = a->m[i][j] + b->m[i][j];
        }
    }
}

void mat3_scale(Mat3 *out, const Mat3 *a, double s) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            out->m[i][j] = a->m[i][j] * s;
        }
    }
}

void mat3_mul(Mat3 *out, const Mat3 *a, const Mat3 *b) {
    Mat3 tmp;
    mat3_zero(&tmp);
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            for (int k = 0; k < 3; k++) {
                tmp.m[i][j] += a->m[i][k] * b->m[k][j];
            }
        }
    }
    *out = tmp;
}

void mat3_transpose(Mat3 *out, const Mat3 *a) {
    Mat3 tmp;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            tmp.m[i][j] = a->m[j][i];
        }
    }
    *out = tmp;
}

double mat3_det(const Mat3 *a) {
    const double (*m)[3] = a->m;
    return m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
           m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
           m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
}

int mat3_chol(Mat3 *L, const Mat3 *a) {
    mat3_zero(L);
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j <= i; j++) {
            double sum = a->m[i][j];
            for (int k = 0; k < j; k++) {
                sum -= L->m[i][k] * L->m[j][k];
            }
            if (i == j) {
                if (!(sum > 0.0) || !isfinite(sum)) {
                    return -1;
                }
                L->m[i][j] = sqrt(sum);
            } else {
                if (fabs(L->m[j][j]) < 1e-300) {
                    return -1;
                }
                L->m[i][j] = sum / L->m[j][j];
            }
        }
    }
    return 0;
}

int mat3_is_spd(const Mat3 *a) {
    Mat3 L;
    return mat3_chol(&L, a) == 0;
}

int mat3_inv(Mat3 *out, const Mat3 *a) {
    double det = mat3_det(a);
    if (!isfinite(det) || fabs(det) < 1e-300) {
        return -1;
    }
    const double (*m)[3] = a->m;
    out->m[0][0] = (m[1][1] * m[2][2] - m[1][2] * m[2][1]) / det;
    out->m[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) / det;
    out->m[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) / det;
    out->m[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) / det;
    out->m[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) / det;
    out->m[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) / det;
    out->m[2][0] = (m[1][0] * m[2][1] - m[1][1] * m[2][0]) / det;
    out->m[2][1] = (m[0][1] * m[2][0] - m[0][0] * m[2][1]) / det;
    out->m[2][2] = (m[0][0] * m[1][1] - m[0][1] * m[1][0]) / det;
    return 0;
}

double mat3_gscale(const Mat3 *a) {
    double d = mat3_det(a);
    if (!(d > 0.0) || !isfinite(d)) {
        return NAN;
    }
    return pow(d, 1.0 / 6.0);
}

void vec3_zero(Vec3 *v) {
    v->v[0] = v->v[1] = v->v[2] = 0.0;
}

void vec3_copy(Vec3 *dst, const Vec3 *src) {
    *dst = *src;
}

void vec3_add(Vec3 *out, const Vec3 *a, const Vec3 *b) {
    out->v[0] = a->v[0] + b->v[0];
    out->v[1] = a->v[1] + b->v[1];
    out->v[2] = a->v[2] + b->v[2];
}

void vec3_scale(Vec3 *out, const Vec3 *a, double s) {
    out->v[0] = a->v[0] * s;
    out->v[1] = a->v[1] * s;
    out->v[2] = a->v[2] * s;
}

void mat3_vec_mul(Vec3 *out, const Mat3 *a, const Vec3 *v) {
    Vec3 tmp;
    for (int i = 0; i < 3; i++) {
        tmp.v[i] = a->m[i][0] * v->v[0] + a->m[i][1] * v->v[1] + a->m[i][2] * v->v[2];
    }
    *out = tmp;
}

double vec3_dot(const Vec3 *a, const Vec3 *b) {
    return a->v[0] * b->v[0] + a->v[1] * b->v[1] + a->v[2] * b->v[2];
}

double quad_form(const Vec3 *x, const Mat3 *a) {
    Vec3 ax;
    mat3_vec_mul(&ax, a, x);
    return vec3_dot(x, &ax);
}

void cov_from_sigmas(Mat3 *out, double sk, double st0, double sq,
                     double rkt0, double rkq, double rt0q) {
    out->m[0][0] = sk * sk;
    out->m[1][1] = st0 * st0;
    out->m[2][2] = sq * sq;
    out->m[0][1] = out->m[1][0] = rkt0 * sk * st0;
    out->m[0][2] = out->m[2][0] = rkq * sk * sq;
    out->m[1][2] = out->m[2][1] = rt0q * st0 * sq;
}

int apply_unit_scale(Vec3 *theta, Mat3 *cov, double sk, double st0, double sq) {
    Mat3 S, St, tmp, out;
    mat3_zero(&S);
    S.m[0][0] = sk;
    S.m[1][1] = st0;
    S.m[2][2] = sq;
    theta->v[0] *= sk;
    theta->v[1] *= st0;
    theta->v[2] *= sq;
    mat3_mul(&tmp, &S, cov);
    mat3_transpose(&St, &S);
    mat3_mul(&out, &tmp, &St);
    *cov = out;
    return 0;
}
