from __future__ import annotations


def forward_topo(nodes: list[str], graph: dict[str, object]) -> list[str]:
    step_table = graph["nodes"]
    deps: dict[str, list[str]] = {}
    for node in nodes:
        deps[node] = [dep for dep in step_table[node]["depends"] if dep in nodes]
    incoming = {node: len(deps.get(node, [])) for node in nodes}
    children = {node: [] for node in nodes}
    for node, parents in deps.items():
        for parent in parents:
            if parent in children:
                children[parent].append(node)
    queue = sorted([node for node in nodes if incoming[node] == 0])
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for child in sorted(children.get(node, [])):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
                queue.sort()
    return order


def reverse_topo(nodes: list[str], graph: dict[str, object]) -> list[str]:
    return forward_topo(nodes, graph)
