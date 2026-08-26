"""Milestone 5 tests: cross-signing trust-graph cycle/reachability analysis.

The agent's `trustgraph` module (at /app/transparency/trustgraph.py) is fuzzed
against a fully INDEPENDENT in-test reference over hundreds of randomized,
tampered cross-signing trust graphs that include multi-node trust cycles,
self-asserted authority (self-loops), duplicate node ids that must collapse to a
single vertex, and edges that dangle to absent keys. The whole per-node verdict
AND the summary must match exactly. The reference re-derives strongly-connected
components with its OWN transitive-closure algorithm and imports only the
mandated public entry point `analyze_trust_graph`.
"""

import random
import sys
from collections import deque

sys.path.insert(0, "/app/transparency")
# the enriched corpus contains deep DAGs / large SCCs; the recursive references
# below can nest beyond the default limit.
sys.setrecursionlimit(100000)

from trustgraph import analyze_trust_graph  # noqa: E402  (only public API name)


# --- INDEPENDENT reference (transitive-closure mutual reachability) ----------

def _ref(graph):
    nodes, present = [], set()
    compromised = set()
    for n in graph.get("nodes", []):
        if isinstance(n, str):
            nid = n
        else:
            nid = n["id"]
            if n.get("compromised"):
                compromised.add(nid)
        if nid not in present:
            present.add(nid)
            nodes.append(nid)
    compromised &= present
    succ = {n: set() for n in nodes}
    dangling = set()
    for e in graph.get("edges", []):
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        if s not in present:
            continue
        if d not in present:
            dangling.add((s, d))
            continue
        succ[s].add(d)
    # transitive closure (paths of length >= 1), independent of any SCC algo
    reach = {a: set(succ[a]) for a in nodes}
    changed = True
    while changed:
        changed = False
        for a in nodes:
            add = set()
            for b in list(reach[a]):
                add |= succ[b]
            if not add <= reach[a]:
                reach[a] |= add
                changed = True
    comp = {}
    for a in nodes:
        comp[a] = frozenset([a] + [b for b in nodes
                                   if b != a and b in reach[a] and a in reach[b]])
    rset = set()
    for r in graph.get("roots", []):
        if r in present:
            rset.add(r)
            rset |= reach[r]

    def is_cyc(a):
        return len(comp[a]) >= 2 or a in succ[a]

    acyclic = {a for a in nodes if not is_cyc(a)}
    preds = {n: set() for n in nodes}
    for a in nodes:
        for b in succ[a]:
            preds[b].add(a)
    rank = {}

    def rk(a, seen):
        if a in rank:
            return rank[a]
        seen = seen | {a}
        best = 0
        for p in preds[a]:
            if p in acyclic and p != a and p not in seen:
                best = max(best, rk(p, seen) + 1)
        rank[a] = best
        return best

    for a in nodes:
        if a in acyclic:
            rk(a, set())
    # --- trust_depth: longest chain over the SCC condensation, re-derived a
    # DIFFERENT way than the oracle: group nodes BY their concrete component
    # (frozenset cluster), build cluster->cluster predecessor sets, then take a
    # memoized DFS longest-path over the cluster objects (no Kahn relaxation,
    # no rep keying). Every member of a cluster shares the depth.
    clusters = []
    seen_cl = set()
    for a in nodes:
        c = comp[a]
        if c not in seen_cl:
            seen_cl.add(c)
            clusters.append(c)
    cl_preds = {c: set() for c in clusters}
    for a in nodes:
        ca = comp[a]
        for b in succ[a]:
            cb = comp[b]
            if cb != ca:
                cl_preds[cb].add(ca)
    cl_depth = {}

    def cdepth(c, stk):
        if c in cl_depth:
            return cl_depth[c]
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk:
                best = max(best, cdepth(p, stk) + 1)
        cl_depth[c] = best
        return best

    for c in clusters:
        cdepth(c, set())
    tdepth = {a: cl_depth[comp[a]] for a in nodes}
    # weighted_trust_depth: same cluster condensation, but each cluster
    # contributes its concrete len(cluster) instead of one level (memoized
    # cluster DFS over predecessors; anchor cluster contributes just its own
    # size, so >= 1 for every key). Every member shares the value.
    cl_wdepth = {}

    def cwdepth(c, stk):
        if c in cl_wdepth:
            return cl_wdepth[c]
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk:
                best = max(best, cwdepth(p, stk))
        cl_wdepth[c] = len(c) + best
        return cl_wdepth[c]

    for c in clusters:
        cwdepth(c, set())
    wdepth = {a: cl_wdepth[comp[a]] for a in nodes}
    # clean_trust_depth: SAME cluster condensation, but a cluster is DIRTY iff any
    # member is compromised; the longest path runs over CLEAN clusters only and is
    # CUT at every dirty cluster (a dirty cluster's members are 0 and dirty
    # predecessors do not contribute). Re-derived a DIFFERENT way than the oracle:
    # a per-cluster dirty flag over the concrete frozenset cluster objects +
    # memoized cluster DFS over clean-only predecessors.
    cl_dirty = {c: any(m in compromised for m in c) for c in clusters}
    cl_cdepth = {}

    def ccdepth(c, stk):
        if c in cl_cdepth:
            return cl_cdepth[c]
        if cl_dirty[c]:
            cl_cdepth[c] = 0
            return 0
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk and not cl_dirty[p]:
                best = max(best, ccdepth(p, stk) + 1)
        cl_cdepth[c] = best
        return best

    for c in clusters:
        ccdepth(c, set())
    cdepth_n = {a: cl_cdepth[comp[a]] for a in nodes}
    # root_distance: forward shortest cross-cluster BFS from every present root's
    # cluster over the condensation (re-derived a DIFFERENT way than the oracle:
    # concrete frozenset clusters + a from-scratch cluster successor map).
    cl_succ_r = _cluster_succ(clusters, comp, nodes, succ)
    rdist = _correct_root_distance(clusters, cl_succ_r, comp,
                                   graph.get("roots", []), present, nodes)
    out = {}
    for a in nodes:
        out[a] = {"in_cycle": is_cyc(a), "scc_rep": min(comp[a]),
                  "scc_size": len(comp[a]), "unreachable": a not in rset,
                  "rank": None if is_cyc(a) else rank[a],
                  "trust_depth": tdepth[a],
                  "weighted_trust_depth": wdepth[a],
                  "clean_trust_depth": cdepth_n[a],
                  "root_distance": rdist[a]}
    seen_c, nscc, ncyc, largest = set(), 0, 0, 0
    for a in nodes:
        if comp[a] not in seen_c:
            seen_c.add(comp[a])
            nscc += 1
            sl = any(m in succ[m] for m in comp[a])
            if len(comp[a]) >= 2 or sl:
                ncyc += 1
                largest = max(largest, len(comp[a]))
    return {"nodes": out, "summary": {
        "num_sccs": nscc, "num_cycle_sccs": ncyc, "largest_cycle": largest,
        "is_acyclic": ncyc == 0,
        "num_unreachable": sum(1 for a in nodes if a not in rset),
        "dangling_edges": len(dangling),
        "max_trust_depth": max((tdepth[a] for a in nodes), default=0),
        "max_weighted_trust_depth": max((wdepth[a] for a in nodes), default=0),
        "max_clean_trust_depth": max((cdepth_n[a] for a in nodes), default=0),
        "max_root_distance": max(
            (rdist[a] for a in nodes if rdist[a] is not None), default=0),
        "num_compromised": len(compromised)}}


