#include "solver.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace {

using Poly = std::vector<long double>;

void trim(Poly& p) {
    while (p.size() > 1 && std::fabs(p.back()) < 1e-24L) p.pop_back();
}

long double peval(const Poly& p, long double x) {
    long double y = 0;
    for (auto it = p.rbegin(); it != p.rend(); ++it) y = y * x + *it;
    return y;
}

Poly derivative(const Poly& p) {
    if (p.size() <= 1) return {0};
    Poly out(p.size() - 1);
    for (std::size_t i = 1; i < p.size(); ++i) out[i - 1] = static_cast<long double>(i) * p[i];
    trim(out);
    return out;
}

Poly multiply(const Poly& a, const Poly& b) {
    Poly out(a.size() + b.size() - 1, 0);
    for (std::size_t i = 0; i < a.size(); ++i) {
        for (std::size_t j = 0; j < b.size(); ++j) out[i + j] += a[i] * b[j];
    }
    trim(out);
    return out;
}

long double bisect_poly(const Poly& p, long double a, long double b, long double fa, long double fb) {
    for (int iter = 0; iter < 180; ++iter) {
        const long double m = (a + b) / 2;
        const long double fm = peval(p, m);
        if (std::fabs(fm) < 1e-20L || b - a < 1e-14L * (1 + std::fabs(m))) return m;
        if ((fa < 0 && fm > 0) || (fa > 0 && fm < 0) || fm == 0) {
            b = m;
            fb = fm;
        } else {
            a = m;
            fa = fm;
        }
    }
    (void)fb;
    return (a + b) / 2;
}

std::vector<long double> polynomial_roots(Poly p, long double lo, long double hi) {
    trim(p);
    const int degree = static_cast<int>(p.size()) - 1;
    if (degree <= 0) return {};
    if (degree == 1) {
        const long double x = -p[0] / p[1];
        if (x >= lo - 1e-12L && x <= hi + 1e-12L) return {std::clamp(x, lo, hi)};
        return {};
    }

    auto critical = polynomial_roots(derivative(p), lo, hi);
    std::vector<long double> points{lo};
    for (long double x : critical) {
        if (x > lo + 1e-13L && x < hi - 1e-13L) points.push_back(x);
    }
    points.push_back(hi);
    std::sort(points.begin(), points.end());

    std::vector<long double> roots;
    for (long double x : points) {
        if (std::fabs(peval(p, x)) < 1e-13L) roots.push_back(x);
    }
    for (std::size_t i = 1; i < points.size(); ++i) {
        const long double a = points[i - 1];
        const long double b = points[i];
        const long double fa = peval(p, a);
        const long double fb = peval(p, b);
        if (fa == 0 || fb == 0) continue;
        if ((fa < 0 && fb > 0) || (fa > 0 && fb < 0)) roots.push_back(bisect_poly(p, a, b, fa, fb));
    }
    std::sort(roots.begin(), roots.end());
    std::vector<long double> unique;
    for (long double x : roots) {
        if (x < lo - 1e-10L || x > hi + 1e-10L) continue;
        if (unique.empty() || std::fabs(x - unique.back()) > 2e-9L * (1 + std::fabs(x))) unique.push_back(std::clamp(x, lo, hi));
    }
    return unique;
}

bool stop_active_mid(const Stop& s, long double x) {
    return s.sense == "upper" ? x > s.angle : x < s.angle;
}

Poly numerator_derivative(const Model& model, long double midpoint) {
    Poly f{0, model.a1, 0, model.a3, 0, model.a5};
    for (const auto& s : model.stops) {
        if (stop_active_mid(s, midpoint)) {
            f[1] += s.stiffness;
            f[0] -= s.stiffness * s.angle;
        }
    }
    Poly d{model.b1, 0, model.b3};
    Poly a = multiply(derivative(f), d);
    Poly b = multiply(f, derivative(d));
    const std::size_t n = std::max(a.size(), b.size());
    a.resize(n, 0);
    b.resize(n, 0);
    Poly out(n, 0);
    for (std::size_t i = 0; i < n; ++i) out[i] = a[i] - b[i];
    trim(out);
    return out;
}

std::vector<long double> stop_cuts(const Model& model) {
    std::vector<long double> cuts{model.theta_min, model.theta_max};
    for (const auto& s : model.stops) {
        if (s.angle > model.theta_min && s.angle < model.theta_max) cuts.push_back(s.angle);
    }
    std::sort(cuts.begin(), cuts.end());
    cuts.erase(std::unique(cuts.begin(), cuts.end(), [](long double a, long double b) { return std::fabs(a - b) < 1e-12L; }), cuts.end());
    return cuts;
}

std::vector<long double> all_partition_points(const Model& model) {
    auto points = stop_cuts(model);
    auto f = find_limit_thetas(model);
    points.insert(points.end(), f.begin(), f.end());
    std::sort(points.begin(), points.end());
    points.erase(std::unique(points.begin(), points.end(), [](long double a, long double b) { return std::fabs(a - b) < 2e-9L; }), points.end());
    return points;
}

