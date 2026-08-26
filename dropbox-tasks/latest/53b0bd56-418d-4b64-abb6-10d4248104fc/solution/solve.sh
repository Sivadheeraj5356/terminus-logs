#!/usr/bin/env bash
#
# Recovers the Halvard bench's certified integration protocol by driving the
# surviving bench executable, then integrates arbitrary reaction networks under
# the recovered protocol. Nothing about the protocol is assumed: the propagated
# companion, the error norm, the scaling rule, the physical clamp, the two
# controller branches, the floors, the growth ceiling and the attempt budget are
# all derived from observed bench behaviour and verified by exact replay of every
# calibration run before a single assay network is integrated.

set -euo pipefail

mkdir -p /app/bin
BUILD=/app/build
mkdir -p "$BUILD"
SRC=$BUILD/integrate.cpp

cat > "$SRC" <<'CPP_EOF'
#include <dirent.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

struct Reaction {
    std::vector<int> reactants;
    std::vector<int> products;
    double rate;
};

struct Network {
    std::string name;
    std::vector<std::string> species;
    std::vector<Reaction> reactions;
    std::vector<double> initial;
    double t0 = 0.0, t1 = 0.0, rtol = 1e-6, atol = 1e-9;
};

struct Tableau {
    double node[6];
    double a[6][6];
    double upper[6];
    double lower[6];
};

struct StepObs {
    double t, h;
    int accepted;
};

struct Summary {
    std::string verdict;
    double stop_time = 0.0;
    long accepted = 0, rejected = 0, derivative_evals = 0;
    std::vector<double> final_state;
};

struct Probe {
    Network net;
    std::vector<StepObs> trace;
    Summary summary;
};

// Every field is derived from the bench's behaviour; none is assumed.
struct Policy {
    int propagate;   // 0 = lower companion advances, 1 = upper companion
    int norm;        // 0 = componentwise maximum, 1 = root mean square
    int clamp;       // 1 = negative concentrations zeroed before scoring
    int scale;       // 0 = max(|y|, |candidate|), 1 = |y| alone
    double safe_acc, exp_cur, exp_hist, grow_max, shrink_acc;
    double safe_rej, exp_rej, shrink_rej;
    double opening;
    double score_floor, history_floor;
    long budget;
    long startup_evals;
};

static void derivative(const Network &net, const std::vector<double> &y, std::vector<double> &dy) {
    const std::size_t n = net.species.size();
    dy.assign(n, 0.0);
    for (std::size_t r = 0; r < net.reactions.size(); ++r) {
        const Reaction &rx = net.reactions[r];
        double flux = rx.rate;
        for (std::size_t i = 0; i < rx.reactants.size(); ++i) flux *= y[rx.reactants[i]];
        for (std::size_t i = 0; i < rx.reactants.size(); ++i) dy[rx.reactants[i]] -= flux;
        for (std::size_t i = 0; i < rx.products.size(); ++i) dy[rx.products[i]] += flux;
    }
}

static bool load_tableau(const std::string &path, Tableau &out) {
    std::ifstream in(path);
    if (!in) return false;
    for (int i = 0; i < 6; ++i) {
        out.node[i] = out.upper[i] = out.lower[i] = 0.0;
        for (int j = 0; j < 6; ++j) out.a[i][j] = 0.0;
    }
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::istringstream iss(line);
        std::string key;
        iss >> key;
        std::vector<double> v;
        std::string tok;
        while (iss >> tok) v.push_back(std::strtod(tok.c_str(), nullptr));
        if (key == "node" && v.size() == 6) {
            for (int i = 0; i < 6; ++i) out.node[i] = v[i];
        } else if (key == "upper" && v.size() == 6) {
            for (int i = 0; i < 6; ++i) out.upper[i] = v[i];
        } else if (key == "lower" && v.size() == 6) {
            for (int i = 0; i < 6; ++i) out.lower[i] = v[i];
        } else if (key.rfind("stage", 0) == 0) {
            int idx = std::atoi(key.substr(5).c_str()) - 1;
            if (idx >= 1 && idx <= 5 && (int)v.size() == idx)
                for (int j = 0; j < idx; ++j) out.a[idx][j] = v[j];
        }
    }
    return true;
}