def _correct_clean(clusters, cl_preds, comp, compromised, nodes):
    """Shared CORRECT clean_trust_depth so the careful controls below diverge
    from the oracle ONLY on their own (rank / raw-depth / unweighted) axis and
    agree on clean_trust_depth. Longest path over CLEAN clusters only, cut at any
    cluster with a compromised member."""
    cl_dirty = {c: any(m in compromised for m in c) for c in clusters}
    cl_cdepth = {}

    def ccdepth(c, stk):
        if c in cl_cdepth:
            return cl_cdepth[c]
        if cl_dirty[c]:
            cl_cdepth[c] = 0
            return 0
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk and not cl_dirty[p]:
                best = max(best, ccdepth(p, stk) + 1)
        cl_cdepth[c] = best
        return best

    for c in clusters:
        ccdepth(c, set())
    return {a: cl_cdepth[comp[a]] for a in nodes}


def _correct_root_distance(clusters, cl_succ, comp, roots, present, nodes):
    """Shared CORRECT root_distance so every careful control below agrees with
    the oracle on this axis and diverges ONLY on its own (rank / raw-depth /
    unweighted / revocation) axis. Forward BFS over the cluster condensation from
    every present root's cluster; a cluster containing a present root anchors at
    0, others take 1 + the minimum distance of a cluster with a cross-component
    edge INTO them; clusters not reached from any root cluster are None. Keyed on
    concrete frozenset cluster objects (a DIFFERENT representation than the
    oracle's min-id rep), re-derived independently."""
    dist = {}
    frontier = deque()
    for r in roots:
        if r in present:
            cr = comp[r]
            if cr not in dist:
                dist[cr] = 0
                frontier.append(cr)
    while frontier:
        cur = frontier.popleft()
        for nxt in cl_succ.get(cur, ()):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                frontier.append(nxt)
    return {a: dist.get(comp[a]) for a in nodes}


def _cluster_succ(clusters, comp, nodes, succ):
    """Cross-cluster successor sets keyed on concrete frozenset cluster objects."""
    cl_succ = {c: set() for c in clusters}
    for a in nodes:
        ca = comp[a]
        for b in succ[a]:
            cb = comp[b]
            if cb != ca:
                cl_succ[ca].add(cb)
    return cl_succ


# --- naive standard solver (negative control) -------------------------------

def _naive(graph):
    """Plain DFS back-edge cycle check, NO duplicate-id collapse, edges to
    absent nodes left in place. Represents a standard first attempt."""
    nodes = [n if isinstance(n, str) else n["id"] for n in graph.get("nodes", [])]
    succ = {}
    for n in nodes:
        succ.setdefault(n, set())
    for e in graph.get("edges", []):
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        succ.setdefault(s, set()).add(d)
        succ.setdefault(d, set())
    color = {n: 0 for n in succ}
    on_cycle = set()

    def dfs(u):
        color[u] = 1
        for v in sorted(succ[u]):
            if color[v] == 1:
                on_cycle.add(u)
                on_cycle.add(v)
            elif color[v] == 0:
                dfs(v)
        color[u] = 2

    for n in list(succ):
        if color[n] == 0:
            dfs(n)
    rset = set(graph.get("roots", []))
    fr = list(rset)
    while fr:
        c = fr.pop()
        for v in succ.get(c, ()):
            if v not in rset:
                rset.add(v)
                fr.append(v)
    # RAW per-node longest predecessor chain (no SCC condensation), bounded to
    # avoid runaway recursion on cycles -- the standard naive trust_depth.
    preds = {n: set() for n in succ}
    for u in succ:
        for v in succ[u]:
            preds.setdefault(v, set()).add(u)
    tdepth = {}

    def td(n, stk):
        if n in tdepth:
            return tdepth[n]
        stk = stk | {n}
        best = 0
        for p in preds.get(n, ()):
            if p != n and p not in stk:
                best = max(best, td(p, stk) + 1)
        tdepth[n] = best
        return best

    for n in succ:
        td(n, set())
    out = {}
    for n in nodes:
        cyc = n in on_cycle
        out[n] = {"in_cycle": cyc, "scc_rep": n, "scc_size": 1,
                  "unreachable": n not in rset, "rank": None if cyc else 0,
                  "trust_depth": tdepth.get(n, 0),
                  "weighted_trust_depth": tdepth.get(n, 0) + 1,
                  "clean_trust_depth": tdepth.get(n, 0),
                  "root_distance": 0 if n in rset else None}
    return {"nodes": out, "summary": {
        "num_sccs": len(set(nodes)), "num_cycle_sccs": len(on_cycle),
        "largest_cycle": 1 if on_cycle else 0, "is_acyclic": not on_cycle,
        "num_unreachable": sum(1 for n in nodes if n not in rset),
        "dangling_edges": 0,
        "max_trust_depth": max((tdepth.get(n, 0) for n in nodes), default=0),
        "max_weighted_trust_depth": max(
            (tdepth.get(n, 0) + 1 for n in nodes), default=0),
        "max_clean_trust_depth": max(
            (tdepth.get(n, 0) for n in nodes), default=0),
        "max_root_distance": 0,
        "num_compromised": 0}}


# --- careful-but-imperfect solver (negative control) ------------------------

def _careful_shortest_rank(graph):
    """SCC / cycle / reachability EXACTLY right (own transitive closure), but
    layers `rank` by SHORTEST path -- 1 + the MINIMUM rank over non-cyclic
    predecessors instead of the spec's maximum (longest-path) layering. This is
    what a careful agent who misreads the rank rule produces; it must DIVERGE
    from the oracle on the deep skip-edge DAGs in the corpus."""
    nodes, present = [], set()
    compromised = set()
    for n in graph.get("nodes", []):
        if isinstance(n, str):
            nid = n
        else:
            nid = n["id"]
            if n.get("compromised"):
                compromised.add(nid)
        if nid not in present:
            present.add(nid)
            nodes.append(nid)
    compromised &= present
    succ = {n: set() for n in nodes}
    dangling = set()
    for e in graph.get("edges", []):
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        if s not in present:
            continue
        if d not in present:
            dangling.add((s, d))
            continue
        succ[s].add(d)
    reach = {a: set(succ[a]) for a in nodes}
    changed = True
    while changed:
        changed = False
        for a in nodes:
            add = set()
            for b in list(reach[a]):
                add |= succ[b]
            if not add <= reach[a]:
                reach[a] |= add
                changed = True
    comp = {a: frozenset([a] + [b for b in nodes if b != a and b in reach[a]
                               and a in reach[b]]) for a in nodes}
    rset = set()
    for r in graph.get("roots", []):
        if r in present:
            rset.add(r)
            rset |= reach[r]

    def is_cyc(a):
        return len(comp[a]) >= 2 or a in succ[a]

    acyclic = {a for a in nodes if not is_cyc(a)}
    preds = {n: set() for n in nodes}
    for a in nodes:
        for b in succ[a]:
            preds[b].add(a)
    rank = {}

    def rk(a, seen):
        if a in rank:
            return rank[a]
        ap = [p for p in preds[a] if p in acyclic and p != a and p not in seen]
        rank[a] = 0 if not ap else 1 + min(rk(p, seen | {a}) for p in ap)
        return rank[a]

    for a in nodes:
        if a in acyclic:
            rk(a, set())
    # trust_depth computed CORRECTLY (condensation longest-path) so this control
    # diverges from the oracle ONLY on its `rank` axis, never on trust_depth.
    clusters = []
    seen_cl = set()
    for a in nodes:
        c = comp[a]
        if c not in seen_cl:
            seen_cl.add(c)
            clusters.append(c)
    cl_preds = {c: set() for c in clusters}
    for a in nodes:
        ca = comp[a]
        for b in succ[a]:
            cb = comp[b]
            if cb != ca:
                cl_preds[cb].add(ca)
    cl_depth = {}

    def cdepth(c, stk):
        if c in cl_depth:
            return cl_depth[c]
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk:
                best = max(best, cdepth(p, stk) + 1)
        cl_depth[c] = best
        return best

    for c in clusters:
        cdepth(c, set())
    tdepth = {a: cl_depth[comp[a]] for a in nodes}
    # weighted_trust_depth: same cluster condensation, but each cluster
    # contributes its concrete len(cluster) instead of one level (memoized
    # cluster DFS over predecessors; anchor cluster contributes just its own
    # size, so >= 1 for every key). Every member shares the value.
    cl_wdepth = {}

    def cwdepth(c, stk):
        if c in cl_wdepth:
            return cl_wdepth[c]
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk:
                best = max(best, cwdepth(p, stk))
        cl_wdepth[c] = len(c) + best
        return cl_wdepth[c]

    for c in clusters:
        cwdepth(c, set())
    wdepth = {a: cl_wdepth[comp[a]] for a in nodes}
    cdepth_n = _correct_clean(clusters, cl_preds, comp, compromised, nodes)
    cl_succ_r = _cluster_succ(clusters, comp, nodes, succ)
    rdist = _correct_root_distance(clusters, cl_succ_r, comp,
                                   graph.get("roots", []), present, nodes)
    out = {}
    for a in nodes:
        out[a] = {"in_cycle": is_cyc(a), "scc_rep": min(comp[a]),
                  "scc_size": len(comp[a]), "unreachable": a not in rset,
                  "rank": None if is_cyc(a) else rank[a],
                  "trust_depth": tdepth[a],
                  "weighted_trust_depth": wdepth[a],
                  "clean_trust_depth": cdepth_n[a],
                  "root_distance": rdist[a]}
    seen_c, nscc, ncyc, largest = set(), 0, 0, 0
    for a in nodes:
        if comp[a] not in seen_c:
            seen_c.add(comp[a])
            nscc += 1
            sl = any(m in succ[m] for m in comp[a])
            if len(comp[a]) >= 2 or sl:
                ncyc += 1
                largest = max(largest, len(comp[a]))
    return {"nodes": out, "summary": {
        "num_sccs": nscc, "num_cycle_sccs": ncyc, "largest_cycle": largest,
        "is_acyclic": ncyc == 0,
        "num_unreachable": sum(1 for a in nodes if a not in rset),
        "dangling_edges": len(dangling),
        "max_trust_depth": max((tdepth[a] for a in nodes), default=0),
        "max_weighted_trust_depth": max((wdepth[a] for a in nodes), default=0),
        "max_clean_trust_depth": max((cdepth_n[a] for a in nodes), default=0),
        "max_root_distance": max(
            (rdist[a] for a in nodes if rdist[a] is not None), default=0),
        "num_compromised": len(compromised)}}


