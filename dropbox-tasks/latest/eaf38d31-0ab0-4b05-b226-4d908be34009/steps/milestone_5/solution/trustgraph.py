"""Milestone 5 reference --- cross-signing trust-graph cycle analysis.

A certificate-transparency monitor is handed a *presented* cross-signing trust
graph: nodes are signing keys (each identified by a string id) and a directed
edge ``a -> b`` records the assertion that key *a* is cross-signed (vouched for)
by key *b* --- i.e. *b* asserts authority over *a*.  The graph may have been
tampered with in transit, so it can contain self-asserted authority
(self-loops), mutual cross-signing rings (cycles), references to keys that are
not actually present (dangling edges), and the SAME key id presented more than
once (which must collapse to a single vertex whose incident edges merge).

The monitor must, for every presented node, decide a fully specified verdict:
whether the key sits inside a trust *cycle* (a strongly-connected component of
size >= 2, or a self-loop), the canonical representative of its trust component,
whether it is *unreachable* from the declared trust-root anchors, --- for keys
that are NOT in any cycle --- a trust *rank* (its layer in a Kahn topological
layering of the acyclic part), a *trust depth* (the longest chain of trust
components leading into the key, computed over the SCC condensation, defined for
cyclic keys too), and a *weighted trust depth* (the same condensation chain but
accumulating each component's MEMBER COUNT rather than one level per component,
so a large cross-signing ring contributes its full size to every component
downstream of it), and a *clean trust depth* (the same condensation chain but
counting only trust components in which NO member key has been flagged
compromised, so any chain of trust is severed the moment it would have to pass
through a revoked key).
"""

from collections import defaultdict, deque


def _normalize(graph):
    """Collapse duplicate node ids to one vertex; merge their edges.

    Returns (nodes, adj, present, dangling, compromised) where *nodes* is the
    de-duplicated list of node ids in first-appearance order, *adj* maps each
    present node to the set of present successors (edges to absent nodes are
    dropped), *present* is the set of node ids that appear at least once,
    *dangling* is the set of (src, dst) edges that pointed at an absent node,
    and *compromised* is the set of present node ids flagged compromised (a node
    is compromised iff ANY of its presented occurrences carries a truthy
    ``compromised`` field; a bare-string node is never compromised).
    """
    nodes = []
    present = set()
    compromised = set()
    for n in graph.get("nodes", []):
        if isinstance(n, str):
            nid = n
        else:
            nid = n.get("id")
            if n.get("compromised"):
                compromised.add(nid)
        if nid not in present:
            present.add(nid)
            nodes.append(nid)
    raw_adj = defaultdict(set)
    dangling = set()
    for e in graph.get("edges", []):
        if isinstance(e, (list, tuple)):
            src, dst = e[0], e[1]
        else:
            src, dst = e.get("src"), e.get("dst")
        if src not in present:
            continue
        if dst not in present:
            dangling.add((src, dst))
            continue
        raw_adj[src].add(dst)
    adj = {n: set(raw_adj.get(n, set())) for n in nodes}
    compromised &= present
    return nodes, adj, present, dangling, compromised


def _sccs(nodes, adj):
    """Strongly-connected components via mutual reachability (iterative Tarjan).

    Returns a dict mapping each node to a frozenset of the members of its SCC.
    """
    index = {}
    low = {}
    on_stack = {}
    stack = []
    comp = {}
    counter = [0]

    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(sorted(adj[root])))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack[root] = True
        while work:
            node, it = work[-1]
            advanced = False
            for succ in it:
                if succ not in index:
                    index[succ] = low[succ] = counter[0]
                    counter[0] += 1
                    stack.append(succ)
                    on_stack[succ] = True
                    work.append((succ, iter(sorted(adj[succ]))))
                    advanced = True
                    break
                if on_stack.get(succ):
                    low[node] = min(low[node], index[succ])
            if advanced:
                continue
            if low[node] == index[node]:
                members = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    members.append(w)
                    if w == node:
                        break
                fs = frozenset(members)
                for m in members:
                    comp[m] = fs
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return comp


