def is_subset_strongly_connected(E, S):
    # בניית adjacency list רק עבור S
    adj = {v: [] for v in S}
    for u, v in E:
        if u in S and v in S:
            adj[u].append(v)

    outs = [v for v in S if v[2] == 1]
    ins = [v for v in S if v[2] == -1]

    reachable_ins = set()
    for out_v in outs:
        queue = [out_v]
        visited = set([out_v])
        while queue:
            node = queue.pop(0)
            for nbr in adj[node]:
                if nbr not in visited:
                    visited.add(nbr)
                    queue.append(nbr)
                    if nbr in ins:
                        reachable_ins.add(nbr)

    # כל ה-in חייבים להיות reachable לפחות מ-out אחד
    return all(in_v in reachable_ins for in_v in ins)

if __name__ == "__main__":
    # Example: small 2x2 grid
    # Vertices: (x, y, side)
    V = [
        (0, 0, -1), (0, 0, 1),
        (0, 1, -1), (0, 1, 1),
        (1, 0, -1), (1, 0, 1),
        (1, 1, -1), (1, 1, 1),
    ]

    # Edges (directed)
    E = [
        ((0, 0, 1), (0, 0, -1)),
        ((0, 0, 1), (1, 0, -1)),
        ((1, 0, 1), (1, 0, -1)),
        ((1, 0, 1), (1, 1, -1)),
        ((0, 1, 1), (0, 1, -1)),
        ((0, 1, 1), (1, 1, -1)),
        ((1, 1, 1), (1, 1, -1)),
        ((0, 0, 1), (0, 1, -1)),  # cross edge
    ]

    # Subset of vertices to check connectivity
    S = [(0, 0, -1), (1, 0, -1), (0, 1, -1), (1, 1, -1),
         (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]

    result = is_subset_strongly_connected(E, S)
    print(f"Subset strongly connected? {result}")

    # Test with a disconnected subset
    S2 = [(0, 0, -1), (1, 1, -1), (0, 0, 1), (1, 1, 1)]
    result2 = is_subset_strongly_connected(E, S2)
    print(f"Disconnected subset strongly connected? {result2}")