# --- careful-but-imperfect solver: RAW per-node trust_depth (negative control)


def _careful_raw_trust_depth(graph):
    """SCC / cycle / reachability / rank ALL EXACTLY right (own transitive
    closure + spec longest-path rank), but computes `trust_depth` the INTUITIVE
    RAW way -- the longest chain of *individual* present predecessor keys ending
    at the node, WITHOUT collapsing strongly-connected components to one level.
    Wherever a trust chain passes through (or sits inside) a cross-signing ring,
    the intra-ring hops inflate this raw depth above the spec's condensation
    depth, so this careful solver must DIVERGE from the oracle on the corpus."""
    nodes, present = [], set()
    compromised = set()
    for n in graph.get("nodes", []):
        if isinstance(n, str):
            nid = n
        else:
            nid = n["id"]
            if n.get("compromised"):
                compromised.add(nid)
        if nid not in present:
            present.add(nid)
            nodes.append(nid)
    compromised &= present
    succ = {n: set() for n in nodes}
    dangling = set()
    for e in graph.get("edges", []):
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        if s not in present:
            continue
        if d not in present:
            dangling.add((s, d))
            continue
        succ[s].add(d)
    reach = {a: set(succ[a]) for a in nodes}
    changed = True
    while changed:
        changed = False
        for a in nodes:
            add = set()
            for b in list(reach[a]):
                add |= succ[b]
            if not add <= reach[a]:
                reach[a] |= add
                changed = True
    comp = {a: frozenset([a] + [b for b in nodes if b != a and b in reach[a]
                               and a in reach[b]]) for a in nodes}
    rset = set()
    for r in graph.get("roots", []):
        if r in present:
            rset.add(r)
            rset |= reach[r]

    def is_cyc(a):
        return len(comp[a]) >= 2 or a in succ[a]

    acyclic = {a for a in nodes if not is_cyc(a)}
    preds = {n: set() for n in nodes}
    for a in nodes:
        for b in succ[a]:
            preds[b].add(a)
    rank = {}

    def rk(a, seen):
        if a in rank:
            return rank[a]
        best = 0
        for p in preds[a]:
            if p in acyclic and p != a and p not in seen:
                best = max(best, rk(p, seen | {a}) + 1)
        rank[a] = best
        return best

    for a in nodes:
        if a in acyclic:
            rk(a, set())
    # RAW per-node longest predecessor chain -- NO SCC condensation.
    raw = {}

    def rd(a, stk):
        if a in raw:
            return raw[a]
        stk = stk | {a}
        best = 0
        for p in preds[a]:
            if p != a and p not in stk:
                best = max(best, rd(p, stk) + 1)
        raw[a] = best
        return best

    for a in nodes:
        rd(a, set())
    # weighted_trust_depth computed CORRECTLY (size-weighted condensation) so
    # this control diverges from the oracle ONLY on its raw `trust_depth` axis.
    clusters = []
    seen_cl = set()
    for a in nodes:
        c = comp[a]
        if c not in seen_cl:
            seen_cl.add(c)
            clusters.append(c)
    cl_preds = {c: set() for c in clusters}
    for a in nodes:
        ca = comp[a]
        for b in succ[a]:
            cb = comp[b]
            if cb != ca:
                cl_preds[cb].add(ca)
    cl_wdepth = {}

    def cwdepth(c, stk):
        if c in cl_wdepth:
            return cl_wdepth[c]
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk:
                best = max(best, cwdepth(p, stk))
        cl_wdepth[c] = len(c) + best
        return cl_wdepth[c]

    for c in clusters:
        cwdepth(c, set())
    wdepth = {a: cl_wdepth[comp[a]] for a in nodes}
    cdepth_n = _correct_clean(clusters, cl_preds, comp, compromised, nodes)
    cl_succ_r = _cluster_succ(clusters, comp, nodes, succ)
    rdist = _correct_root_distance(clusters, cl_succ_r, comp,
                                   graph.get("roots", []), present, nodes)
    out = {}
    for a in nodes:
        out[a] = {"in_cycle": is_cyc(a), "scc_rep": min(comp[a]),
                  "scc_size": len(comp[a]), "unreachable": a not in rset,
                  "rank": None if is_cyc(a) else rank[a],
                  "trust_depth": raw[a],
                  "weighted_trust_depth": wdepth[a],
                  "clean_trust_depth": cdepth_n[a],
                  "root_distance": rdist[a]}
    seen_c, nscc, ncyc, largest = set(), 0, 0, 0
    for a in nodes:
        if comp[a] not in seen_c:
            seen_c.add(comp[a])
            nscc += 1
            sl = any(m in succ[m] for m in comp[a])
            if len(comp[a]) >= 2 or sl:
                ncyc += 1
                largest = max(largest, len(comp[a]))
    return {"nodes": out, "summary": {
        "num_sccs": nscc, "num_cycle_sccs": ncyc, "largest_cycle": largest,
        "is_acyclic": ncyc == 0,
        "num_unreachable": sum(1 for a in nodes if a not in rset),
        "dangling_edges": len(dangling),
        "max_trust_depth": max((raw[a] for a in nodes), default=0),
        "max_weighted_trust_depth": max((wdepth[a] for a in nodes), default=0),
        "max_clean_trust_depth": max((cdepth_n[a] for a in nodes), default=0),
        "max_root_distance": max(
            (rdist[a] for a in nodes if rdist[a] is not None), default=0),
        "num_compromised": len(compromised)}}


