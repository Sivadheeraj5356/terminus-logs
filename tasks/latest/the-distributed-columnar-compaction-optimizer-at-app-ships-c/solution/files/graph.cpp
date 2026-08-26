#include "graph.h"
#include "row_overlap.h"
#include <map>
#include <set>

static const Fragment* find_frag(const std::vector<Fragment>& frags, uint16_t id) {
    for (const auto& f : frags) {
        if (f.id == id) return &f;
    }
    return nullptr;
}

std::optional<EdgeChoice> select_outgoing_edge(uint16_t from_id, const std::vector<Fragment>& frags, const Policy& policy) {
    const Fragment* from = find_frag(frags, from_id);
    if (!from) return std::nullopt;
    std::optional<EdgeChoice> best;
    for (const auto& cand : frags) {
        if (cand.id == from_id) continue;
        int ov = row_junction_overlap(*from, cand, policy.min_row_overlap, policy.case_fold_ascii);
        if (ov == 0) continue;
        EdgeChoice edge{from_id, cand.id, ov};
        if (!best.has_value()) { best = edge; continue; }
        if (edge.overlap > best->overlap) {
            best = edge;
        } else if (edge.overlap == best->overlap) {
            const Fragment* bto = find_frag(frags, best->to);
            if (cand.seq < bto->seq || (cand.seq == bto->seq && cand.id < bto->id)) {
                best = edge;
            }
        }
    }
    return best;
}

std::optional<uint16_t> resolve_open_fragment(const std::vector<Fragment>& fragments, const Policy& policy) {
    std::set<uint16_t> has_incoming;
    for (const auto& a : fragments) {
        for (const auto& b : fragments) {
            if (a.id == b.id) continue;
            if (row_junction_overlap(a, b, policy.min_row_overlap, policy.case_fold_ascii) > 0) {
                has_incoming.insert(b.id);
            }
        }
    }
    std::vector<const Fragment*> anchors;
    for (const auto& f : fragments) {
        if ((f.flags & 1) != 0) anchors.push_back(&f);
    }
    auto pick = [](const std::vector<const Fragment*>& cands) -> std::optional<uint16_t> {
        if (cands.empty()) return std::nullopt;
        const Fragment* best = cands[0];
        for (const Fragment* f : cands) {
            if (f->seq < best->seq || (f->seq == best->seq && f->id < best->id)) best = f;
        }
        return best->id;
    };
    if (!anchors.empty()) return pick(anchors);
    std::vector<const Fragment*> no_in;
    for (const auto& f : fragments) {
        if (has_incoming.count(f.id) == 0) no_in.push_back(&f);
    }
    if (!no_in.empty()) return pick(no_in);
    std::vector<const Fragment*> all;
    for (const auto& f : fragments) all.push_back(&f);
    return pick(all);
}

std::vector<EdgeChoice> trace_edge_path(const std::vector<Fragment>& fragments, const Policy& policy) {
    std::vector<EdgeChoice> chain;
    auto start = resolve_open_fragment(fragments, policy);
    if (!start.has_value()) return chain;
    std::set<uint16_t> used;
    uint16_t cur = *start;
    used.insert(cur);
    while (true) {
        auto nxt = select_outgoing_edge(cur, fragments, policy);
        if (!nxt.has_value() || used.count(nxt->to) != 0) break;
        chain.push_back(*nxt);
        used.insert(nxt->to);
        cur = nxt->to;
    }
    return chain;
}
