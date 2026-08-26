#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
using namespace std;

static const int NEG = -1000000000;

struct Action {
    string kind = "none";
    int a = -1;
    int b = -1;
};

struct ParamRec {
    string key;
    int value;
};

struct PairRec {
    string pair;
    int value;
};

struct MotifRec {
    string motif;
    int bonus;
};

struct StackRec {
    string outer;
    string inner;
    int bonus;
};

struct CoaxRec {
    string left;
    string right;
    int phase;
    int bonus;
};

struct ShapeRec {
    string left;
    string right;
    int phase;
    int mod;
    int bonus;
};

struct SpliceRec {
    string left;
    string right;
    int phase;
    int mod;
    int bonus;
};

struct ContextRec {
    string pair;
    int mod;
    int bonus;
};

struct ChannelRec {
    string name;
    int pair_weight;
    int unpair_weight;
};

struct LaneRec {
    string name;
    int mode;
    int weight;
};

struct ReactRec {
    string channel;
    int index;
    int value;
};

struct GuideRec {
    string channel;
    int i;
    int j;
    int value;
};

struct Params {
    int min_loop = 3;
    int max_internal = 9;
    int hairpin_base = 7;
    int hairpin_slope = 2;
    int stack_base = 5;
    int reg_penalty = 2;
    int internal_penalty = 3;
    int asym_penalty = 1;
    int split_penalty = 0;
    int ml_close = 11;
    int ml_branch = 6;
    int ml_unpaired = 1;
    int terminal_seed = 19;

    vector<ParamRec> param_recs;
    vector<PairRec> pair_recs;
    vector<MotifRec> motifs;
    vector<StackRec> stack_recs;
    vector<CoaxRec> coax_recs;
    vector<ShapeRec> shape_recs;
    vector<SpliceRec> splice_recs;
    vector<ContextRec> context_recs;
    vector<ChannelRec> channel_recs;
    vector<LaneRec> lane_recs;

    map<string, int> pair_score;
    map<string, int> stack_bonus;
    map<string, int> coax_bonus;
    map<string, int> shape_bonus;
    map<string, int> splice_bonus;
    map<string, int> context_bonus;
    map<string, pair<int, int>> channel_weights;
    map<string, pair<int, int>> lane_info;
    int probe_salt = 0;
    int guide_salt = 0;
};

static string app_path(const string &rel) {
    const char *root = getenv("APP_DIR");
    return string(root ? root : "/app") + "/" + rel;
}

static int base36(const string &tok) {
    int value = 0;
    for (char c : tok) {
        int d = 0;
        if ('0' <= c && c <= '9') d = c - '0';
        else if ('A' <= c && c <= 'Z') d = c - 'A' + 10;
        else if ('a' <= c && c <= 'z') d = c - 'a' + 10;
        value = value * 36 + d;
    }
    return value;
}

static int hex_value(const string &tok) {
    int value = 0;
    for (char c : tok) {
        int d = 0;
        if ('0' <= c && c <= '9') d = c - '0';
        else if ('A' <= c && c <= 'F') d = c - 'A' + 10;
        else if ('a' <= c && c <= 'f') d = c - 'a' + 10;
        value = value * 16 + d;
    }
    return value;
}

static int base_idx(char c) {
    if (c == 'A') return 0;
    if (c == 'C') return 1;
    if (c == 'G') return 2;
    return 3;
}

static char idx_base(int x) {
    static const string bases = "ACGU";
    x %= 4;
    if (x < 0) x += 4;
    return bases[x];
}

static string key2(const string &a, const string &b) {
    return a + "/" + b;
}

static string key3(const string &a, const string &b, int phase) {
    return a + "/" + b + "/" + to_string(phase);
}

static string key4(const string &a, const string &b, int phase, int mod) {
    return a + "/" + b + "/" + to_string(phase) + "/" + to_string(mod);
}

static string key_context(const string &pair, int mod) {
    return pair + "/" + to_string(mod);
}