# --- careful-but-imperfect solver: UNWEIGHTED trust_depth (negative control) --


def _unweighted_trust_depth(graph):
    """SCC / cycle / reachability / rank / trust_depth ALL EXACTLY right (own
    transitive closure + spec longest-path rank + spec SCC-condensation
    trust_depth), but computes `weighted_trust_depth` the INTUITIVE UNWEIGHTED
    way -- one level per trust component (a super-node with no cross-component
    predecessor anchors at 1, otherwise 1 + the max weighted depth of a
    predecessor super-node) -- instead of the spec's SIZE-WEIGHTED accumulation
    where each component contributes its whole member count. This is exactly the
    careful agent who reads "longest chain of trust components" and reports one
    level per component, ignoring the size weighting. Wherever a multi-key
    cross-signing ring sits on a trust chain, the size weighting inflates the
    spec value above this unweighted reading, so this control must DIVERGE from
    the oracle on the corpus."""
    nodes, present = [], set()
    compromised = set()
    for n in graph.get("nodes", []):
        if isinstance(n, str):
            nid = n
        else:
            nid = n["id"]
            if n.get("compromised"):
                compromised.add(nid)
        if nid not in present:
            present.add(nid)
            nodes.append(nid)
    compromised &= present
    succ = {n: set() for n in nodes}
    dangling = set()
    for e in graph.get("edges", []):
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        if s not in present:
            continue
        if d not in present:
            dangling.add((s, d))
            continue
        succ[s].add(d)
    reach = {a: set(succ[a]) for a in nodes}
    changed = True
    while changed:
        changed = False
        for a in nodes:
            add = set()
            for b in list(reach[a]):
                add |= succ[b]
            if not add <= reach[a]:
                reach[a] |= add
                changed = True
    comp = {a: frozenset([a] + [b for b in nodes if b != a and b in reach[a]
                               and a in reach[b]]) for a in nodes}
    rset = set()
    for r in graph.get("roots", []):
        if r in present:
            rset.add(r)
            rset |= reach[r]

    def is_cyc(a):
        return len(comp[a]) >= 2 or a in succ[a]

    acyclic = {a for a in nodes if not is_cyc(a)}
    preds = {n: set() for n in nodes}
    for a in nodes:
        for b in succ[a]:
            preds[b].add(a)
    rank = {}

    def rk(a, seen):
        if a in rank:
            return rank[a]
        best = 0
        for p in preds[a]:
            if p in acyclic and p != a and p not in seen:
                best = max(best, rk(p, seen | {a}) + 1)
        rank[a] = best
        return best

    for a in nodes:
        if a in acyclic:
            rk(a, set())
    clusters = []
    seen_cl = set()
    for a in nodes:
        c = comp[a]
        if c not in seen_cl:
            seen_cl.add(c)
            clusters.append(c)
    cl_preds = {c: set() for c in clusters}
    for a in nodes:
        ca = comp[a]
        for b in succ[a]:
            cb = comp[b]
            if cb != ca:
                cl_preds[cb].add(ca)
    # CORRECT spec trust_depth (one level per component, anchor 0).
    cl_depth = {}

    def cdepth(c, stk):
        if c in cl_depth:
            return cl_depth[c]
        stk = stk | {c}
        best = 0
        for p in cl_preds[c]:
            if p != c and p not in stk:
                best = max(best, cdepth(p, stk) + 1)
        cl_depth[c] = best
        return cl_depth[c]

    for c in clusters:
        cdepth(c, set())
    tdepth = {a: cl_depth[comp[a]] for a in nodes}
    # WRONG weighted_trust_depth: one level per component (size weighting
    # ignored), anchored at 1 -- i.e. exactly trust_depth + 1.
    wdepth = {a: cl_depth[comp[a]] + 1 for a in nodes}
    cdepth_n = _correct_clean(clusters, cl_preds, comp, compromised, nodes)
    cl_succ_r = _cluster_succ(clusters, comp, nodes, succ)
    rdist = _correct_root_distance(clusters, cl_succ_r, comp,
                                   graph.get("roots", []), present, nodes)
    out = {}
    for a in nodes:
        out[a] = {"in_cycle": is_cyc(a), "scc_rep": min(comp[a]),
                  "scc_size": len(comp[a]), "unreachable": a not in rset,
                  "rank": None if is_cyc(a) else rank[a],
                  "trust_depth": tdepth[a],
                  "weighted_trust_depth": wdepth[a],
                  "clean_trust_depth": cdepth_n[a],
                  "root_distance": rdist[a]}
    seen_c, nscc, ncyc, largest = set(), 0, 0, 0
    for a in nodes:
        if comp[a] not in seen_c:
            seen_c.add(comp[a])
            nscc += 1
            sl = any(m in succ[m] for m in comp[a])
            if len(comp[a]) >= 2 or sl:
                ncyc += 1
                largest = max(largest, len(comp[a]))
    return {"nodes": out, "summary": {
        "num_sccs": nscc, "num_cycle_sccs": ncyc, "largest_cycle": largest,
        "is_acyclic": ncyc == 0,
        "num_unreachable": sum(1 for a in nodes if a not in rset),
        "dangling_edges": len(dangling),
        "max_trust_depth": max((tdepth[a] for a in nodes), default=0),
        "max_weighted_trust_depth": max((wdepth[a] for a in nodes), default=0),
        "max_clean_trust_depth": max((cdepth_n[a] for a in nodes), default=0),
        "max_root_distance": max(
            (rdist[a] for a in nodes if rdist[a] is not None), default=0),
        "num_compromised": len(compromised)}}


# --- careful-but-imperfect solver: IGNORE-REVOCATION clean_trust_depth -------


def _ignore_revocation(graph):
    """SCC / cycle / reachability / rank / trust_depth / weighted_trust_depth ALL
    EXACTLY right, but computes `clean_trust_depth` as a COPY of the plain
    structural `trust_depth` -- i.e. it ignores the per-key compromise flags
    entirely and never severs a trust chain at a revoked component. This is the
    careful agent who analyses the trust structure correctly but does NOT couple
    it to the key-revocation state. Wherever a compromised key sits on (or roots)
    a trust chain, the spec's clean depth is cut below this structural reading, so
    this control must DIVERGE from the oracle on the corpus.

    Built by re-using the fully-correct independent reference and overwriting only
    the clean_trust_depth field (both per-node and the summary max) with the plain
    trust_depth, which is the exact mistake being modelled."""
    base = _ref(graph)
    for v in base["nodes"].values():
        v["clean_trust_depth"] = v["trust_depth"]
    base["summary"]["max_clean_trust_depth"] = base["summary"]["max_trust_depth"]
    return base


# --- careful-but-imperfect solver: RAW-BFS root_distance (negative control) ---


def _raw_bfs_root_distance(graph):
    """SCC / cycle / reachability / rank / trust_depth / weighted_trust_depth /
    clean_trust_depth ALL EXACTLY right, but computes `root_distance` by a RAW
    per-key BFS over individual present edges from the declared roots -- counting
    one hop for EVERY key crossed -- instead of the shortest path over the SCC
    *condensation*, where a whole cross-signing ring is a single super-node and
    crossing it costs ONE hop, not one per ring member. This is exactly the
    careful agent who measures distance-from-roots but forgets to collapse rings
    first. Wherever the shortest root path threads (or enters) a multi-key ring,
    the raw per-key count over-states the condensed distance, so this control must
    DIVERGE from the oracle on the corpus.

    Built by re-using the fully-correct independent reference and overwriting only
    the root_distance field (per-node and the summary max) with the raw per-key
    BFS value, which is the exact mistake being modelled."""
    base = _ref(graph)
    # rebuild normalized adjacency + present set for the raw BFS
    present, order = set(), []
    for n in graph.get("nodes", []):
        nid = n if isinstance(n, str) else n["id"]
        if nid not in present:
            present.add(nid)
            order.append(nid)
    succ = {n: set() for n in order}
    for e in graph.get("edges", []):
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        if s in present and d in present:
            succ[s].add(d)
    dist = {}
    frontier = deque()
    for r in graph.get("roots", []):
        if r in present and r not in dist:
            dist[r] = 0
            frontier.append(r)
    while frontier:
        cur = frontier.popleft()
        for nxt in succ.get(cur, ()):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                frontier.append(nxt)
    for nid, v in base["nodes"].items():
        v["root_distance"] = dist.get(nid)
    finite = [d for d in dist.values()]
    base["summary"]["max_root_distance"] = max(finite, default=0)
    return base