long double bisect_curve(const Model& model, long double load, long double a, long double b) {
    long double fa = load_curve(model, a) - load;
    long double fb = load_curve(model, b) - load;
    for (int iter = 0; iter < 180; ++iter) {
        const long double m = (a + b) / 2;
        const long double fm = load_curve(model, m) - load;
        if (std::fabs(fm) < 1e-18L || b - a < 1e-13L * (1 + std::fabs(m))) return m;
        if ((fa < 0 && fm > 0) || (fa > 0 && fm < 0) || fm == 0) {
            b = m;
            fb = fm;
        } else {
            a = m;
            fa = fm;
        }
    }
    (void)fb;
    return (a + b) / 2;
}

std::pair<long double, long double> branch_bounds(const Model& model, const std::vector<long double>& folds, long double theta) {
    std::vector<long double> points{model.theta_min};
    points.insert(points.end(), folds.begin(), folds.end());
    points.push_back(model.theta_max);
    for (std::size_t i = 1; i < points.size(); ++i) {
        if (theta >= points[i - 1] - 1e-8L && theta <= points[i] + 1e-8L) return {points[i - 1], points[i]};
    }
    throw std::runtime_error("state outside model domain");
}

mj::Value number_array(const std::vector<int>& values) {
    mj::Value::Array out;
    for (int v : values) out.emplace_back(v);
    return mj::Value(std::move(out));
}

mj::Value eq_state_json(const Model& model, long double theta, long double load) {
    const long double tl = tangent(model, theta, load, -1);
    const long double tr = tangent(model, theta, load, 1);
    mj::Value::Object obj;
    obj["active_stops"] = number_array(active_stop_indices(model, theta, 0));
    obj["energy"] = static_cast<double>(energy(model, theta, load));
    obj["stability"] = stability_of(model, theta, load);
    obj["tangent_left"] = static_cast<double>(tl);
    obj["tangent_right"] = static_cast<double>(tr);
    obj["theta"] = static_cast<double>(theta);
    return mj::Value(std::move(obj));
}

}  // namespace

std::vector<long double> find_limit_thetas(const Model& model) {
    const auto cuts = stop_cuts(model);
    std::vector<long double> roots;
    for (std::size_t i = 1; i < cuts.size(); ++i) {
        const long double a = cuts[i - 1];
        const long double b = cuts[i];
        if (b - a < 1e-12L) continue;
        auto candidates = polynomial_roots(numerator_derivative(model, (a + b) / 2), a, b);
        for (long double x : candidates) {
            if (x <= a + 1e-8L || x >= b - 1e-8L) continue;
            const long double h = std::min(1e-5L * (1 + std::fabs(x)), 0.1L * std::min(x - a, b - x));
            if (!(h > 0)) continue;
            const long double center = load_curve(model, x);
            const long double left = load_curve(model, x - h);
            const long double right = load_curve(model, x + h);
            if ((center > left && center > right) || (center < left && center < right)) roots.push_back(x);
        }
    }
    std::sort(roots.begin(), roots.end());
    roots.erase(std::unique(roots.begin(), roots.end(), [](long double a, long double b) { return std::fabs(a - b) < 2e-8L; }), roots.end());
    return roots;
}

std::vector<long double> equilibria_at(const Model& model, long double load) {
    const auto points = all_partition_points(model);
    std::vector<long double> roots;
    for (std::size_t i = 1; i < points.size(); ++i) {
        const long double a = points[i - 1];
        const long double b = points[i];
        const long double ya = load_curve(model, a);
        const long double yb = load_curve(model, b);
        if (load < std::min(ya, yb) - 1e-10L || load > std::max(ya, yb) + 1e-10L) continue;
        const long double fa = ya - load;
        const long double fb = yb - load;
        if (std::fabs(fa) < 1e-10L) roots.push_back(a);
        if (std::fabs(fb) < 1e-10L) roots.push_back(b);
        if ((fa < 0 && fb > 0) || (fa > 0 && fb < 0)) roots.push_back(bisect_curve(model, load, a, b));
    }
    for (long double& root : roots) {
        for (long double point : points) {
            if (std::fabs(root - point) < 1e-8L * (1 + std::fabs(point))) {
                root = point;
                break;
            }
        }
    }
    std::sort(roots.begin(), roots.end());
    roots.erase(std::unique(roots.begin(), roots.end(), [](long double a, long double b) {
                    return std::fabs(a - b) < 2e-7L * (1 + std::fabs(a));
                }),
                roots.end());
    return roots;
}