def _reachable_from_roots(adj, roots, present):
    """Set of present nodes reachable from any present declared root."""
    seen = set()
    frontier = [r for r in roots if r in present]
    seen.update(frontier)
    while frontier:
        cur = frontier.pop()
        for succ in adj.get(cur, ()):  # successors are already present-only
            if succ not in seen:
                seen.add(succ)
                frontier.append(succ)
    return seen


def _kahn_rank(nodes, adj, comp):
    """Kahn topological layering restricted to acyclic nodes.

    Acyclic nodes (SCC size 1 and no self-loop) get an integer rank; cyclic
    nodes get None.  A node's rank is 1 + the max rank of its acyclic
    predecessors, or 0 if it has no acyclic predecessor.
    """
    acyclic = set()
    for n in nodes:
        members = comp[n]
        is_cycle = len(members) >= 2 or (n in adj.get(n, set()))
        if not is_cycle:
            acyclic.add(n)
    preds = defaultdict(set)
    for n in nodes:
        for s in adj[n]:
            preds[s].add(n)
    rank = {}

    def compute(n):
        if n in rank:
            return rank[n]
        rank[n] = 0  # guard against pathological recursion
        best = 0
        for p in preds.get(n, ()):
            if p in acyclic and p != n:
                best = max(best, compute(p) + 1)
        rank[n] = best
        return best

    for n in nodes:
        if n in acyclic:
            compute(n)
    return {n: rank.get(n) for n in nodes}


def _condensation_depth(nodes, adj, comp):
    """Longest chain over the SCC *condensation*.

    Collapse every strongly-connected component to a single super-node keyed by
    its representative ``min(members)``.  Build the DAG of super-nodes using only
    DISTINCT *cross-component* edges (an edge whose endpoints sit in different
    components); intra-component edges and self-loops are ignored.  The depth of
    a super-node is ``1 + the maximum depth of any super-node that has an edge
    into it`` (a super-node with no cross-component predecessor anchors at ``0``)
    --- i.e. the longest path of super-nodes ending at it.  Every member of a
    component SHARES that one depth.  Unlike ``rank`` this is defined for cyclic
    keys too.  Returns a per-node dict of integer depths.
    """
    rep_of = {n: min(comp[n]) for n in nodes}
    reps = []
    seen_rep = set()
    for n in nodes:
        r = rep_of[n]
        if r not in seen_rep:
            seen_rep.add(r)
            reps.append(r)
    # distinct cross-component edges between super-nodes (rep -> rep)
    rep_preds = defaultdict(set)
    for n in nodes:
        rn = rep_of[n]
        for s in adj[n]:
            rs = rep_of[s]
            if rs != rn:
                rep_preds[rs].add(rn)
    depth = {}

    def compute(r):
        if r in depth:
            return depth[r]
        depth[r] = 0  # guard against pathological recursion (DAG, but be safe)
        best = 0
        for p in rep_preds.get(r, ()):
            if p != r:
                best = max(best, compute(p) + 1)
        depth[r] = best
        return best

    for r in reps:
        compute(r)
    return {n: depth[rep_of[n]] for n in nodes}