static int species_index(const Network &net, const std::string &nm) {
    for (std::size_t i = 0; i < net.species.size(); ++i)
        if (net.species[i] == nm) return (int)i;
    return -1;
}

static bool parse_side(const Network &net, const std::string &text, std::vector<int> &out) {
    std::istringstream iss(text);
    std::string tok;
    while (iss >> tok) {
        if (tok == "+") continue;
        int i = species_index(net, tok);
        if (i < 0) return false;
        out.push_back(i);
    }
    return !out.empty();
}

static bool load_network(const std::string &path, Network &out) {
    std::ifstream in(path);
    if (!in) return false;
    out = Network();
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::istringstream iss(line);
        std::string key;
        iss >> key;
        if (key == "network") {
            iss >> out.name;
        } else if (key == "species") {
            std::string s;
            while (iss >> s) out.species.push_back(s);
            out.initial.assign(out.species.size(), 0.0);
        } else if (key == "initial") {
            std::string s;
            double v = 0.0;
            iss >> s >> v;
            int i = species_index(out, s);
            if (i >= 0) out.initial[i] = v;
        } else if (key == "reaction") {
            double rate = 0.0;
            iss >> rate;
            std::string rest;
            std::getline(iss, rest);
            std::size_t arrow = rest.find("->");
            if (arrow == std::string::npos) return false;
            Reaction rx;
            rx.rate = rate;
            if (!parse_side(out, rest.substr(0, arrow), rx.reactants)) return false;
            if (!parse_side(out, rest.substr(arrow + 2), rx.products)) return false;
            out.reactions.push_back(rx);
        } else if (key == "horizon") {
            iss >> out.t0 >> out.t1;
        } else if (key == "rtol") {
            iss >> out.rtol;
        } else if (key == "atol") {
            iss >> out.atol;
        }
    }
    return !out.species.empty() && !out.reactions.empty();
}

struct Trial {
    std::vector<double> upper, lower, candidate;
    double score;
};

static Trial trial_step(const Network &net, const Tableau &tab, const Policy &p,
                        const std::vector<double> &y, double h) {
    const int n = (int)net.species.size();
    std::vector<std::vector<double> > k(6, std::vector<double>(n, 0.0));
    std::vector<double> stage(n);
    for (int s = 0; s < 6; ++s) {
        for (int i = 0; i < n; ++i) {
            double acc = y[i];
            for (int j = 0; j < s; ++j) acc += h * tab.a[s][j] * k[j][i];
            stage[i] = acc;
        }
        derivative(net, stage, k[s]);
    }
    Trial tr;
    tr.upper.assign(n, 0.0);
    tr.lower.assign(n, 0.0);
    for (int i = 0; i < n; ++i) {
        double su = 0.0, sl = 0.0;
        for (int s = 0; s < 6; ++s) {
            su += tab.upper[s] * k[s][i];
            sl += tab.lower[s] * k[s][i];
        }
        tr.upper[i] = y[i] + h * su;
        tr.lower[i] = y[i] + h * sl;
    }
    if (p.clamp == 1) {
        for (int i = 0; i < n; ++i) {
            if (tr.upper[i] < 0.0) tr.upper[i] = 0.0;
            if (tr.lower[i] < 0.0) tr.lower[i] = 0.0;
        }
    }
    tr.candidate = (p.propagate == 0) ? tr.lower : tr.upper;

    double worst = 0.0, sq = 0.0;
    bool blew = false;
    for (int i = 0; i < n; ++i) {
        const double ref = (p.scale == 0)
                               ? std::max(std::fabs(y[i]), std::fabs(tr.candidate[i]))
                               : std::fabs(y[i]);
        const double sc = net.atol + net.rtol * ref;
        const double e = std::fabs(tr.upper[i] - tr.lower[i]) / sc;
        if (!(e <= std::numeric_limits<double>::max())) {
            blew = true;
            break;
        }
        if (e > worst) worst = e;
        sq += e * e;
    }
    if (blew) tr.score = std::numeric_limits<double>::infinity();
    else if (p.norm == 0) tr.score = worst;
    else tr.score = std::sqrt(sq / (double)n);
    return tr;
}