std::vector<LimitPoint> limit_points(const Model& model) {
    std::vector<LimitPoint> out;
    const auto cuts = stop_cuts(model);
    for (long double theta : find_limit_thetas(model)) {
        long double a = model.theta_min;
        long double b = model.theta_max;
        for (std::size_t i = 1; i < cuts.size(); ++i) {
            if (theta > cuts[i - 1] && theta < cuts[i]) {
                a = cuts[i - 1];
                b = cuts[i];
                break;
            }
        }
        const long double h = std::min(1e-5L * (1 + std::fabs(theta)), 0.1L * std::min(theta - a, b - theta));
        const long double center = load_curve(model, theta);
        const std::string type = center > load_curve(model, theta - h) && center > load_curve(model, theta + h) ? "maximum" : "minimum";
        out.push_back({theta, center, type, active_stop_indices(model, theta, 0)});
    }
    return out;
}

std::vector<SweepState> run_sweep(const Model& model, const Sweep& sweep) {
    auto initial_roots = equilibria_at(model, sweep.loads.front());
    std::vector<long double> stable;
    for (long double x : initial_roots) {
        if (stability_of(model, x, sweep.loads.front()) == "stable") stable.push_back(x);
    }
    if (stable.empty()) throw std::runtime_error("sweep has no initial stable state");
    long double previous = *std::min_element(stable.begin(), stable.end(), [&](long double a, long double b) {
        return std::fabs(a - sweep.initial_theta) < std::fabs(b - sweep.initial_theta);
    });
    if (std::fabs(previous - sweep.initial_theta) > 1e-5L) throw std::runtime_error("initial_theta is not a stable equilibrium");

    std::vector<SweepState> out{{sweep.loads.front(), previous, energy(model, previous, sweep.loads.front()), "initial"}};
    const auto folds = find_limit_thetas(model);
    const int direction = sweep.loads.back() > sweep.loads.front() ? 1 : -1;

    for (std::size_t i = 1; i < sweep.loads.size(); ++i) {
        const long double load = sweep.loads[i];
        const auto bounds = branch_bounds(model, folds, previous);
        auto roots = equilibria_at(model, load);
        std::vector<long double> all_stable;
        std::vector<long double> same_branch;
        for (long double x : roots) {
            if (stability_of(model, x, load) != "stable") continue;
            all_stable.push_back(x);
            if (x >= bounds.first - 1e-8L && x <= bounds.second + 1e-8L) same_branch.push_back(x);
        }
        if (all_stable.empty()) throw std::runtime_error("sweep has no stable state");

        long double current;
        std::string transition;
        if (!same_branch.empty()) {
            current = *std::min_element(same_branch.begin(), same_branch.end(), [&](long double a, long double b) {
                return std::fabs(a - previous) < std::fabs(b - previous);
            });
            transition = "follow";
        } else {
            const long double residual = force(model, previous) - load * drive(model, previous);
            int move = residual > 1e-9L ? -1 : residual < -1e-9L ? 1 : direction;
            std::vector<long double> side;
            for (long double x : all_stable) {
                if ((x - previous) * move > 1e-9L) side.push_back(x);
            }
            const auto& pool = side.empty() ? all_stable : side;
            current = *std::min_element(pool.begin(), pool.end(), [&](long double a, long double b) {
                return std::fabs(a - previous) < std::fabs(b - previous);
            });
            transition = "snap";
        }
        out.push_back({load, current, energy(model, current, load), transition});
        previous = current;
    }
    return out;
}

mj::Value build_report(const Campaign& campaign) {
    mj::Value::Object root;
    root["campaign"] = campaign.campaign;

    mj::Value::Array eq_queries;
    for (long double load : campaign.equilibrium_loads) {
        mj::Value::Object query;
        query["load"] = static_cast<double>(load);
        mj::Value::Array states;
        for (long double theta : equilibria_at(campaign.model, load)) states.push_back(eq_state_json(campaign.model, theta, load));
        query["states"] = mj::Value(std::move(states));
        eq_queries.emplace_back(std::move(query));
    }
    root["equilibria"] = mj::Value(std::move(eq_queries));

    mj::Value::Array lp_array;
    for (const auto& p : limit_points(campaign.model)) {
        mj::Value::Object obj;
        obj["active_stops"] = number_array(p.active_stops);
        obj["load"] = static_cast<double>(p.load);
        obj["theta"] = static_cast<double>(p.theta);
        obj["type"] = p.type;
        lp_array.emplace_back(std::move(obj));
    }
    root["limit_points"] = mj::Value(std::move(lp_array));

    root["schema"] = "kirigami-snapthrough-v1";
    mj::Value::Array sweep_array;
    for (const auto& sw : campaign.sweeps) {
        mj::Value::Object sw_obj;
        sw_obj["id"] = sw.id;
        mj::Value::Array states;
        for (const auto& state : run_sweep(campaign.model, sw)) {
            mj::Value::Object obj;
            obj["energy"] = static_cast<double>(state.energy);
            obj["load"] = static_cast<double>(state.load);
            obj["theta"] = static_cast<double>(state.theta);
            obj["transition"] = state.transition;
            states.emplace_back(std::move(obj));
        }
        sw_obj["states"] = mj::Value(std::move(states));
        sweep_array.emplace_back(std::move(sw_obj));
    }
    root["sweeps"] = mj::Value(std::move(sweep_array));
    return mj::Value(std::move(root));
}