static void set_param(Params &p, const string &key, int value) {
    if (key == "min_loop") p.min_loop = value;
    else if (key == "max_internal") p.max_internal = value;
    else if (key == "hairpin_base") p.hairpin_base = value;
    else if (key == "hairpin_slope") p.hairpin_slope = value;
    else if (key == "stack_base") p.stack_base = value;
    else if (key == "reg_penalty") p.reg_penalty = value;
    else if (key == "internal_penalty") p.internal_penalty = value;
    else if (key == "asym_penalty") p.asym_penalty = value;
    else if (key == "split_penalty") p.split_penalty = value;
    else if (key == "ml_close") p.ml_close = value;
    else if (key == "ml_branch") p.ml_branch = value;
    else if (key == "ml_unpaired") p.ml_unpaired = value;
    else if (key == "terminal_seed") p.terminal_seed = value;
}

static Params read_params() {
    Params p;
    {
        ifstream in(app_path("thermo/loops.tbl"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
            } else if (tag == "param") {
                string key, tok;
                in >> key >> tok;
                int value = (base36(tok) ^ salt) - 128;
                p.param_recs.push_back({key, value});
                set_param(p, key, value);
            }
        }
    }
    {
        ifstream in(app_path("thermo/pairs.tbl"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
            } else if (tag == "pair") {
                string pair, tok;
                in >> pair >> tok;
                int mask = (pair[0] * 17 + pair[1] * 31 + salt) & 255;
                int value = (base36(tok) ^ mask) - 64;
                p.pair_recs.push_back({pair, value});
                p.pair_score[pair] = value;
            }
        }
    }
    {
        ifstream in(app_path("thermo/motif.pack"));
        string line;
        while (getline(in, line)) {
            if (line.empty() || line[0] == '#') continue;
            stringstream ss(line);
            string tag, name, encoded, hexv;
            int seed = 0;
            ss >> tag >> name >> seed >> encoded >> hexv;
            if (tag != "motif") continue;
            string motif;
            for (int i = 0; i < (int)encoded.size(); i++) {
                motif.push_back(idx_base(base_idx(encoded[i]) - seed - 3 * i));
            }
            int raw = hex_value(hexv);
            int bonus = (raw ^ (((int)motif.size() * 29 + seed * 7) & 255)) - 64;
            p.motifs.push_back({motif, bonus});
        }
    }
    {
        ifstream in(app_path("thermo/stack.pack"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
            } else if (tag == "stack") {
                string outer, inner, tok;
                in >> outer >> inner >> tok;
                int sum = 0;
                for (char c : outer + inner) sum += c;
                int mask = (sum * 5 + salt) & 255;
                int value = (base36(tok) ^ mask) - 40;
                p.stack_recs.push_back({outer, inner, value});
                p.stack_bonus[key2(outer, inner)] = value;
            }
        }
    }
    {
        ifstream in(app_path("thermo/coax.pack"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
            } else if (tag == "coax") {
                string left, right, tok;
                int phase;
                in >> left >> right >> phase >> tok;
                int sum = 0;
                for (char c : left + right) sum += c;
                int mask = (sum + 37 * phase + salt) & 255;
                int value = (base36(tok) ^ mask) - 48;
                p.coax_recs.push_back({left, right, phase, value});
                p.coax_bonus[key3(left, right, phase)] = value;
            }
        }
    }
    {
        ifstream in(app_path("thermo/shape.pack"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
            } else if (tag == "shape") {
                string left, right, tok;
                int phase, mod;
                in >> left >> right >> phase >> mod >> tok;
                int sum = 0;
                for (char c : left + right) sum += c;
                int mask = (sum + 41 * phase + 17 * mod + salt) & 255;
                int value = (base36(tok) ^ mask) - 36;
                p.shape_recs.push_back({left, right, phase, mod, value});
                p.shape_bonus[key4(left, right, phase, mod)] = value;
            }
        }
    }
    {
        ifstream in(app_path("thermo/splice.pack"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
            } else if (tag == "splice") {
                string left, right, tok;
                int phase, mod;
                in >> left >> right >> phase >> mod >> tok;
                auto cx = p.coax_bonus.find(key3(left, right, phase));
                auto sh = p.shape_bonus.find(key4(left, right, phase, mod));
                if (cx == p.coax_bonus.end() || sh == p.shape_bonus.end()) continue;
                int sum = 0;
                for (char c : left + right) sum += c;
                int mask = (sum + 43 * phase + 19 * mod + salt
                    + ((cx->second + 96) & 255) + ((sh->second + 96) & 255)) & 255;
                int value = (base36(tok) ^ mask) - 44;
                p.splice_recs.push_back({left, right, phase, mod, value});
                p.splice_bonus[key4(left, right, phase, mod)] = value;
            }
        }
    }
    {
        ifstream in(app_path("thermo/context.pack"));
        string tag;
        int salt = 0;
        int carry = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
                carry = salt;
            } else if (tag == "context") {
                string pair, tok;
                int mod;
                in >> pair >> mod >> tok;
                int mask = (pair[0] * 11 + pair[1] * 13 + 23 * mod + salt + carry) & 255;
                int value = (base36(tok) ^ mask) - 50;
                carry = (carry * 3 + value + 257) & 255;
                p.context_recs.push_back({pair, mod, value});
                p.context_bonus[key_context(pair, mod)] = value;
            }
        }
    }
    {
        ifstream in(app_path("thermo/probe.pack"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
                p.probe_salt = salt;
            } else if (tag == "channel") {
                string ch, pair_tok, unpair_tok;
                in >> ch >> pair_tok >> unpair_tok;
                int sum = 0;
                for (char c : ch) sum += c;
                int pair_weight = (base36(pair_tok) ^ ((sum * 13 + salt) & 255)) - 32;
                int unpair_weight = (base36(unpair_tok) ^ ((sum * 17 + salt) & 255)) - 32;
                p.channel_recs.push_back({ch, pair_weight, unpair_weight});
                p.channel_weights[ch] = {pair_weight, unpair_weight};
            }
        }
    }
    {
        ifstream in(app_path("thermo/guide.pack"));
        string tag;
        int salt = 0;
        while (in >> tag) {
            if (tag.empty() || tag[0] == '#') {
                string rest;
                getline(in, rest);
                continue;
            }
            if (tag == "salt") {
                in >> salt;
                p.guide_salt = salt;
            } else if (tag == "lane") {
                string ch, mode_tok, weight_tok;
                in >> ch >> mode_tok >> weight_tok;
                int sum = 0;
                for (char c : ch) sum += c;
                int mode = (base36(mode_tok) ^ ((sum * 11 + salt) & 255)) % 4;
                int weight = (base36(weight_tok) ^ ((sum * 17 + 23 * mode + salt) & 255)) - 16;
                p.lane_recs.push_back({ch, mode, weight});
                p.lane_info[ch] = {mode, weight};
            }
        }
    }
    return p;
}