static Summary run_policy(const Network &net, const Tableau &tab, const Policy &p) {
    Summary out;
    out.verdict = "converged";
    out.derivative_evals = p.startup_evals;

    std::vector<double> y = net.initial;
    double t = net.t0;
    double h = (net.t1 - net.t0) * p.opening;
    double history = 1.0;
    long attempts = 0;

    while (t < net.t1) {
        if (attempts >= p.budget) {
            out.verdict = "step_budget";
            break;
        }
        if (t + h > net.t1) h = net.t1 - t;

        Trial tr = trial_step(net, tab, p, y, h);
        out.derivative_evals += 6;
        attempts += 1;

        if (tr.score <= 1.0) {
            t += h;
            y = tr.candidate;
            out.accepted += 1;
            const double e = std::max(tr.score, p.score_floor);
            const double eh = std::max(history, p.history_floor);
            double f = p.safe_acc * std::pow(e, -p.exp_cur) * std::pow(eh, p.exp_hist);
            f = std::min(p.grow_max, std::max(p.shrink_acc, f));
            h *= f;
            history = tr.score;
        } else {
            out.rejected += 1;
            const double e = std::max(tr.score, p.score_floor);
            double f = p.safe_rej * std::pow(e, -p.exp_rej);
            f = std::min(1.0, std::max(p.shrink_rej, f));
            h *= f;
        }
    }
    out.stop_time = t;
    out.final_state = y;
    return out;
}

static bool run_bench(const std::string &cmd, std::vector<StepObs> &trace, Summary &sum) {
    FILE *fp = popen(cmd.c_str(), "r");
    if (fp == nullptr) return false;
    char buf[512];
    trace.clear();
    sum = Summary();
    while (std::fgets(buf, sizeof(buf), fp) != nullptr) {
        const std::string line(buf);
        std::istringstream iss(line);
        std::string key;
        iss >> key;
        if (key == "step") {
            long idx;
            StepObs s;
            iss >> idx >> s.t >> s.h >> s.accepted;
            trace.push_back(s);
        } else if (key == "verdict") {
            iss >> sum.verdict;
        } else if (key == "stop_time") {
            iss >> sum.stop_time;
        } else if (key == "accepted") {
            iss >> sum.accepted;
        } else if (key == "rejected") {
            iss >> sum.rejected;
        } else if (key == "derivative_evals") {
            iss >> sum.derivative_evals;
        } else if (key == "final") {
            std::string nm;
            double v;
            iss >> nm >> v;
            sum.final_state.push_back(v);
        }
    }
    return pclose(fp) == 0;
}

// The sweep is chosen so every regime the controller can enter shows up
// somewhere: saturated growth at the loose end, boundary-hugging steps in the
// middle, and heavy rejection on the stiff systems.
static std::vector<Probe> collect_probes() {
    std::vector<Probe> probes;
    std::vector<std::string> names;
    FILE *fp = popen("/app/bench/bench list", "r");
    if (fp == nullptr) return probes;
    char buf[512];
    while (std::fgets(buf, sizeof(buf), fp) != nullptr) {
        const std::string line(buf);
        std::istringstream iss(line);
        std::string nm;
        iss >> nm;
        if (!nm.empty()) names.push_back(nm);
    }
    pclose(fp);

    const double sweeps[4][2] = {{0.0, 0.0}, {1e-2, 1e-5}, {1e-4, 1e-7}, {1e-9, 1e-12}};

    for (std::size_t i = 0; i < names.size(); ++i) {
        Network base;
        if (!load_network("/app/calibration/" + names[i] + ".net", base)) continue;
        for (int s = 0; s < 4; ++s) {
            Probe p;
            p.net = base;
            char cmd[512];
            if (sweeps[s][0] == 0.0) {
                std::snprintf(cmd, sizeof(cmd), "/app/bench/bench run --system %s --trace",
                              names[i].c_str());
            } else {
                p.net.rtol = sweeps[s][0];
                p.net.atol = sweeps[s][1];
                std::snprintf(cmd, sizeof(cmd),
                              "/app/bench/bench run --system %s --rtol %.17g --atol %.17g --trace",
                              names[i].c_str(), sweeps[s][0], sweeps[s][1]);
            }
            if (!run_bench(cmd, p.trace, p.summary)) continue;
            if (p.trace.empty()) continue;
            probes.push_back(p);
        }
    }
    return probes;
}

