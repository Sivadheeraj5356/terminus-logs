#include "ingest_chain.h"
#include "row_overlap.h"
#include <set>

static const Fragment* find_frag(const std::vector<Fragment>& frags, uint16_t id) {
    for (const auto& f : frags) {
        if (f.id == id) return &f;
    }
    return nullptr;
}

static std::optional<uint16_t> anchor_preferred_id(const std::vector<const Fragment*>& cands) {
    if (cands.empty()) return std::nullopt;
    const Fragment* best = cands[0];
    for (const Fragment* f : cands) {
        if (f->seq < best->seq || (f->seq == best->seq && f->id < best->id)) best = f;
    }
    return best->id;
}

static std::optional<uint16_t> resolve_ingest_open(const std::vector<Fragment>& fragments, const Policy& policy) {
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
    if (!anchors.empty()) return anchor_preferred_id(anchors);
    std::vector<const Fragment*> no_in;
    for (const auto& f : fragments) {
        if (has_incoming.count(f.id) == 0) no_in.push_back(&f);
    }
    if (!no_in.empty()) return anchor_preferred_id(no_in);
    std::vector<const Fragment*> all;
    for (const auto& f : fragments) all.push_back(&f);
    return anchor_preferred_id(all);
}

static std::optional<std::pair<uint16_t, int>> select_ingest_edge(
    uint16_t from_id, const std::vector<Fragment>& frags, const Policy& policy) {
    const Fragment* from = find_frag(frags, from_id);
    if (!from) return std::nullopt;
    std::optional<std::pair<uint16_t, int>> best;
    for (const auto& cand : frags) {
        if (cand.id == from_id) continue;
        int ov = row_junction_overlap(*from, cand, policy.min_row_overlap, policy.case_fold_ascii);
        if (ov == 0) continue;
        if (!best.has_value()) {
            best = {cand.id, ov};
            continue;
        }
        if (ov > best->second) {
            best = {cand.id, ov};
        } else if (ov == best->second) {
            const Fragment* bto = find_frag(frags, best->first);
            if (cand.seq < bto->seq || (cand.seq == bto->seq && cand.id < bto->id)) {
                best = {cand.id, ov};
            }
        }
    }
    return best;
}

IngestChainResult trace_ingest_chain(const std::vector<Fragment>& fragments, const Policy& policy) {
    IngestChainResult out;
    auto start = resolve_ingest_open(fragments, policy);
    if (!start.has_value()) return out;
    out.open_fragment_id = *start;
    out.chain_fragment_ids.push_back(*start);
    std::set<uint16_t> used;
    used.insert(*start);
    uint16_t cur = *start;
    while (true) {
        auto nxt = select_ingest_edge(cur, fragments, policy);
        if (!nxt.has_value() || used.count(nxt->first) != 0) break;
        out.chain_fragment_ids.push_back(nxt->first);
        out.chain_overlaps.push_back(nxt->second);
        used.insert(nxt->first);
        cur = nxt->first;
    }
    return out;
}

bool evaluate_replica_coverage(const std::vector<Fragment>& fragments, const Policy& policy) {
    for (const auto& f : fragments) {
        if ((f.replica_mask & policy.required_replica_mask) != policy.required_replica_mask) {
            return false;
        }
    }
    return true;
}