struct Input {
    string name;
    string seq;
    vector<ReactRec> reacts;
    vector<GuideRec> guides;
    vector<pair<int, int>> probes;
};

static Input read_input(const string &path, const Params &p) {
    ifstream in(path);
    if (!in) {
        cerr << "cannot open " << path << "\n";
        exit(2);
    }
    Input x;
    string line;
    while (getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        stringstream ss(line);
        string key;
        ss >> key;
        if (key == "sequence") ss >> x.name >> x.seq;
        else if (key == "react") {
            string ch, tok;
            int idx;
            ss >> ch >> idx >> tok;
            int sum = 0;
            for (char c : ch) sum += c;
            int mask = (idx * 19 + sum * 7 + p.probe_salt) & 255;
            int value = (base36(tok) ^ mask) - 96;
            x.reacts.push_back({ch, idx, value});
        }
        else if (key == "guide") {
            string ch, tok;
            int i, j;
            ss >> ch >> i >> j >> tok;
            int sum = 0;
            for (char c : ch) sum += c;
            int mask = (i * 31 + j * 17 + sum * 5 + p.guide_salt) & 255;
            int value = (base36(tok) ^ mask) - 32;
            x.guides.push_back({ch, i, j, value});
        }
        else if (key == "probe") {
            int i, j;
            ss >> i >> j;
            x.probes.push_back({i, j});
        }
    }
    return x;
}