def _condensation_weighted_depth(nodes, adj, comp):
    """Size-weighted longest chain over the SCC *condensation*.

    Identical condensation to ``_condensation_depth`` (collapse every
    strongly-connected component to a super-node keyed by ``min(members)``, keep
    only DISTINCT cross-component edges), but instead of every super-node adding
    exactly ``1`` level, each super-node contributes its component's MEMBER COUNT
    (``scc_size``).  The weighted depth of a super-node is its own component size
    PLUS the maximum weighted depth of any super-node with a cross-component edge
    into it; a super-node with no cross-component predecessor anchors at just its
    own size (so the value is ``>= 1`` for every key, never ``0``).  Every member
    of a component SHARES that one weighted depth.  A multi-key cross-signing ring
    therefore adds its full size — not a single level — to every component reached
    through it, which is what distinguishes this from the unweighted
    ``trust_depth``.  Defined for cyclic keys too.  Returns a per-node dict.
    """
    rep_of = {n: min(comp[n]) for n in nodes}
    size_of = {}
    reps = []
    seen_rep = set()
    for n in nodes:
        r = rep_of[n]
        if r not in seen_rep:
            seen_rep.add(r)
            reps.append(r)
            size_of[r] = len(comp[n])
    rep_preds = defaultdict(set)
    for n in nodes:
        rn = rep_of[n]
        for s in adj[n]:
            rs = rep_of[s]
            if rs != rn:
                rep_preds[rs].add(rn)
    wdepth = {}

    def compute(r):
        if r in wdepth:
            return wdepth[r]
        wdepth[r] = size_of[r]  # guard against pathological recursion
        best = 0
        for p in rep_preds.get(r, ()):
            if p != r:
                best = max(best, compute(p))
        wdepth[r] = size_of[r] + best
        return wdepth[r]

    for r in reps:
        compute(r)
    return {n: wdepth[rep_of[n]] for n in nodes}


def _condensation_clean_depth(nodes, adj, comp, compromised):
    """Longest clean chain over the SCC *condensation*, severed at revoked keys.

    Uses the SAME condensation as ``_condensation_depth`` (collapse every
    strongly-connected component to a super-node keyed by ``min(members)``, keep
    only DISTINCT cross-component edges), but a trust component is *clean* iff
    NONE of its member keys is flagged compromised (one revoked member taints the
    whole super-node).  ``clean_trust_depth`` is the longest path over CLEAN
    super-nodes only:

    * a compromised (dirty) component's members get ``0`` — a revoked key roots no
      clean chain;
    * a clean super-node's depth is ``1 + the maximum clean depth of any *clean*
      super-node with a cross-component edge into it``; cross-component edges
      coming from a dirty super-node are IGNORED (the chain is cut there), so a
      clean component reached only through revoked keys anchors back at ``0``;
    * every member of a component SHARES that one clean depth.

    Thus a trust chain contributes to ``clean_trust_depth`` only along its longest
    *uninterrupted* run of non-revoked components; the moment it would pass through
    a compromised component the accumulated depth is discarded and counting
    restarts downstream.  Defined for cyclic keys too.  Returns a per-node dict.
    """
    rep_of = {n: min(comp[n]) for n in nodes}
    reps = []
    seen_rep = set()
    dirty_rep = set()
    for n in nodes:
        r = rep_of[n]
        if r not in seen_rep:
            seen_rep.add(r)
            reps.append(r)
        if n in compromised:
            dirty_rep.add(r)
    rep_preds = defaultdict(set)
    for n in nodes:
        rn = rep_of[n]
        for s in adj[n]:
            rs = rep_of[s]
            if rs != rn:
                rep_preds[rs].add(rn)
    depth = {}

    def compute(r):
        if r in depth:
            return depth[r]
        if r in dirty_rep:
            depth[r] = 0  # a revoked component roots no clean chain
            return 0
        depth[r] = 0  # guard against pathological recursion (DAG, but be safe)
        best = 0
        for p in rep_preds.get(r, ()):
            if p != r and p not in dirty_rep:
                best = max(best, compute(p) + 1)
        depth[r] = best
        return best

    for r in reps:
        compute(r)
    return {n: depth[rep_of[n]] for n in nodes}