# --- corpus builder ---------------------------------------------------------

def _make_small(rng):
    """Original shallow tampered graph (kept ~35% of the corpus for variety)."""
    base = ["k%02d" % i for i in range(rng.randint(3, 9))]
    nodes = list(base)
    for _ in range(rng.randint(0, 3)):
        nodes.insert(rng.randint(0, len(nodes)), rng.choice(base))
    edges = []
    for _ in range(rng.randint(2, len(base) * 2)):
        edges.append([rng.choice(base), rng.choice(base)])
    if rng.random() < 0.7 and len(base) >= 3:
        ring = rng.sample(base, rng.randint(2, min(4, len(base))))
        for i in range(len(ring)):
            edges.append([ring[i], ring[(i + 1) % len(ring)]])
    for _ in range(rng.randint(0, 2)):
        s = rng.choice(base)
        edges.append([s, s])
    for _ in range(rng.randint(0, 3)):
        if rng.random() < 0.5:
            edges.append([rng.choice(base), "ABSENT%d" % rng.randint(0, 5)])
        else:
            edges.append(["ABSENT%d" % rng.randint(0, 5), rng.choice(base)])
    roots = rng.sample(base, rng.randint(0, min(2, len(base))))
    rng.shuffle(edges)
    return {"nodes": nodes, "edges": edges, "roots": roots}


def _make_deep(rng):
    """Deep+wide acyclic DAG (long backbone + multi-layer SKIP edges so the
    longest-path rank differs from the shortest-path rank) PLUS one or two
    large sparse-chord SCCs (size 6-12) that region-A chains reach but are not
    members of. Self-loops, duplicate ids and dangling edges layered on top."""
    nodes = []
    edges = []

    # ---- Region A: layered acyclic DAG (longest != shortest path) ----
    n_layers = rng.randint(5, 9)
    layers = []
    for li in range(n_layers):
        w = rng.randint(1, 3)
        layer = ["a%d_%d" % (li, j) for j in range(w)]
        layers.append(layer)
        nodes.extend(layer)
    # backbone: a long chain through one node per adjacent layer (deep longest path)
    for li in range(n_layers - 1):
        edges.append([rng.choice(layers[li]), rng.choice(layers[li + 1])])
    # extra adjacent-layer edges (width)
    for li in range(n_layers - 1):
        for u in layers[li]:
            if rng.random() < 0.5:
                edges.append([u, rng.choice(layers[li + 1])])
    # multi-layer SKIP edges (jump >=2 layers): a short path competes with the
    # long backbone, so shortest-path rank != longest-path rank.
    for li in range(n_layers):
        for lj in range(li + 2, n_layers):
            if rng.random() < 0.30:
                edges.append([rng.choice(layers[li]), rng.choice(layers[lj])])

    # ---- Region B: one or two sparse-chord SCCs (size 6-12) ----
    n_scc = rng.randint(1, 2)
    sccs = []
    for si in range(n_scc):
        size = rng.randint(6, 12)
        ring = ["s%d_%d" % (si, j) for j in range(size)]
        nodes.extend(ring)
        sccs.append(ring)
        for j in range(size):
            edges.append([ring[j], ring[(j + 1) % size]])  # closing ring
        n_chords = max(1, int(round(size * (size - 1) * rng.uniform(0.10, 0.14))))
        for _ in range(n_chords):
            a, b = rng.sample(ring, 2)
            edges.append([a, b])

    # ---- reaches-but-not-in-cycle: region-A chain enters each SCC ----
    for ring in sccs:
        edges.append([rng.choice(layers[rng.randint(0, n_layers - 1)]),
                      rng.choice(ring)])
    # exit chain from an SCC into a fresh acyclic tail (cyclic preds don't
    # contribute, so the tail re-starts at rank 0)
    if rng.random() < 0.6 and sccs:
        tlen = rng.randint(1, 4)
        tail = ["t%d" % j for j in range(tlen)]
        nodes.extend(tail)
        edges.append([rng.choice(sccs[0]), tail[0]])
        for j in range(tlen - 1):
            edges.append([tail[j], tail[j + 1]])

    # ---- tamper layer: self-loops, dangling edges, duplicate ids ----
    for _ in range(rng.randint(0, 2)):
        s = rng.choice(nodes)
        edges.append([s, s])
    for _ in range(rng.randint(0, 3)):
        if rng.random() < 0.5:
            edges.append([rng.choice(nodes), "ABSENT%d" % rng.randint(0, 6)])
        else:
            edges.append(["ABSENT%d" % rng.randint(0, 6), rng.choice(nodes)])
    out_nodes = list(nodes)
    for _ in range(rng.randint(0, 3)):
        out_nodes.insert(rng.randint(0, len(out_nodes)), rng.choice(nodes))

    root_pool = layers[0] + (layers[1] if n_layers > 1 else [])
    roots = rng.sample(root_pool, rng.randint(1, min(2, len(root_pool))))
    rng.shuffle(edges)
    return {"nodes": out_nodes, "edges": edges, "roots": roots}