static string closing_pair(const string &s, int i, int j) {
    string out;
    out.push_back(s[i]);
    out.push_back(s[j]);
    return out;
}

static int score_pair(const Params &p, const string &pair) {
    auto it = p.pair_score.find(pair);
    return it == p.pair_score.end() ? NEG : it->second;
}

static int stack_score(const Params &p, const string &outer, const string &inner) {
    int bonus = 0;
    auto it = p.stack_bonus.find(key2(outer, inner));
    if (it != p.stack_bonus.end()) bonus = it->second;
    return p.stack_base + bonus;
}

static int motif_bonus(const Params &p, const string &loop) {
    int bonus = 0;
    for (const auto &mb : p.motifs) {
        if (loop.find(mb.motif) != string::npos) bonus += mb.bonus;
    }
    return bonus;
}

static int terminal_score(const Params &p, const string &pair, char a, char b) {
    int gc_flag = (pair[0] == 'G' || pair[0] == 'C' || pair[1] == 'G' || pair[1] == 'C') ? 1 : 0;
    return (((base_idx(a) + 1) * 3 + (base_idx(b) + 1) * 5 + gc_flag * 2 + p.terminal_seed) % 7) - 3;
}

static int registered_mod(int i, int k, int j) {
    return ((k - i + 1) * 7 + (j - k) * 3 + i + j) % 4;
}

static bool channel_applies(const string &channel, char base) {
    if (channel == "SH") return true;
    if (channel == "DM") return base == 'A' || base == 'C';
    if (channel == "CM") return base == 'G' || base == 'U';
    return false;
}

static bool lane_applies(int mode, const string &pair) {
    if (mode == 0) return pair == "AU" || pair == "UA" || pair == "GC" || pair == "CG";
    if (mode == 1) return pair == "GU" || pair == "UG";
    if (mode == 2) return pair == "GC" || pair == "CG";
    if (mode == 3) return pair[0] == 'A' || pair[0] == 'G';
    return false;
}

