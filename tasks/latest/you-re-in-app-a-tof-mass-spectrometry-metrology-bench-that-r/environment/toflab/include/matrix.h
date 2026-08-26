#ifndef TOFLAB_MATRIX_H
#define TOFLAB_MATRIX_H

#include <stddef.h>

typedef struct {
    double m[3][3];
} Mat3;

typedef struct {
    double v[3];
} Vec3;

void mat3_zero(Mat3 *a);
void mat3_identity(Mat3 *a);
void mat3_copy(Mat3 *dst, const Mat3 *src);
void mat3_add(Mat3 *out, const Mat3 *a, const Mat3 *b);
void mat3_scale(Mat3 *out, const Mat3 *a, double s);
void mat3_mul(Mat3 *out, const Mat3 *a, const Mat3 *b);
void mat3_transpose(Mat3 *out, const Mat3 *a);
double mat3_det(const Mat3 *a);
int mat3_inv(Mat3 *out, const Mat3 *a);
int mat3_chol(Mat3 *L, const Mat3 *a);
int mat3_is_spd(const Mat3 *a);
double mat3_gscale(const Mat3 *a);

void vec3_zero(Vec3 *v);
void vec3_copy(Vec3 *dst, const Vec3 *src);
void vec3_add(Vec3 *out, const Vec3 *a, const Vec3 *b);
void vec3_scale(Vec3 *out, const Vec3 *a, double s);
void mat3_vec_mul(Vec3 *out, const Mat3 *a, const Vec3 *v);
double vec3_dot(const Vec3 *a, const Vec3 *b);
double quad_form(const Vec3 *x, const Mat3 *a);

void cov_from_sigmas(Mat3 *out, double sk, double st0, double sq,
                     double rkt0, double rkq, double rt0q);
int apply_unit_scale(Vec3 *theta, Mat3 *cov, double sk, double st0, double sq);

#endif