// Replay the OBSERVED step sizes and ask whether the hypothesis reproduces every
// accept/reject decision the bench actually made. Only the true structure
// survives all traces.
static bool structure_consistent(const std::vector<Probe> &probes, const Tableau &tab,
                                 const Policy &p) {
    for (std::size_t q = 0; q < probes.size(); ++q) {
        const Probe &pr = probes[q];
        std::vector<double> y = pr.net.initial;
        for (std::size_t j = 0; j < pr.trace.size(); ++j) {
            Trial tr = trial_step(pr.net, tab, p, y, pr.trace[j].h);
            const int ok = (tr.score <= 1.0) ? 1 : 0;
            if (ok != pr.trace[j].accepted) return false;
            if (ok) y = tr.candidate;
        }
    }
    return true;
}

static double round_to(double v, int places) {
    const double m = std::pow(10.0, places);
    return std::round(v * m) / m;
}

static bool solve3(double M[3][3], double rhs[3], double out[3]) {
    for (int i = 0; i < 3; ++i) {
        int piv = i;
        for (int r = i + 1; r < 3; ++r)
            if (std::fabs(M[r][i]) > std::fabs(M[piv][i])) piv = r;
        if (std::fabs(M[piv][i]) < 1e-14) return false;
        if (piv != i) {
            for (int c = 0; c < 3; ++c) std::swap(M[i][c], M[piv][c]);
            std::swap(rhs[i], rhs[piv]);
        }
        for (int r = i + 1; r < 3; ++r) {
            const double f = M[r][i] / M[i][i];
            for (int c = i; c < 3; ++c) M[r][c] -= f * M[i][c];
            rhs[r] -= f * rhs[i];
        }
    }
    for (int i = 2; i >= 0; --i) {
        double s = rhs[i];
        for (int c = i + 1; c < 3; ++c) s -= M[i][c] * out[c];
        out[i] = s / M[i][i];
    }
    return true;
}

struct Obs {
    double ratio, e, eh;
};

