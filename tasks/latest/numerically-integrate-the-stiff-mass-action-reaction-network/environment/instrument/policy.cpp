#include "policy.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace {

const double SAFE_ACCEPT = 0.8317;
const double EXPONENT_CURRENT = 0.1743;
const double EXPONENT_HISTORY = 0.0621;
const double GROWTH_CEILING = 6.25;
const double SHRINK_FLOOR_ACCEPT = 0.2431;
const double SAFE_REJECT = 0.7124;
const double EXPONENT_REJECT = 0.2589;
const double SHRINK_FLOOR_REJECT = 0.1136;
const double OPENING_FRACTION = 1.0 / 512.0;
const long ATTEMPT_BUDGET = 18000;
const double SCORE_FLOOR = 1.0e-10;
const double HISTORY_FLOOR = 1.0e-4;

void realize(std::vector<double> &v) {
    for (std::size_t i = 0; i < v.size(); ++i) {
        if (v[i] < 0.0) v[i] = 0.0;
    }
}

}  // namespace

RunResult integrate(const Network &net, const Tableau &tab, bool keep_trace) {
    const int n = static_cast<int>(net.species.size());
    RunResult r;
    r.verdict = "converged";

    std::vector<double> y = net.initial;
    double t = net.t0;
    double h = (net.t1 - net.t0) * OPENING_FRACTION;

    std::vector<double> probe(n);
    derivative(net, y, probe);
    r.derivative_evals += 1;

    std::vector<std::vector<double> > k(6, std::vector<double>(n, 0.0));
    std::vector<double> stage(n), upper(n), lower(n);

    double history = 1.0;
    long attempts = 0;
    long step_index = 0;

    while (t < net.t1) {
        if (attempts >= ATTEMPT_BUDGET) {
            r.verdict = "step_budget";
            break;
        }
        if (t + h > net.t1) h = net.t1 - t;

        for (int s = 0; s < 6; ++s) {
            for (int i = 0; i < n; ++i) {
                double acc = y[i];
                for (int j = 0; j < s; ++j) acc += h * tab.a[s][j] * k[j][i];
                stage[i] = acc;
            }
            derivative(net, stage, k[s]);
        }
        r.derivative_evals += 6;
        attempts += 1;

        for (int i = 0; i < n; ++i) {
            double su = 0.0, sl = 0.0;
            for (int s = 0; s < 6; ++s) {
                su += tab.upper[s] * k[s][i];
                sl += tab.lower[s] * k[s][i];
            }
            upper[i] = y[i] + h * su;
            lower[i] = y[i] + h * sl;
        }
        realize(upper);
        realize(lower);

        double score = 0.0;
        for (int i = 0; i < n; ++i) {
            double scale = net.atol + net.rtol * std::max(std::fabs(y[i]), std::fabs(lower[i]));
            double e = std::fabs(upper[i] - lower[i]) / scale;
            if (!(e <= std::numeric_limits<double>::max())) {
                score = std::numeric_limits<double>::infinity();
                break;
            }
            if (e > score) score = e;
        }

        const bool ok = (score <= 1.0);
        if (keep_trace) {
            StepRecord rec;
            rec.index = step_index;
            rec.t = t;
            rec.h = h;
            rec.accepted = ok ? 1 : 0;
            r.trace.push_back(rec);
        }
        step_index += 1;

        if (ok) {
            t += h;
            y = lower;
            r.accepted += 1;
            const double e = std::max(score, SCORE_FLOOR);
            const double eh = std::max(history, HISTORY_FLOOR);
            double factor = SAFE_ACCEPT * std::pow(e, -EXPONENT_CURRENT) * std::pow(eh, EXPONENT_HISTORY);
            factor = std::min(GROWTH_CEILING, std::max(SHRINK_FLOOR_ACCEPT, factor));
            h *= factor;
            history = score;
        } else {
            r.rejected += 1;
            const double e = std::max(score, SCORE_FLOOR);
            double factor = SAFE_REJECT * std::pow(e, -EXPONENT_REJECT);
            factor = std::min(1.0, std::max(SHRINK_FLOOR_REJECT, factor));
            h *= factor;
        }
    }

    r.stop_time = t;
    r.final_state = y;
    return r;
}