def _condensation_root_distance(nodes, adj, comp, roots, present):
    """Forward shortest cross-component hop distance from the trust anchors.

    Measures how many trust *components* a key sits **below** the declared roots,
    travelling FORWARD along cross-signing edges (the opposite direction to the
    ``*_depth`` fields, which look at chains leading INTO a key).  Built over the
    SAME SCC condensation as ``trust_depth``: collapse every strongly-connected
    component to a super-node keyed by ``min(members)`` and keep only DISTINCT
    cross-component edges; intra-component edges and self-loops are ignored.

    A super-node that CONTAINS a present declared root anchors at ``0``; any other
    super-node's distance is ``1 + the minimum distance of any super-node with a
    cross-component edge INTO it`` (a *shortest* path over super-nodes from the
    roots, not a longest one).  Because a whole cross-signing ring is one
    super-node, every member of the ring shares the single distance and crossing
    the ring costs ONE hop, not one per member.  A key whose component is not
    reachable from any present root's component gets ``None`` (mirroring
    ``unreachable``).  Every member of a component SHARES the value.
    """
    rep_of = {n: min(comp[n]) for n in nodes}
    rep_succ = defaultdict(set)
    for n in nodes:
        rn = rep_of[n]
        for s in adj[n]:
            rs = rep_of[s]
            if rs != rn:
                rep_succ[rn].add(rs)
    dist = {}
    frontier = deque()
    for r in roots:
        if r in present:
            rr = rep_of[r]
            if rr not in dist:
                dist[rr] = 0
                frontier.append(rr)
    while frontier:
        cur = frontier.popleft()
        for nxt in rep_succ.get(cur, ()):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                frontier.append(nxt)
    return {n: dist.get(rep_of[n]) for n in nodes}


def analyze_trust_graph(graph):
    """Return the full per-node trust verdict plus a summary.

    Duplicate node ids collapse to one vertex; every occurrence reports the same
    verdict.  Roots are read from ``graph["roots"]`` (default empty).
    """
    nodes, adj, present, dangling, compromised = _normalize(graph)
    comp = _sccs(nodes, adj)
    roots = graph.get("roots", [])
    reachable = _reachable_from_roots(adj, roots, present)
    ranks = _kahn_rank(nodes, adj, comp)
    depths = _condensation_depth(nodes, adj, comp)
    wdepths = _condensation_weighted_depth(nodes, adj, comp)
    cdepths = _condensation_clean_depth(nodes, adj, comp, compromised)
    rdists = _condensation_root_distance(nodes, adj, comp, roots, present)

    seen_comp = set()
    num_sccs = 0
    num_cycle_sccs = 0
    largest_cycle = 0
    node_out = {}
    for n in nodes:
        members = comp[n]
        if members not in seen_comp:
            seen_comp.add(members)
            num_sccs += 1
            self_loop = any(m in adj.get(m, set()) for m in members)
            if len(members) >= 2 or self_loop:
                num_cycle_sccs += 1
                largest_cycle = max(largest_cycle, len(members))
        is_cycle = len(members) >= 2 or (n in adj.get(n, set()))
        node_out[n] = {
            "in_cycle": is_cycle,
            "scc_rep": min(members),
            "scc_size": len(members),
            "unreachable": n not in reachable,
            "rank": None if is_cycle else ranks[n],
            "trust_depth": depths[n],
            "weighted_trust_depth": wdepths[n],
            "clean_trust_depth": cdepths[n],
            "root_distance": rdists[n],
        }

    num_unreachable = sum(1 for n in nodes if n not in reachable)
    max_trust_depth = max((depths[n] for n in nodes), default=0)
    max_weighted_trust_depth = max((wdepths[n] for n in nodes), default=0)
    max_clean_trust_depth = max((cdepths[n] for n in nodes), default=0)
    _finite_rd = [rdists[n] for n in nodes if rdists[n] is not None]
    max_root_distance = max(_finite_rd, default=0)
    num_compromised = len(compromised)
    return {
        "nodes": node_out,
        "summary": {
            "num_sccs": num_sccs,
            "num_cycle_sccs": num_cycle_sccs,
            "largest_cycle": largest_cycle,
            "is_acyclic": num_cycle_sccs == 0,
            "num_unreachable": num_unreachable,
            "dangling_edges": len(dangling),
            "max_trust_depth": max_trust_depth,
            "max_weighted_trust_depth": max_weighted_trust_depth,
            "max_clean_trust_depth": max_clean_trust_depth,
            "max_root_distance": max_root_distance,
            "num_compromised": num_compromised,
        },
    }