int main(int argc, char **argv) {
    if (argc < 3) {
        std::fprintf(stderr, "usage: integrate <network_dir> <out_jsonl>\n");
        return 2;
    }
    const std::string dir = argv[1];
    const std::string out_path = argv[2];

    Tableau tab;
    if (!load_tableau("/app/bench/stage_weights.tsv", tab)) {
        std::fprintf(stderr, "the stage weight table is unreadable\n");
        return 3;
    }

    std::vector<Probe> probes = collect_probes();
    if (probes.empty()) {
        std::fprintf(stderr, "the bench produced no usable traces\n");
        return 3;
    }

    Policy zero;
    std::memset(&zero, 0, sizeof(zero));

    bool found = false;
    Policy p = zero;
    for (int prop = 0; prop < 2 && !found; ++prop)
        for (int norm = 0; norm < 2 && !found; ++norm)
            for (int clamp = 0; clamp < 2 && !found; ++clamp)
                for (int scale = 0; scale < 2 && !found; ++scale) {
                    Policy c = zero;
                    c.propagate = prop;
                    c.norm = norm;
                    c.clamp = clamp;
                    c.scale = scale;
                    if (structure_consistent(probes, tab, c)) {
                        p = c;
                        found = true;
                    }
                }
    if (!found) {
        std::fprintf(stderr, "no structural hypothesis reproduces the bench's decisions\n");
        return 4;
    }

    p.opening = probes[0].trace[0].h / (probes[0].net.t1 - probes[0].net.t0);
    p.budget = std::numeric_limits<long>::max();
    for (std::size_t q = 0; q < probes.size(); ++q) {
        if (probes[q].summary.verdict != "converged") {
            const long attempts = probes[q].summary.accepted + probes[q].summary.rejected;
            if (attempts < p.budget) p.budget = attempts;
        }
    }
    if (p.budget == std::numeric_limits<long>::max()) p.budget = 1L << 60;
    p.startup_evals = probes[0].summary.derivative_evals -
                      6 * (probes[0].summary.accepted + probes[0].summary.rejected);

    std::vector<Obs> acc_obs, rej_obs;
    for (std::size_t q = 0; q < probes.size(); ++q) {
        const Probe &pr = probes[q];
        std::vector<double> y = pr.net.initial;
        double history = 1.0;
        for (std::size_t j = 0; j + 1 < pr.trace.size(); ++j) {
            Trial tr = trial_step(pr.net, tab, p, y, pr.trace[j].h);
            const double hn = pr.trace[j + 1].h;
            // A step clipped onto the horizon carries no controller information.
            const bool clipped = (pr.trace[j + 1].t + hn >= pr.net.t1);
            Obs o;
            o.ratio = hn / pr.trace[j].h;
            o.e = tr.score;
            o.eh = history;
            if (pr.trace[j].accepted == 1) {
                if (!clipped) acc_obs.push_back(o);
                y = tr.candidate;
                history = tr.score;
            } else if (!clipped) {
                rej_obs.push_back(o);
            }
        }
    }

    double grow = 0.0;
    for (std::size_t i = 0; i < acc_obs.size(); ++i) grow = std::max(grow, acc_obs[i].ratio);
    p.grow_max = round_to(grow, 4);
    p.shrink_acc = 0.0;

    {
        double M[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
        double rhs[3] = {0, 0, 0};
        long used = 0;
        for (std::size_t i = 0; i < acc_obs.size(); ++i) {
            const Obs &o = acc_obs[i];
            if (!(o.e > 1e-2 && o.e <= 1.0)) continue;
            if (!(o.eh > 1e-2 && o.eh <= 1.0)) continue;
            if (o.ratio >= p.grow_max * (1.0 - 1e-9)) continue;
            const double row[3] = {1.0, -std::log(o.e), std::log(o.eh)};
            const double yv = std::log(o.ratio);
            for (int r = 0; r < 3; ++r) {
                for (int c = 0; c < 3; ++c) M[r][c] += row[r] * row[c];
                rhs[r] += row[r] * yv;
            }
            used += 1;
        }
        if (used < 20) {
            std::fprintf(stderr, "too few clean accepted transitions to fit the controller\n");
            return 5;
        }
        double sol[3];
        if (!solve3(M, rhs, sol)) {
            std::fprintf(stderr, "the accepted-branch fit is singular\n");
            return 5;
        }
        p.safe_acc = round_to(std::exp(sol[0]), 4);
        p.exp_cur = round_to(sol[1], 4);
        p.exp_hist = round_to(sol[2], 4);
    }

    {
        double lo = 1e300;
        for (std::size_t i = 0; i < rej_obs.size(); ++i)
            if (rej_obs[i].ratio > 0.0) lo = std::min(lo, rej_obs[i].ratio);

        double sxx = 0, sx = 0, sy = 0, sxy = 0;
        long used = 0;
        for (std::size_t i = 0; i < rej_obs.size(); ++i) {
            const Obs &o = rej_obs[i];
            if (!(o.e > 1.0 && o.e < 1e6)) continue;
            if (o.ratio <= lo * (1.0 + 1e-9)) continue;
            const double x = -std::log(o.e);
            const double yv = std::log(o.ratio);
            sxx += x * x;
            sx += x;
            sy += yv;
            sxy += x * yv;
            used += 1;
        }
        if (used < 5) {
            std::fprintf(stderr, "too few clean rejected transitions to fit the controller\n");
            return 5;
        }
        const double det = (double)used * sxx - sx * sx;
        const double slope = ((double)used * sxy - sx * sy) / det;
        const double icpt = (sy - slope * sx) / (double)used;
        p.safe_rej = round_to(std::exp(icpt), 4);
        p.exp_rej = round_to(slope, 4);

        bool floored = false;
        for (std::size_t i = 0; i < rej_obs.size(); ++i) {
            const double bare =
                p.safe_rej * std::pow(std::max(rej_obs[i].e, 1e-300), -p.exp_rej);
            if (bare < lo * (1.0 - 1e-6)) floored = true;
        }
        p.shrink_rej = floored ? round_to(lo, 4) : 0.0;
    }

    // The two floors take a handful of candidate values each; the decision is
    // made by exact replay of every calibration run the bench performed.
    const double score_floors[5] = {0.0, 1e-12, 1e-10, 1e-8, 1e-6};
    const double history_floors[6] = {0.0, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2};

    bool verified = false;
    Policy best = p;
    for (int a = 0; a < 5 && !verified; ++a) {
        for (int b = 0; b < 6 && !verified; ++b) {
            Policy c = p;
            c.score_floor = score_floors[a];
            c.history_floor = history_floors[b];
            bool all = true;
            for (std::size_t q = 0; q < probes.size() && all; ++q) {
                Summary got = run_policy(probes[q].net, tab, c);
                const Summary &want = probes[q].summary;
                if (got.verdict != want.verdict) all = false;
                else if (got.accepted != want.accepted) all = false;
                else if (got.rejected != want.rejected) all = false;
                else if (got.derivative_evals != want.derivative_evals) all = false;
                else if (std::fabs(got.stop_time - want.stop_time) >
                         1e-12 * std::max(1.0, std::fabs(want.stop_time)))
                    all = false;
            }
            if (all) {
                best = c;
                verified = true;
            }
        }
    }
    if (!verified) {
        std::fprintf(stderr, "the recovered protocol does not replay the calibration suite\n");
        return 6;
    }

    std::vector<std::string> files;
    DIR *d = opendir(dir.c_str());
    if (d == nullptr) {
        std::fprintf(stderr, "cannot read network directory: %s\n", dir.c_str());
        return 3;
    }
    struct dirent *ent;
    while ((ent = readdir(d)) != nullptr) {
        const std::string nm = ent->d_name;
        if (nm.size() > 4 && nm.compare(nm.size() - 4, 4, ".net") == 0) files.push_back(nm);
    }
    closedir(d);
    std::sort(files.begin(), files.end());

    FILE *out = std::fopen(out_path.c_str(), "w");
    if (out == nullptr) return 3;
    for (std::size_t i = 0; i < files.size(); ++i) {
        Network net;
        if (!load_network(dir + "/" + files[i], net)) continue;
        Summary res = run_policy(net, tab, best);
        std::fprintf(out,
                     "{\"network\": \"%s\", \"verdict\": \"%s\", \"stop_time\": %.17g, "
                     "\"accepted\": %ld, \"rejected\": %ld, \"derivative_evals\": %ld, "
                     "\"final\": {",
                     net.name.c_str(), res.verdict.c_str(), res.stop_time, res.accepted,
                     res.rejected, res.derivative_evals);
        for (std::size_t s = 0; s < net.species.size(); ++s) {
            if (s) std::fprintf(out, ", ");
            std::fprintf(out, "\"%s\": %.17g", net.species[s].c_str(), res.final_state[s]);
        }
        std::fprintf(out, "}}\n");
    }
    std::fclose(out);
    return 0;
}
CPP_EOF

g++ -O2 -std=c++17 -ffp-contract=off -fno-fast-math -o /app/bin/integrate "$SRC"
chmod +x /app/bin/integrate

/app/bin/integrate /app/assay "$BUILD"/assay_check.jsonl
echo "protocol recovered and replayed against the calibration suite"
head -n 1 "$BUILD"/assay_check.jsonl
