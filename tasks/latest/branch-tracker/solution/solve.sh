#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/src/continuation.cpp <<'SRC'
#include "continuation.hpp"

#include <cmath>
#include <cstdlib>
#include <vector>

namespace {

const int N = kNodes;
const double H = 1.0 / (N + 1);
const double DS_NOMINAL = 5e-4;

bool is_bratu(const std::string &p) { return p == "bratu"; }

double gfun(bool bratu, double v) { return bratu ? std::exp(v) : v - v * v * v; }
double gder(bool bratu, double v) { return bratu ? std::exp(v) : 1.0 - 3.0 * v * v; }

void residual(bool bratu, const std::vector<double> &y, std::vector<double> &r) {
    double lam = y[N];
    for (int i = 0; i < N; i++) {
        double um = (i == 0) ? 0.0 : y[i - 1];
        double up = (i == N - 1) ? 0.0 : y[i + 1];
        r[i] = (um - 2.0 * y[i] + up) / (H * H) + lam * gfun(bratu, y[i]);
    }
}

// Dense Gaussian elimination with partial pivoting; A is n x n row-major.
bool solve_lin(std::vector<double> &A, std::vector<double> &b, int n) {
    for (int c = 0; c < n; c++) {
        int piv = c;
        double best = std::fabs(A[c * n + c]);
        for (int r = c + 1; r < n; r++) {
            double v = std::fabs(A[r * n + c]);
            if (v > best) {
                best = v;
                piv = r;
            }
        }
        if (best < 1e-300) return false;
        if (piv != c) {
            for (int j = 0; j < n; j++) std::swap(A[c * n + j], A[piv * n + j]);
            std::swap(b[c], b[piv]);
        }
        double d = A[c * n + c];
        for (int r = c + 1; r < n; r++) {
            double f = A[r * n + c] / d;
            if (f == 0.0) continue;
            for (int j = c; j < n; j++) A[r * n + j] -= f * A[c * n + j];
            b[r] -= f * b[c];
        }
    }
    for (int r = n - 1; r >= 0; r--) {
        double s = b[r];
        for (int j = r + 1; j < n; j++) s -= A[r * n + j] * b[j];
        b[r] = s / A[r * n + r];
    }
    return true;
}

// Rows 0..N-1 hold [dR/du | dR/dlambda]; row N holds the tangent constraint.
void bordered(bool bratu, const std::vector<double> &y, const std::vector<double> &t,
              std::vector<double> &A) {
    int n = N + 1;
    std::fill(A.begin(), A.end(), 0.0);
    double lam = y[N];
    for (int i = 0; i < N; i++) {
        A[i * n + i] = -2.0 / (H * H) + lam * gder(bratu, y[i]);
        if (i > 0) A[i * n + (i - 1)] = 1.0 / (H * H);
        if (i < N - 1) A[i * n + (i + 1)] = 1.0 / (H * H);
        A[i * n + N] = gfun(bratu, y[i]);
    }
    for (int j = 0; j < n; j++) A[N * n + j] = t[j];
}

void normalize(std::vector<double> &v) {
    double s = 0.0;
    for (double q : v) s += q * q;
    s = std::sqrt(s);
    for (double &q : v) q /= s;
}

// Newton with the chord constraint <y - y_prev, t> = ds.
std::vector<double> corrector(bool bratu, const std::vector<double> &y_prev,
                              const std::vector<double> &t, double ds,
                              std::vector<double> y) {
    int n = N + 1;
    std::vector<double> A(n * n), rhs(n), r(N);
    for (int it = 0; it < 60; it++) {
        residual(bratu, y, r);
        double c = -ds;
        for (int j = 0; j < n; j++) c += (y[j] - y_prev[j]) * t[j];
        for (int i = 0; i < N; i++) rhs[i] = -r[i];
        rhs[N] = -c;
        bordered(bratu, y, t, A);
        if (!solve_lin(A, rhs, n)) break;
        double step = 0.0;
        for (int j = 0; j < n; j++) {
            y[j] += rhs[j];
            step += std::fabs(rhs[j]);
        }
        if (step < 1e-14) break;
    }
    return y;
}

void start_state(bool bratu, int k, std::vector<double> &y, std::vector<double> &t) {
    int n = N + 1;
    y.assign(n, 0.0);
    t.assign(n, 0.0);
    if (bratu) {
        // u = 0, lambda = 0; tangent from dR/du * z = -dR/dlambda, oriented to
        // increasing lambda.
        std::vector<double> A(N * N, 0.0), b(N);
        for (int i = 0; i < N; i++) {
            A[i * N + i] = -2.0 / (H * H);
            if (i > 0) A[i * N + (i - 1)] = 1.0 / (H * H);
            if (i < N - 1) A[i * N + (i + 1)] = 1.0 / (H * H);
            b[i] = -gfun(true, 0.0);
        }
        solve_lin(A, b, N);
        for (int i = 0; i < N; i++) t[i] = b[i];
        t[N] = 1.0;
        normalize(t);
        if (t[N] < 0.0) {
            for (double &q : t) q = -q;
        }
        return;
    }
    // cubic: the branch meets the trivial branch where dR/du is singular.
    double sk = std::sin(k * M_PI * H / 2.0);
    y[N] = (4.0 / (H * H)) * sk * sk;
    for (int i = 0; i < N; i++) t[i] = std::sin(k * M_PI * (i + 1) * H);
    normalize(t);
    if (t[0] < 0.0) {
        for (int i = 0; i < N; i++) t[i] = -t[i];
    }
    t[N] = 0.0;
}

// March to every target, subdividing each segment so it lands exactly on the
// target; `refine` multiplies the step count.
std::vector<std::vector<double>> march(bool bratu, int k,
                                       const std::vector<double> &targets, int refine) {
    std::vector<double> y, t;
    start_state(bratu, k, y, t);
    std::vector<std::vector<double>> out;
    double s_at = 0.0;
    for (double s_target : targets) {
        double span = s_target - s_at;
        if (span > 0.0) {
            long nsteps = static_cast<long>(std::ceil(span / DS_NOMINAL)) * refine;
            if (nsteps < refine) nsteps = refine;
            double ds = span / static_cast<double>(nsteps);
            for (long i = 0; i < nsteps; i++) {
                std::vector<double> yp(y.size());
                for (size_t j = 0; j < y.size(); j++) yp[j] = y[j] + ds * t[j];
                std::vector<double> yn = corrector(bratu, y, t, ds, yp);
                double nrm = 0.0;
                for (size_t j = 0; j < y.size(); j++) nrm += (yn[j] - y[j]) * (yn[j] - y[j]);
                nrm = std::sqrt(nrm);
                if (nrm > 1e-14) {
                    for (size_t j = 0; j < y.size(); j++) t[j] = (yn[j] - y[j]) / nrm;
                }
                y = yn;
            }
            s_at = s_target;
        }
        out.push_back(y);
    }
    return out;
}

}  // namespace

std::vector<CurvePoint> trace_branch(const std::string &problem, int k,
                                     const std::vector<double> &arclengths) {
    bool bratu = is_bratu(problem);
    // The chord constraint tracks arclength only to O(ds^2); extrapolate the
    // two step resolutions to remove the leading term.
    std::vector<std::vector<double>> a = march(bratu, k, arclengths, 1);
    std::vector<std::vector<double>> b = march(bratu, k, arclengths, 2);

    std::vector<CurvePoint> out;
    for (size_t j = 0; j < arclengths.size(); j++) {
        CurvePoint p;
        p.u.resize(N);
        for (int i = 0; i < N; i++) p.u[i] = (4.0 * b[j][i] - a[j][i]) / 3.0;
        p.lambda = (4.0 * b[j][N] - a[j][N]) / 3.0;
        out.push_back(p);
    }
    return out;
}
SRC

cd /app/environment
make clean >/dev/null
make
bash scripts/run_all.sh
echo "oracle build and run complete"