static int printable(int value) {
    return value <= NEG / 2 ? -999999 : value;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        cerr << "usage: fold <rna_file>\n";
        return 1;
    }

    Params par = read_params();
    Input input = read_input(argv[1], par);
    const string &s = input.seq;
    int n = (int)s.size();

    vector<int> paired_ev(n, 0), unpaired_ev(n, 0);
    for (const auto &rec : input.reacts) {
        if (rec.index < 0 || rec.index >= n) continue;
        auto it = par.channel_weights.find(rec.channel);
        if (it == par.channel_weights.end()) continue;
        if (!channel_applies(rec.channel, s[rec.index])) continue;
        paired_ev[rec.index] -= it->second.first * rec.value;
        unpaired_ev[rec.index] += it->second.second * rec.value;
    }
    vector<int> unpaired_prefix(n + 1, 0);
    for (int i = 0; i < n; i++) unpaired_prefix[i + 1] = unpaired_prefix[i] + unpaired_ev[i];
    auto sum_unpaired = [&](int l, int r) -> int {
        if (l > r) return 0;
        l = max(l, 0);
        r = min(r, n - 1);
        if (l > r) return 0;
        return unpaired_prefix[r + 1] - unpaired_prefix[l];
    };

    vector<vector<int>> guide_ev(n, vector<int>(n, 0));
    for (const auto &rec : input.guides) {
        if (rec.i < 0 || rec.j < 0 || rec.i >= n || rec.j >= n || rec.i >= rec.j) continue;
        auto it = par.lane_info.find(rec.channel);
        if (it == par.lane_info.end()) continue;
        string pair = closing_pair(s, rec.i, rec.j);
        if (!lane_applies(it->second.first, pair)) continue;
        guide_ev[rec.i][rec.j] += it->second.second * rec.value;
    }

    vector<vector<int>> F(n, vector<int>(n, 0));
    vector<vector<int>> P(n, vector<int>(n, NEG));
    vector<vector<int>> G(n, vector<int>(n, NEG));
    vector<vector<int>> R(n, vector<int>(n, NEG));
    vector<vector<Action>> actF(n, vector<Action>(n));
    vector<vector<Action>> actP(n, vector<Action>(n));
    vector<vector<Action>> actG(n, vector<Action>(n));
    vector<vector<Action>> actR(n, vector<Action>(n));

    for (int len = 1; len <= n; len++) {
        for (int i = 0; i + len - 1 < n; i++) {
            int j = i + len - 1;
            if (i >= j) {
                F[i][j] = 0;
                continue;
            }

            string outer = closing_pair(s, i, j);
            int ps = score_pair(par, outer);
            if (ps > NEG / 2 && j - i - 1 >= par.min_loop) {
                int context_mod = ((j - i) + 2 * i + 3 * j) % 5;
                int context_value = 0;
                auto ctx = par.context_bonus.find(key_context(outer, context_mod));
                if (ctx != par.context_bonus.end()) context_value = ctx->second;
                int close_score = ps + paired_ev[i] + paired_ev[j] + context_value + guide_ev[i][j];
                int loop_len = j - i - 1;
                string loop = s.substr(i + 1, loop_len);
                P[i][j] = close_score - (par.hairpin_base + par.hairpin_slope * (loop_len - par.min_loop))
                    + terminal_score(par, outer, s[i + 1], s[j - 1])
                    + motif_bonus(par, loop)
                    + sum_unpaired(i + 1, j - 1);
                actP[i][j].kind = "hairpin";

                if (i + 1 < j && P[i + 1][j - 1] > NEG / 2) {
                    string inner = closing_pair(s, i + 1, j - 1);
                    int val = close_score + stack_score(par, outer, inner) + P[i + 1][j - 1];
                    if (val > P[i][j]) {
                        P[i][j] = val;
                        actP[i][j].kind = "stack";
                    }
                }

                for (int a = i + 1; a <= min(j - 2, i + par.max_internal + 1); a++) {
                    for (int b = max(a + 1, j - par.max_internal - 1); b < j; b++) {
                        int left = a - i - 1;
                        int right = j - b - 1;
                        int unpaired = left + right;
                        if (unpaired <= 0 || unpaired > par.max_internal) continue;
                        if (P[a][b] <= NEG / 2) continue;
                        int val = close_score + P[a][b]
                            - par.internal_penalty * unpaired
                            - par.asym_penalty * abs(left - right)
                            + sum_unpaired(i + 1, a - 1)
                            + sum_unpaired(b + 1, j - 1);
                        if (left > 0 && right > 0) {
                            string inner = closing_pair(s, a, b);
                            val += terminal_score(par, outer, s[i + 1], s[j - 1]);
                            val += terminal_score(par, inner, s[a - 1], s[b + 1]);
                        }
                        if (val > P[i][j]) {
                            P[i][j] = val;
                            actP[i][j].kind = "internal";
                            actP[i][j].a = a;
                            actP[i][j].b = b;
                        }
                    }
                }

                if (i + 1 <= j - 1 && G[i + 1][j - 1] > NEG / 2) {
                    int val = close_score - par.ml_close + G[i + 1][j - 1];
                    if (val > P[i][j]) {
                        P[i][j] = val;
                        actP[i][j].kind = "multiloop";
                    }
                }
            }

            for (int k = i; k < j; k++) {
                if (P[i][k] <= NEG / 2 || P[k + 1][j] <= NEG / 2) continue;
                string left_pair = closing_pair(s, i, k);
                string right_pair = closing_pair(s, k + 1, j);
                int phase = ((k - i + 1) + 2 * (j - k)) % 3;
                int mod = registered_mod(i, k, j);
                auto cx = par.coax_bonus.find(key3(left_pair, right_pair, phase));
                auto sh = par.shape_bonus.find(key4(left_pair, right_pair, phase, mod));
                auto sp = par.splice_bonus.find(key4(left_pair, right_pair, phase, mod));
                if (cx == par.coax_bonus.end() || sh == par.shape_bonus.end()
                    || sp == par.splice_bonus.end()) continue;
                int val = P[i][k] + P[k + 1][j] - 2 * par.ml_branch
                    - par.reg_penalty + cx->second + sh->second + sp->second;
                if (val > R[i][j]) {
                    R[i][j] = val;
                    actR[i][j].kind = "registered";
                    actR[i][j].a = k;
                }
            }

            if (P[i][j] > NEG / 2) {
                G[i][j] = P[i][j] - par.ml_branch;
                actG[i][j].kind = "branch";
            }
            if (i + 1 <= j && G[i + 1][j] > NEG / 2) {
                int val = unpaired_ev[i] + G[i + 1][j] - par.ml_unpaired;
                if (val > G[i][j]) {
                    G[i][j] = val;
                    actG[i][j].kind = "left";
                }
            }
            if (i <= j - 1 && G[i][j - 1] > NEG / 2) {
                int val = unpaired_ev[j] + G[i][j - 1] - par.ml_unpaired;
                if (val > G[i][j]) {
                    G[i][j] = val;
                    actG[i][j].kind = "right";
                }
            }
            if (R[i][j] > NEG / 2) {
                int val = R[i][j];
                if (val > G[i][j]) {
                    G[i][j] = val;
                    actG[i][j].kind = "registered";
                }
            }
            for (int k = i; k < j; k++) {
                if (P[i][k] <= NEG / 2 || P[k + 1][j] <= NEG / 2) continue;
                string left_pair = closing_pair(s, i, k);
                string right_pair = closing_pair(s, k + 1, j);
                int phase = ((k - i + 1) + 2 * (j - k)) % 3;
                auto it = par.coax_bonus.find(key3(left_pair, right_pair, phase));
                if (it == par.coax_bonus.end()) continue;
                int val = P[i][k] + P[k + 1][j] - 2 * par.ml_branch + it->second;
                if (val > G[i][j]) {
                    G[i][j] = val;
                    actG[i][j].kind = "coax";
                    actG[i][j].a = k;
                }
            }
            for (int k = i; k < j; k++) {
                if (G[i][k] <= NEG / 2 || G[k + 1][j] <= NEG / 2) continue;
                int val = G[i][k] + G[k + 1][j];
                if (val > G[i][j]) {
                    G[i][j] = val;
                    actG[i][j].kind = "split";
                    actG[i][j].a = k;
                }
            }

            int best = 0;
            Action best_act;
            if (P[i][j] > best) {
                best = P[i][j];
                best_act.kind = "pair";
            }
            if (unpaired_ev[i] + F[i + 1][j] > best) {
                best = unpaired_ev[i] + F[i + 1][j];
                best_act.kind = "left";
            }
            if (unpaired_ev[j] + F[i][j - 1] > best) {
                best = unpaired_ev[j] + F[i][j - 1];
                best_act.kind = "right";
            }
            for (int k = i; k < j; k++) {
                int val = F[i][k] + F[k + 1][j] - par.split_penalty;
                if (val > best) {
                    best = val;
                    best_act.kind = "split";
                    best_act.a = k;
                }
            }
            F[i][j] = best;
            actF[i][j] = best_act;
        }
    }

    vector<pair<int, int>> pairs;
    function<void(int, int)> traceP;
    function<void(int, int)> traceG;
    function<void(int, int)> traceR;
    function<void(int, int)> traceF;

    traceP = [&](int i, int j) -> void {
        if (i < 0 || j < 0 || i >= n || j >= n || i >= j) return;
        if (P[i][j] <= NEG / 2) return;
        pairs.push_back({i, j});
        const Action &a = actP[i][j];
        if (a.kind == "stack") {
            traceP(i + 1, j - 1);
        } else if (a.kind == "internal") {
            traceP(a.a, a.b);
        } else if (a.kind == "multiloop") {
            traceG(i + 1, j - 1);
        }
    };
    traceR = [&](int i, int j) -> void {
        if (i < 0 || j < 0 || i >= n || j >= n || i >= j) return;
        if (R[i][j] <= NEG / 2) return;
        const Action &a = actR[i][j];
        if (a.kind == "registered") {
            traceP(i, a.a);
            traceP(a.a + 1, j);
        }
    };
    traceG = [&](int i, int j) -> void {
        if (i < 0 || j < 0 || i >= n || j >= n || i >= j) return;
        if (G[i][j] <= NEG / 2) return;
        const Action &a = actG[i][j];
        if (a.kind == "branch") {
            traceP(i, j);
        } else if (a.kind == "left") {
            traceG(i + 1, j);
        } else if (a.kind == "right") {
            traceG(i, j - 1);
        } else if (a.kind == "registered") {
            traceR(i, j);
        } else if (a.kind == "coax") {
            traceP(i, a.a);
            traceP(a.a + 1, j);
        } else if (a.kind == "split") {
            traceG(i, a.a);
            traceG(a.a + 1, j);
        }
    };
    traceF = [&](int i, int j) -> void {
        if (i < 0 || j < 0 || i >= n || j >= n || i >= j) return;
        const Action &a = actF[i][j];
        if (a.kind == "pair") {
            traceP(i, j);
        } else if (a.kind == "left") {
            traceF(i + 1, j);
        } else if (a.kind == "right") {
            traceF(i, j - 1);
        } else if (a.kind == "split") {
            traceF(i, a.a);
            traceF(a.a + 1, j);
        }
    };
    if (n > 0) traceF(0, n - 1);

    sort(pairs.begin(), pairs.end());
    string dot(n, '.');
    for (auto [i, j] : pairs) {
        dot[i] = '(';
        dot[j] = ')';
    }

    for (const auto &rec : par.pair_recs) {
        cout << "pairscore " << rec.pair << " " << rec.value << "\n";
    }
    for (const auto &rec : par.param_recs) {
        cout << "param " << rec.key << " " << rec.value << "\n";
    }
    for (const auto &rec : par.motifs) {
        cout << "motif " << rec.motif << " " << rec.bonus << "\n";
    }
    for (const auto &rec : par.stack_recs) {
        cout << "stack " << rec.outer << " " << rec.inner << " " << rec.bonus << "\n";
    }
    for (const auto &rec : par.coax_recs) {
        cout << "coax " << rec.left << " " << rec.right << " " << rec.phase << " " << rec.bonus << "\n";
    }
    for (const auto &rec : par.shape_recs) {
        cout << "shape " << rec.left << " " << rec.right << " " << rec.phase << " "
             << rec.mod << " " << rec.bonus << "\n";
    }
    for (const auto &rec : par.splice_recs) {
        cout << "splice " << rec.left << " " << rec.right << " " << rec.phase << " "
             << rec.mod << " " << rec.bonus << "\n";
    }
    for (const auto &rec : par.context_recs) {
        cout << "context " << rec.pair << " " << rec.mod << " " << rec.bonus << "\n";
    }
    for (const auto &rec : par.channel_recs) {
        cout << "channel " << rec.name << " " << rec.pair_weight << " " << rec.unpair_weight << "\n";
    }
    for (const auto &rec : par.lane_recs) {
        cout << "lane " << rec.name << " " << rec.mode << " " << rec.weight << "\n";
    }
    for (const auto &rec : input.reacts) {
        cout << "react " << rec.channel << " " << rec.index << " " << rec.value << "\n";
    }
    for (const auto &rec : input.guides) {
        cout << "guide " << rec.channel << " " << rec.i << " " << rec.j << " " << rec.value << "\n";
    }
    for (auto [i, j] : input.probes) {
        int fv = (0 <= i && i < n && 0 <= j && j < n && i <= j) ? F[i][j] : 0;
        int pv = (0 <= i && i < n && 0 <= j && j < n && i <= j) ? P[i][j] : NEG;
        int gv = (0 <= i && i < n && 0 <= j && j < n && i <= j) ? G[i][j] : NEG;
        int rv = (0 <= i && i < n && 0 <= j && j < n && i <= j) ? R[i][j] : NEG;
        cout << "trace " << i << " " << j << " " << fv << " " << printable(pv) << " "
             << printable(gv) << " " << printable(rv) << "\n";
    }
    for (auto [i, j] : pairs) {
        cout << "pair " << i << " " << j << "\n";
    }
    cout << "score " << (n ? F[0][n - 1] : 0) << "\n";
    cout << "dotbracket " << dot << "\n";
    return 0;
}