def _inject_compromise(graph, rng):
    """Flag a fraction of present keys as *compromised* (revoked) so that the
    coupled `clean_trust_depth` genuinely varies across the corpus.

    Each presented key node is normally a bare string id; this rewrites a chosen
    subset of present ids to dict form ``{"id": <id>, "compromised": True}`` on
    EVERY occurrence (so duplicate-collapse still applies and the flag is read
    consistently). The selection is biased toward keys that have at least one
    present successor (interior keys that sit ON a trust chain) -- revoking those
    actually SEVERS a downstream clean chain, which is where the spec's
    clean_trust_depth drops below the structural trust_depth. A handful of pure
    leaves are flagged too for variety. ~10% of graphs are left fully clean so the
    fields coincide there (clean_trust_depth == trust_depth), keeping the coupling
    genuine rather than universal."""
    nodes = graph["nodes"]
    # present ids in first-appearance order
    present, order = set(), []
    for n in nodes:
        nid = n if isinstance(n, str) else n["id"]
        if nid not in present:
            present.add(nid)
            order.append(nid)
    if not order or rng.random() < 0.10:
        return graph  # leave ~10% of graphs fully clean
    # interior keys = those with at least one present successor (sit on a chain)
    has_succ = set()
    for e in graph["edges"]:
        s, d = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e["src"], e["dst"])
        if s in present and d in present:
            has_succ.add(s)
    interior = [n for n in order if n in has_succ]
    leaves = [n for n in order if n not in has_succ]
    chosen = set()
    # bias: revoke ~20-40% of interior keys (chain-severing), plus a few leaves
    if interior:
        k = max(1, int(round(len(interior) * rng.uniform(0.20, 0.40))))
        chosen.update(rng.sample(interior, min(k, len(interior))))
    if leaves and rng.random() < 0.6:
        k = rng.randint(1, max(1, len(leaves) // 3))
        chosen.update(rng.sample(leaves, min(k, len(leaves))))
    if not chosen:
        chosen.add(rng.choice(order))
    new_nodes = []
    for n in nodes:
        nid = n if isinstance(n, str) else n["id"]
        if nid in chosen:
            if isinstance(n, str):
                new_nodes.append({"id": nid, "compromised": True})
            else:
                m = dict(n)
                m["compromised"] = True
                new_nodes.append(m)
        else:
            new_nodes.append(n)
    graph["nodes"] = new_nodes
    return graph


def _make(rng):
    """Blend ~35% small shallow tampered graphs (natural texture) with ~65%
    deep skip-edge DAG + sparse-chord SCC graphs (the careful-rank trap), then
    flag a fraction of keys compromised so the coupled clean_trust_depth varies."""
    g = _make_small(rng) if rng.random() < 0.35 else _make_deep(rng)
    return _inject_compromise(g, rng)


# --- tests ------------------------------------------------------------------

def test_surface():
    """analyze_trust_graph is importable and callable."""
    assert callable(analyze_trust_graph)


def test_simple_two_node_cycle():
    """A two-node mutual cross-signing pair forms one SCC of size 2 with both keys in_cycle."""
    g = {"nodes": ["a", "b"], "edges": [["a", "b"], ["b", "a"]], "roots": ["a"]}
    r = analyze_trust_graph(g)
    assert r["nodes"]["a"]["in_cycle"] is True
    assert r["nodes"]["b"]["in_cycle"] is True
    assert r["nodes"]["a"]["scc_rep"] == "a"
    assert r["nodes"]["b"]["scc_rep"] == "a"
    assert r["nodes"]["a"]["scc_size"] == 2
    assert r["summary"]["largest_cycle"] == 2
    assert r["summary"]["is_acyclic"] is False


def test_self_loop_is_cycle():
    """A self-loop makes a single key a cycle of scc_size 1 without ranking its successor below it."""
    g = {"nodes": ["x", "y"], "edges": [["x", "x"], ["x", "y"]], "roots": ["x"]}
    r = analyze_trust_graph(g)
    assert r["nodes"]["x"]["in_cycle"] is True
    assert r["nodes"]["x"]["scc_size"] == 1
    assert r["nodes"]["y"]["in_cycle"] is False
    # x is a self-loop (cyclic) so it is NOT an acyclic predecessor of y;
    # y therefore has no acyclic predecessor and ranks at layer 0.
    assert r["nodes"]["y"]["rank"] == 0
    assert r["summary"]["num_cycle_sccs"] == 1


def test_duplicate_ids_collapse():
    """A duplicated key id collapses to one vertex and does not inflate the SCC size or node count."""
    # "a" presented twice; edges merge; both occurrences report same verdict
    g = {"nodes": ["a", "b", "a"], "edges": [["a", "b"], ["b", "a"]], "roots": ["a"]}
    r = analyze_trust_graph(g)
    assert r["nodes"]["a"]["in_cycle"] is True
    assert r["nodes"]["a"]["scc_size"] == 2  # NOT 3 -- duplicate collapsed
    assert r["summary"]["num_sccs"] == 1


def test_absent_edge_does_not_close_cycle():
    """Edges to absent keys are dropped before cycle analysis and only the present-source one counts as dangling."""
    # b -> ABSENT and ABSENT -> a are dropped; no cycle forms
    g = {"nodes": ["a", "b"],
         "edges": [["a", "b"], ["b", "ghost"], ["ghost", "a"]], "roots": ["a"]}
    r = analyze_trust_graph(g)
    assert r["nodes"]["a"]["in_cycle"] is False
    assert r["nodes"]["b"]["in_cycle"] is False
    assert r["summary"]["is_acyclic"] is True
    # only the present-source -> absent-dst edge (b -> ghost) counts as
    # dangling; the absent-source edge (ghost -> a) is dropped entirely.
    assert r["summary"]["dangling_edges"] == 1


def test_unreachable_from_roots():
    """Keys not reachable from any present root are marked unreachable."""
    g = {"nodes": ["a", "b", "c"], "edges": [["a", "b"]], "roots": ["a"]}
    r = analyze_trust_graph(g)
    assert r["nodes"]["c"]["unreachable"] is True
    assert r["nodes"]["b"]["unreachable"] is False
    assert r["summary"]["num_unreachable"] == 1


def test_trust_depth_collapses_scc_to_one_level():
    """trust_depth collapses a cross-signing ring to one shared condensation level rather than the raw chain length."""
    # r -> a, and a<->b<->c form one cross-signing ring, c -> t.
    # Over the SCC condensation there are 3 super-nodes: {r}, {a,b,c}, {t}, in a
    # chain r -> {a,b,c} -> t. So trust_depth is r=0, a=b=c=1 (all share the one
    # ring depth), t=2 -- NOT the 4-long raw chain r->a->b->c->t.
    g = {"nodes": ["r", "a", "b", "c", "t"],
         "edges": [["r", "a"], ["a", "b"], ["b", "c"], ["c", "a"],
                   ["b", "a"], ["c", "b"], ["c", "t"]],
         "roots": ["r"]}
    r = analyze_trust_graph(g)
    nd = r["nodes"]
    assert nd["r"]["trust_depth"] == 0
    assert nd["a"]["trust_depth"] == 1
    assert nd["b"]["trust_depth"] == 1
    assert nd["c"]["trust_depth"] == 1
    assert nd["t"]["trust_depth"] == 2
    assert r["summary"]["max_trust_depth"] == 2
    # the ring members are cyclic (rank None) yet still carry an integer depth
    assert nd["a"]["in_cycle"] is True
    assert nd["a"]["rank"] is None
    assert isinstance(nd["a"]["trust_depth"], int)


def test_weighted_trust_depth_weights_cycle_by_size():
    """weighted_trust_depth adds each ring's full member count downstream, exceeding trust_depth+1 through a ring."""
    # Same graph as above: r -> a, a<->b<->c ring (size 3), c -> t.
    # The condensation is the chain {r}(size 1) -> {a,b,c}(size 3) -> {t}(size 1).
    # weighted_trust_depth accumulates the member count of each component on the
    # chain leading into a key (anchor contributes just its own size):
    #   {r}      : size 1, no predecessor              -> 1
    #   {a,b,c}  : size 3 + wtd({r})=1                 -> 4  (all three members)
    #   {t}      : size 1 + wtd({a,b,c})=4             -> 5
    # whereas the UNWEIGHTED one-level-per-component reading would give
    #   r=1, a=b=c=2, t=3  (trust_depth + 1) -- so the ring's size (3) is what
    # separates the two.
    g = {"nodes": ["r", "a", "b", "c", "t"],
         "edges": [["r", "a"], ["a", "b"], ["b", "c"], ["c", "a"],
                   ["b", "a"], ["c", "b"], ["c", "t"]],
         "roots": ["r"]}
    r = analyze_trust_graph(g)
    nd = r["nodes"]
    assert nd["r"]["weighted_trust_depth"] == 1
    assert nd["a"]["weighted_trust_depth"] == 4
    assert nd["b"]["weighted_trust_depth"] == 4
    assert nd["c"]["weighted_trust_depth"] == 4
    assert nd["t"]["weighted_trust_depth"] == 5
    assert r["summary"]["max_weighted_trust_depth"] == 5
    # plain trust_depth still collapses the ring to one level (1), so the two
    # fields genuinely differ by more than a constant on the ring + tail.
    assert nd["a"]["trust_depth"] == 1
    assert nd["t"]["trust_depth"] == 2
    # a purely acyclic chain (all components size 1) makes weighted == td + 1.
    g2 = {"nodes": ["p", "q", "z"],
          "edges": [["p", "q"], ["q", "z"]], "roots": ["p"]}
    r2 = analyze_trust_graph(g2)
    nd2 = r2["nodes"]
    for k in ("p", "q", "z"):
        assert nd2[k]["weighted_trust_depth"] == nd2[k]["trust_depth"] + 1


def test_fuzz_matches_independent_reference():
    """Over hundreds of tampered graphs, analyze_trust_graph matches the reference exactly and covers all edge cases."""
    rng = random.Random(20260625)
    cov = {"multi_scc": 0, "self_loop": 0, "dup": 0, "dangling": 0,
           "unreach": 0, "deep_rank": 0, "large_scc": 0,
           "deep_td": 0, "cyclic_td": 0, "td_ne_rank": 0,
           "wtd_gt_td_plus1": 0, "max_wtd_gt_max_td": 0,
           "has_compromised": 0, "fully_clean": 0, "ctd_lt_td": 0,
           "cyclic_revoked": 0, "deep_rootdist": 0, "rootdist_none": 0,
           "ring_on_root_path": 0}
    for case in range(400):
        g = _make(rng)
        got = analyze_trust_graph(g)
        ref = _ref(g)
        assert got == ref, f"case {case}: mismatch\nG={got}\nR={ref}"
        s = ref["summary"]
        if s["largest_cycle"] >= 2:
            cov["multi_scc"] += 1
        if any(isinstance(e, list) and e[0] == e[1] for e in g["edges"]):
            cov["self_loop"] += 1
        node_ids = [n if isinstance(n, str) else n["id"] for n in g["nodes"]]
        if len(node_ids) != len(set(node_ids)):
            cov["dup"] += 1
        if s["dangling_edges"] > 0:
            cov["dangling"] += 1
        if s["num_unreachable"] > 0:
            cov["unreach"] += 1
        ranks = [v["rank"] for v in ref["nodes"].values() if v["rank"] is not None]
        if ranks and max(ranks) >= 3:
            cov["deep_rank"] += 1   # deep skip-edge DAG region exercised
        if s["largest_cycle"] >= 6:
            cov["large_scc"] += 1   # sparse-chord SCC region exercised
        if s["max_trust_depth"] >= 2:
            cov["deep_td"] += 1     # multi-level condensation exercised
        for v in ref["nodes"].values():
            if v["in_cycle"] and v["trust_depth"] > 0:
                cov["cyclic_td"] += 1  # cyclic key carries a positive depth
                break
        for v in ref["nodes"].values():
            if v["rank"] is not None and v["trust_depth"] != v["rank"]:
                cov["td_ne_rank"] += 1  # condensation depth != Kahn rank
                break
        for v in ref["nodes"].values():
            # size weighting genuinely bites: weighted depth exceeds the
            # unweighted one-level-per-component reading (trust_depth + 1) --
            # only possible when a multi-key ring threads the chain.
            if v["weighted_trust_depth"] > v["trust_depth"] + 1:
                cov["wtd_gt_td_plus1"] += 1
                break
        if s["max_weighted_trust_depth"] > s["max_trust_depth"] + 1:
            cov["max_wtd_gt_max_td"] += 1
        # --- coupled clean_trust_depth coverage ---
        if s["num_compromised"] > 0:
            cov["has_compromised"] += 1
        else:
            cov["fully_clean"] += 1
        for v in ref["nodes"].values():
            # the revocation coupling genuinely bites: a key's clean depth is cut
            # BELOW its structural trust_depth because a chain leading into it runs
            # through a revoked component.
            if v["clean_trust_depth"] < v["trust_depth"]:
                cov["ctd_lt_td"] += 1
                break
        compromised_ids = {n["id"] for n in g["nodes"]
                           if not isinstance(n, str) and n.get("compromised")}
        for nid, v in ref["nodes"].items():
            if v["in_cycle"] and nid in compromised_ids:
                cov["cyclic_revoked"] += 1  # a revoked key inside a ring
                break
        # --- forward root_distance coverage ---
        if s["max_root_distance"] >= 3:
            cov["deep_rootdist"] += 1   # multi-hop condensed root chain exercised
        if any(v["root_distance"] is None for v in ref["nodes"].values()):
            cov["rootdist_none"] += 1   # a key unreachable from roots -> None
        for v in ref["nodes"].values():
            # a cyclic key that is itself a finite root_distance away from a root
            # means a ring sits on a shortest root path: the condensation collapse
            # (ring = one hop) genuinely bites versus the raw per-key BFS.
            if v["in_cycle"] and v["root_distance"] is not None \
                    and v["root_distance"] >= 1:
                cov["ring_on_root_path"] += 1
                break
    for k, v in cov.items():
        assert v > 0, f"edge case never exercised: {k} ({cov})"


def test_negative_control_naive_dfs_fails():
    """A naive DFS back-edge solver that does not collapse duplicate ids nor
    drop absent edges must DISAGREE with the oracle on the overlapping corpus,
    proving the suite genuinely requires correct SCC + edge-case handling."""
    rng = random.Random(999)
    diverged = 0
    total = 200
    for _ in range(total):
        g = _make(rng)
        if _naive(g) != analyze_trust_graph(g):
            diverged += 1
    assert diverged >= total * 0.30, (
        f"naive solver only diverged {diverged}/{total}; suite too weak")


def test_negative_control_careful_shortest_rank_fails():
    """The load-bearing difficulty control. A *careful* solver that gets SCCs,
    cycles, reachability and collapse all correct -- but layers `rank` by
    SHORTEST path (1 + min over non-cyclic predecessors) instead of the spec's
    LONGEST-path layering -- must DISAGREE with the oracle on a large fraction
    of the corpus. The deep skip-edge DAGs make longest-path rank differ from
    shortest-path rank; if this control's divergence collapses, the corpus has
    gone shallow and the milestone is no longer HARD for careful agents."""
    rng = random.Random(0xED25519)
    diverged = 0
    total = 300
    for _ in range(total):
        g = _make(rng)
        if _careful_shortest_rank(g) != analyze_trust_graph(g):
            diverged += 1
    assert diverged >= total * 0.30, (
        f"careful shortest-path-rank solver only diverged {diverged}/{total}; "
        "longest-vs-shortest rank trap too weak -- enrich the deep DAG corpus")


def test_negative_control_raw_trust_depth_fails():
    """The load-bearing difficulty control for `trust_depth`. A *careful* solver
    that gets SCCs, cycles, reachability AND the longest-path rank all correct --
    but computes trust_depth as the INTUITIVE RAW per-key longest predecessor
    chain instead of the spec's longest path over the SCC *condensation* (which
    collapses each cross-signing ring to ONE level) -- must DISAGREE with the
    oracle on a large fraction of the corpus. Wherever a trust chain runs through
    a ring, the raw per-key depth over-counts the intra-ring hops. If this
    control's divergence collapses, the condensation trap has gone shallow and
    the milestone is no longer HARD for careful agents."""
    rng = random.Random(0x7D)
    diverged = 0
    total = 300
    for _ in range(total):
        g = _make(rng)
        if _careful_raw_trust_depth(g) != analyze_trust_graph(g):
            diverged += 1
    assert diverged >= total * 0.30, (
        f"raw-trust-depth solver only diverged {diverged}/{total}; the SCC "
        "condensation trap is too weak -- enrich the cyclic-chain corpus")


def test_negative_control_unweighted_trust_depth_fails():
    """The load-bearing difficulty control for `weighted_trust_depth`. A *careful*
    solver that gets SCCs, cycles, reachability, the longest-path rank AND the
    SCC-condensation trust_depth ALL correct -- but computes
    weighted_trust_depth as the INTUITIVE UNWEIGHTED one-level-per-component
    chain (ignoring the size weighting that makes each component contribute its
    whole member count) -- must DISAGREE with the oracle on a large fraction of
    the corpus. Wherever a multi-key cross-signing ring sits on a trust chain,
    the size weighting inflates the spec value above this unweighted reading. If
    this control's divergence collapses, the size-weighting trap has gone shallow
    and the milestone is no longer HARD for careful agents."""
    rng = random.Random(0x5217E)
    diverged = 0
    total = 300
    for _ in range(total):
        g = _make(rng)
        if _unweighted_trust_depth(g) != analyze_trust_graph(g):
            diverged += 1
    assert diverged >= total * 0.30, (
        f"unweighted-trust-depth solver only diverged {diverged}/{total}; the "
        "size-weighting trap is too weak -- enrich the cyclic-chain corpus")


def test_negative_control_ignore_revocation_fails():
    """The load-bearing difficulty control for `clean_trust_depth`. A *careful*
    solver that gets SCCs, cycles, reachability, the longest-path rank, the
    SCC-condensation trust_depth AND the size-weighted weighted_trust_depth ALL
    correct -- but computes `clean_trust_depth` as a COPY of the structural
    trust_depth, i.e. it analyses the trust graph WITHOUT coupling it to the
    per-key compromise/revocation flags -- must DISAGREE with the oracle on a
    large fraction of the corpus. Wherever a trust chain runs through (or is
    rooted at) a revoked key, the spec severs the clean chain there and the depth
    drops below the structural reading. This forces an agent to COMPOSE the graph
    analysis with the key-revocation state rather than solving them
    independently; if this control's divergence collapses, the coupling has gone
    shallow and the milestone is no longer HARD for careful agents."""
    rng = random.Random(0xC1EA2)
    diverged = 0
    total = 300
    for _ in range(total):
        g = _make(rng)
        if _ignore_revocation(g) != analyze_trust_graph(g):
            diverged += 1
    assert diverged >= total * 0.30, (
        f"ignore-revocation solver only diverged {diverged}/{total}; the "
        "revocation coupling is too weak -- flag more chain-interior keys")


def test_negative_control_raw_bfs_root_distance_fails():
    """The load-bearing difficulty control for `root_distance`. A *careful* solver
    that gets SCCs, cycles, reachability, the longest-path rank, the
    SCC-condensation trust_depth, the size-weighted weighted_trust_depth AND the
    revocation-coupled clean_trust_depth ALL correct -- but measures
    `root_distance` by a RAW per-key BFS over individual present edges from the
    roots (one hop per key crossed) instead of the shortest path over the SCC
    *condensation* (where a whole cross-signing ring is ONE super-node and costs a
    single hop) -- must DISAGREE with the oracle on a large fraction of the
    corpus. Wherever the shortest root path threads or enters a multi-key ring,
    the raw per-key count over-states the condensed distance. This forces an agent
    to apply the SAME ring-collapsing condensation to the forward root distance
    that the depth fields use; if this control's divergence collapses, the
    condensation has gone shallow and the milestone is no longer HARD for careful
    agents."""
    rng = random.Random(0x500D15)
    diverged = 0
    total = 300
    for _ in range(total):
        g = _make(rng)
        if _raw_bfs_root_distance(g) != analyze_trust_graph(g):
            diverged += 1
    assert diverged >= total * 0.30, (
        f"raw-BFS root-distance solver only diverged {diverged}/{total}; the "
        "forward condensation trap is too weak -- enrich the ring-on-root-path "
        "corpus")


def test_root_distance_collapses_ring_to_one_hop():
    """root_distance collapses a ring to one forward condensation hop and is None for keys unreachable from roots."""
    # r -> a, the ring a <-> b <-> c, c -> t, with r the only root.
    # Over the condensation the chain of super-nodes is {r} -> {a,b,c} -> {t}, so
    # root_distance is r=0, a=b=c=1 (the whole ring is one hop from the root and
    # all three members share it), t=2 -- NOT the raw per-key BFS r=0, a=1, then
    # b/c=2 (a second hop inside the ring) and t=3.
    g = {"nodes": ["r", "a", "b", "c", "t"],
         "edges": [["r", "a"], ["a", "b"], ["b", "c"], ["c", "a"],
                   ["b", "a"], ["c", "b"], ["c", "t"]],
         "roots": ["r"]}
    nd = analyze_trust_graph(g)["nodes"]
    assert nd["r"]["root_distance"] == 0
    assert nd["a"]["root_distance"] == 1
    assert nd["b"]["root_distance"] == 1
    assert nd["c"]["root_distance"] == 1
    assert nd["t"]["root_distance"] == 2
    # a key unreachable from any present root has root_distance None (mirrors
    # `unreachable`), and a present root anchors at 0 even with no in-edges.
    g2 = {"nodes": ["r", "a", "iso"], "edges": [["r", "a"]], "roots": ["r"]}
    r2 = analyze_trust_graph(g2)
    nd2 = r2["nodes"]
    assert nd2["r"]["root_distance"] == 0
    assert nd2["a"]["root_distance"] == 1
    assert nd2["iso"]["root_distance"] is None
    assert nd2["iso"]["unreachable"] is True
    assert r2["summary"]["max_root_distance"] == 1


def test_clean_trust_depth_severs_at_revoked_component():
    """clean_trust_depth is cut at every compromised component while trust_depth and weighted_trust_depth stay unchanged."""
    # r -> a -> b -> c -> t, a clean acyclic chain: trust_depth = 0,1,2,3,4.
    # Mark `b` compromised. The condensation is unchanged, but clean_trust_depth
    # is CUT at b: r=0, a=1 (clean run r->a), b=0 (revoked component roots no
    # clean chain), c=0 and t=1 (the clean run restarts below b: c has no clean
    # predecessor so anchors at 0, t is one clean level past c). trust_depth is
    # untouched (still 0,1,2,3,4) and weighted_trust_depth too -- only the clean
    # field reacts to the revocation.
    g = {"nodes": ["r", "a", {"id": "b", "compromised": True}, "c", "t"],
         "edges": [["r", "a"], ["a", "b"], ["b", "c"], ["c", "t"]],
         "roots": ["r"]}
    res = analyze_trust_graph(g)
    nd = res["nodes"]
    assert [nd[k]["trust_depth"] for k in "rabct"] == [0, 1, 2, 3, 4]
    assert nd["r"]["clean_trust_depth"] == 0
    assert nd["a"]["clean_trust_depth"] == 1
    assert nd["b"]["clean_trust_depth"] == 0   # revoked: roots no clean chain
    assert nd["c"]["clean_trust_depth"] == 0   # chain cut at b, restarts at 0
    assert nd["t"]["clean_trust_depth"] == 1
    assert res["summary"]["max_clean_trust_depth"] == 1
    assert res["summary"]["num_compromised"] == 1
    # a fully clean variant: clean_trust_depth tracks trust_depth exactly.
    g2 = {"nodes": ["r", "a", "b", "c", "t"],
          "edges": [["r", "a"], ["a", "b"], ["b", "c"], ["c", "t"]],
          "roots": ["r"]}
    nd2 = analyze_trust_graph(g2)["nodes"]
    for k in "rabct":
        assert nd2[k]["clean_trust_depth"] == nd2[k]["trust_depth"]
    # a revoked key INSIDE a ring taints the whole component: ring members and
    # everything downstream of the ring get clean_trust_depth 0.
    g3 = {"nodes": ["r", "a", {"id": "x", "compromised": True}, "y", "t"],
          "edges": [["r", "a"], ["a", "x"], ["x", "y"], ["y", "x"], ["x", "t"]],
          "roots": ["r"]}
    nd3 = analyze_trust_graph(g3)["nodes"]
    assert nd3["a"]["clean_trust_depth"] == 1      # clean run r->a
    assert nd3["x"]["clean_trust_depth"] == 0      # revoked ring
    assert nd3["y"]["clean_trust_depth"] == 0      # same revoked ring
    assert nd3["t"]["clean_trust_depth"] == 0      # downstream of revoked ring
    # but the structural trust_depth still sees the ring as one clean level
    assert nd3["x"]["trust_depth"] == nd3["y"]["trust_depth"]
    assert nd3["t"]["trust_depth"] == nd3["x"]["trust_depth"] + 1
