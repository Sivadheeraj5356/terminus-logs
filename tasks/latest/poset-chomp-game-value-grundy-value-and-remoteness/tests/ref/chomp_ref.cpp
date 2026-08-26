// Independent reference solver for the poset-Chomp task.
//
// It reads one position ("n m" then m cover edges "a b") and prints "V C G R".
// The default build computes the correct answer under the normal poison-loss
// convention. Compile-time flags select deliberately wrong variants used by the
// grader to prove the disclosed obligations are load-bearing:
//
//   -DNORMAL_TERMINAL   : the poison is an ordinary eatable cell and the empty
//                         ideal is the terminal position (normal-play Chomp
//                         with no poison penalty).
//   -DWINLOSS_GRUNDY    : report the Grundy value collapsed to 0/1 (loss/win)
//                         instead of the true mex.
//   -DNAIVE_REMOTENESS  : report remoteness as the shortest distance to a
//                         terminal, ignoring the parity-aware optimal play.
//
// This source is verifier-only and is never shipped in the agent image. It is
// an independent re-implementation of the same contract computed by the Python
// fixture generator, so the two cross-check each other.
//
// Positions may have more than 64 elements (up to 128), so an ideal is stored
// as a 128-bit mask (unsigned __int128) rather than a machine word, and the
// retrograde memoises only the reachable order ideals keyed by that mask.

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <utility>
#include <vector>

using u128 = unsigned __int128;

static int N;
static std::vector<u128> UP;  // UP[x] = mask {y : y >= x}, includes x

struct U128Hash {
    std::size_t operator()(u128 x) const noexcept {
        std::uint64_t lo = static_cast<std::uint64_t>(x);
        std::uint64_t hi = static_cast<std::uint64_t>(x >> 64);
        std::size_t h = std::hash<std::uint64_t>()(lo);
        h ^= std::hash<std::uint64_t>()(hi) + 0x9e3779b97f4a7c15ULL + (h << 6) +
             (h >> 2);
        return h;
    }
};

static inline u128 bit(int i) { return (static_cast<u128>(1) << i); }

static void build_closure(const std::vector<std::pair<int, int>> &covers) {
    // ge[a] = mask of elements b with a <= b, via transitive closure of covers.
    std::vector<u128> ge(N, 0);
    for (int a = 0; a < N; ++a) ge[a] = bit(a);
    for (auto &e : covers) ge[e.first] |= bit(e.second);
    bool changed = true;
    while (changed) {
        changed = false;
        for (int a = 0; a < N; ++a) {
            u128 m = ge[a];
            u128 add = 0;
            for (int b = 0; b < N; ++b)
                if ((m >> b) & 1) add |= ge[b];
            if ((m | add) != m) {
                ge[a] = m | add;
                changed = true;
            }
        }
    }
    UP.assign(N, 0);
    for (int x = 0; x < N; ++x) UP[x] = ge[x];
}

// ---- correct semantics ----------------------------------------------------
static std::unordered_map<u128, int, U128Hash> g_grundy;
static std::unordered_map<u128, int, U128Hash> g_rem;

static int grundy(u128 S) {
    auto it = g_grundy.find(S);
    if (it != g_grundy.end()) return it->second;
    std::vector<int> vals;
    for (int x = 1; x < N; ++x) {  // element 0 is the poison, never a move
        if (!((S >> x) & 1)) continue;
        vals.push_back(grundy(S & ~UP[x]));
    }
    int mex = 0;
    std::sort(vals.begin(), vals.end());
    for (int v : vals) {
        if (v == mex) ++mex;
        else if (v > mex) break;
    }
    g_grundy[S] = mex;
    return mex;
}

static int remoteness(u128 S) {
    auto it = g_rem.find(S);
    if (it != g_rem.end()) return it->second;
    std::vector<int> rs;
    for (int x = 1; x < N; ++x) {
        if (!((S >> x) & 1)) continue;
        rs.push_back(remoteness(S & ~UP[x]));
    }
    int val;
    if (rs.empty()) {
        val = 0;
    } else {
        int best_even = -1, best_odd = -1;
        for (int r : rs) {
            if (r % 2 == 0) best_even = (best_even < 0) ? r : std::min(best_even, r);
            else best_odd = std::max(best_odd, r);
        }
        if (best_even >= 0) val = 1 + best_even;
        else val = 1 + best_odd;
    }
    g_rem[S] = val;
    return val;
}

