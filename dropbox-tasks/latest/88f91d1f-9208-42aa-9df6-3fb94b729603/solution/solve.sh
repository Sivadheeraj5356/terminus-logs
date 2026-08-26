#!/bin/bash
set -euo pipefail

cat > /app/src/chomp.cpp <<'EOF'
#include "chomp.hpp"

#include <algorithm>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace {

// A position may have more than 64 elements, so an ideal is a 128-bit mask
// (unsigned __int128), not a machine word, and the retrograde memoises only the
// reachable order ideals keyed by that mask.
using u128 = unsigned __int128;

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

inline u128 bit(int i) { return (static_cast<u128>(1) << i); }

int g_n;
std::vector<u128> g_up;  // g_up[x] = mask {y : y >= x}
std::unordered_map<u128, int, U128Hash> g_grundy;
std::unordered_map<u128, int, U128Hash> g_rem;

void build_closure(const PosetPosition &pos) {
    g_n = pos.n;
    std::vector<u128> ge(g_n, 0);
    for (int a = 0; a < g_n; ++a) ge[a] = bit(a);
    for (const auto &e : pos.covers) ge[e.first] |= bit(e.second);
    bool changed = true;
    while (changed) {
        changed = false;
        for (int a = 0; a < g_n; ++a) {
            u128 add = 0;
            for (int b = 0; b < g_n; ++b)
                if ((ge[a] >> b) & 1) add |= ge[b];
            if ((ge[a] | add) != ge[a]) {
                ge[a] |= add;
                changed = true;
            }
        }
    }
    g_up = ge;
}

int grundy(u128 S) {
    auto it = g_grundy.find(S);
    if (it != g_grundy.end()) return it->second;
    std::vector<int> vals;
    for (int x = 1; x < g_n; ++x) {  // element 0 is the poison, never a move
        if (!((S >> x) & 1)) continue;
        vals.push_back(grundy(S & ~g_up[x]));
    }
    std::sort(vals.begin(), vals.end());
    int mex = 0;
    for (int v : vals) {
        if (v == mex) ++mex;
        else if (v > mex) break;
    }
    g_grundy[S] = mex;
    return mex;
}

int remoteness(u128 S) {
    auto it = g_rem.find(S);
    if (it != g_rem.end()) return it->second;
    int best_even = -1, best_odd = -1;
    bool any = false;
    for (int x = 1; x < g_n; ++x) {
        if (!((S >> x) & 1)) continue;
        any = true;
        int r = remoteness(S & ~g_up[x]);
        if (r % 2 == 0) best_even = (best_even < 0) ? r : std::min(best_even, r);
        else best_odd = std::max(best_odd, r);
    }
    int val;
    if (!any) val = 0;
    else if (best_even >= 0) val = 1 + best_even;
    else val = 1 + best_odd;
    g_rem[S] = val;
    return val;
}

}  // namespace

std::string solve(const PosetPosition &pos) {
    g_grundy.clear();
    g_rem.clear();
    build_closure(pos);
    u128 full = 0;
    for (int x = 0; x < g_n; ++x) full |= bit(x);
    int g = grundy(full);
    int r = remoteness(full);
    int c = 0;
    for (int x = 1; x < g_n; ++x)
        if (((full >> x) & 1) && grundy(full & ~g_up[x]) == 0) ++c;
    std::string v = (g > 0) ? "N" : "P";
    return v + " " + std::to_string(c) + " " + std::to_string(g) + " " +
           std::to_string(r);
}
EOF

cd /app
make
echo "example_1 (antichain of 4 above poison):"
printf '5 4\n0 1\n0 2\n0 3\n0 4\n' | ./chomp
echo "example_2 (single element above poison):"
printf '2 1\n0 1\n' | ./chomp
echo "grid 9x9 (2D Chomp, 81 cells > 64):"
printf '81 144\n' > /tmp/g99.txt
python3 - <<'PY' >> /tmp/g99.txt
a=b=9
lines=[]
for i in range(a):
    for j in range(b):
        cur=i*b+j
        if i+1<a: lines.append(f"{cur} {(i+1)*b+j}")
        if j+1<b: lines.append(f"{cur} {i*b+j+1}")
print("\n".join(lines))
PY
./chomp < /tmp/g99.txt