// ---- NORMAL_TERMINAL wrong semantics --------------------------------------
static std::unordered_map<u128, int, U128Hash> nt_grundy;
static std::unordered_map<u128, int, U128Hash> nt_rem;

static int grundy_nt(u128 S) {
    auto it = nt_grundy.find(S);
    if (it != nt_grundy.end()) return it->second;
    std::vector<int> vals;
    for (int x = 0; x < N; ++x) {  // every present cell is eatable, incl. poison
        if (!((S >> x) & 1)) continue;
        vals.push_back(grundy_nt(S & ~UP[x]));
    }
    int mex = 0;
    std::sort(vals.begin(), vals.end());
    for (int v : vals) {
        if (v == mex) ++mex;
        else if (v > mex) break;
    }
    nt_grundy[S] = mex;
    return mex;
}

static int remoteness_nt(u128 S) {
    auto it = nt_rem.find(S);
    if (it != nt_rem.end()) return it->second;
    std::vector<int> rs;
    for (int x = 0; x < N; ++x) {
        if (!((S >> x) & 1)) continue;
        rs.push_back(remoteness_nt(S & ~UP[x]));
    }
    int val;
    if (rs.empty()) {
        val = 0;
    } else {
        int best_even = -1, best_odd = -1;
        for (int r : rs) {
            if (r % 2 == 0) best_even = (best_even < 0) ? r : std::min(best_even, r);
            else best_odd = std::max(best_odd, r);
        }
        if (best_even >= 0) val = 1 + best_even;
        else val = 1 + best_odd;
    }
    nt_rem[S] = val;
    return val;
}

// ---- NAIVE_REMOTENESS wrong semantics -------------------------------------
static std::unordered_map<u128, int, U128Hash> nr_rem;

static int remoteness_naive(u128 S) {
    auto it = nr_rem.find(S);
    if (it != nr_rem.end()) return it->second;
    int best = -1;
    for (int x = 1; x < N; ++x) {
        if (!((S >> x) & 1)) continue;
        int r = remoteness_naive(S & ~UP[x]);
        best = (best < 0) ? r : std::min(best, r);
    }
    int val = (best < 0) ? 0 : 1 + best;
    nr_rem[S] = val;
    return val;
}

int main() {
    int m = 0;
    if (!(std::cin >> N >> m)) return 0;
    std::vector<std::pair<int, int>> covers;
    for (int e = 0; e < m; ++e) {
        int a = 0, b = 0;
        if (!(std::cin >> a >> b)) return 0;
        covers.emplace_back(a, b);
    }
    build_closure(covers);
    u128 full = 0;
    for (int x = 0; x < N; ++x) full |= bit(x);

#if defined(NORMAL_TERMINAL)
    int g = grundy_nt(full);
    int r = remoteness_nt(full);
    int c = 0;
    for (int x = 1; x < N; ++x)
        if (((full >> x) & 1) && grundy_nt(full & ~UP[x]) == 0) ++c;
    std::cout << (g > 0 ? "N " : "P ") << c << " " << g << " " << r << "\n";
#elif defined(WINLOSS_GRUNDY)
    int g = grundy(full);
    int r = remoteness(full);
    int c = 0;
    for (int x = 1; x < N; ++x)
        if (((full >> x) & 1) && grundy(full & ~UP[x]) == 0) ++c;
    int g01 = (g > 0) ? 1 : 0;  // wrong: collapse mex to a win/loss bit
    std::cout << (g > 0 ? "N " : "P ") << c << " " << g01 << " " << r << "\n";
#elif defined(NAIVE_REMOTENESS)
    int g = grundy(full);
    int r = remoteness_naive(full);  // wrong: shortest path, no parity
    int c = 0;
    for (int x = 1; x < N; ++x)
        if (((full >> x) & 1) && grundy(full & ~UP[x]) == 0) ++c;
    std::cout << (g > 0 ? "N " : "P ") << c << " " << g << " " << r << "\n";
#else
    int g = grundy(full);
    int r = remoteness(full);
    int c = 0;
    for (int x = 1; x < N; ++x)
        if (((full >> x) & 1) && grundy(full & ~UP[x]) == 0) ++c;
    std::cout << (g > 0 ? "N " : "P ") << c << " " << g << " " << r << "\n";
#endif
    return 0;
}
