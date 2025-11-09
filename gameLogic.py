from settings import Settings


class Board:
    """
    The Board class represents the underlying game structure.
    It stores:
      - the grid of points (nodes)
      - the available and owned edges
      - conquered and original dots for each player
    """

    def __init__(self, rows, cols, players_original_dots):
        self.rows = rows
        self.cols = cols

        # 2D visual representation of the board (for debugging / printing)
        self.board = [["." for _ in range(cols)] for _ in range(rows)]

        # All nodes (each with "in" and "out" states)
        self.all_points = [(x, y, i) for x in range(cols) for y in range(rows) for i in [-1, 1]]

        # Store original player starting positions (duplicated with in/out states)
        self.players_original_dots = {Settings.PLAYER1: [], Settings.PLAYER2: []}
        for player, dots in players_original_dots.items():
            for x, y in dots:
                self.players_original_dots[player].append((x, y, -1))
                self.players_original_dots[player].append((x, y, 1))

        # Initialize empty dots (unclaimed points)
        self.empty_dots = [(x, y) for x, y, _ in self.all_points.copy()]
        self.conquer_dots = {Settings.PLAYER1: [], Settings.PLAYER2: []}
        self.available_pairs = set()

        # Create default internal edges for all vertices (between in and out states)
        default_edges = {
            ((x, y, -1), (x, y, 1)) for x in range(cols) for y in range(rows)
        }.union({
            ((x, y, 1), (x, y, -1)) for x in range(cols) for y in range(rows)
        })
        self.players_pairs = {player: default_edges.copy() for player in [Settings.PLAYER1, Settings.PLAYER2]}

        # Remove internal edges that belong to conquered (initial) opponent dots
        for player in [Settings.PLAYER1, Settings.PLAYER2]:
            opponent = Settings.PLAYER1 if player == Settings.PLAYER2 else Settings.PLAYER2
            opponent_xy = {(x, y) for x, y, _ in self.players_original_dots[opponent]}

            for x, y in opponent_xy:
                self.conquer_dot(opponent, (x, y))
                for edge in [((x, y, -1), (x, y, 1)), ((x, y, 1), (x, y, -1))]:
                    if edge in self.players_pairs[player]:
                        self.players_pairs[player].remove(edge)

        # Place player symbols on the visual board (for debugging)
        for player, dots in self.players_original_dots.items():
            for x, y, _ in dots:
                self.board[y][x] = player

        # Generate all possible orthogonal edge pairs (up, down, left, right)
        for y in range(rows):
            for x in range(cols):
                p1_out = (x, y, 1)
                p1_in = (x, y, -1)
                neighbors = [
                    (x - 1, y),  # left
                    (x + 1, y),  # right
                    (x, y - 1),  # up
                    (x, y + 1),  # down
                ]
                for nx, ny in neighbors:
                    if 0 <= nx < cols and 0 <= ny < rows:
                        self.available_pairs.add((p1_out, (nx, ny, -1)))
                        self.available_pairs.add(((nx, ny, 1), p1_in))

    # --------------------------
    # CONQUERING MECHANICS
    # --------------------------

    def conquer_dot(self, player, dot):
        """
        When a dot is conquered:
          - remove the opponent's internal edge for that point
          - add it to the conquer list
          - remove it from empty dots
        """
        opponent = Settings.PLAYER1 if player == Settings.PLAYER2 else Settings.PLAYER2
        x, y = dot

        # Remove the internal "in↔out" edges from the opponent
        for edge in [((x, y, -1), (x, y, 1)), ((x, y, 1), (x, y, -1))]:
            if edge in self.players_pairs[opponent]:
                self.players_pairs[opponent].remove(edge)

        # Update conquered / empty sets
        if dot not in self.conquer_dots[player]:
            self.conquer_dots[player].append(dot)
        if dot in self.empty_dots:
            self.empty_dots.remove(dot)

    def unconquer_dot(self, player, dot):
        """
        Reverts a conquered dot (used for rollback during legality checks):
          - removes from conquer list
          - restores to empty dots
          - restores the opponent's internal edge
        """
        opponent = Settings.PLAYER1 if player == Settings.PLAYER2 else Settings.PLAYER2
        x, y = dot

        if dot in self.conquer_dots[player]:
            self.conquer_dots[player].remove(dot)

        if dot not in self.empty_dots:
            self.empty_dots.append(dot)

        restored_edges = [((x, y, -1), (x, y, 1)), ((x, y, 1), (x, y, -1))]
        for edge in restored_edges:
            self.players_pairs[opponent].add(edge)

    # --------------------------
    # DEBUG PRINTING
    # --------------------------

    def print_board(self):
        """Prints a readable debug view of the board’s state."""
        print("\n=== BOARD STATE ===")
        print(f"Board size: {self.cols} x {self.rows}\n")

        # Display ownership of vertices
        print("Vertices:")
        for y in range(self.rows):
            for x in range(self.cols):
                owner = "."
                if (x, y, -1) in self.players_original_dots[Settings.PLAYER1]:
                    owner = Settings.PLAYER1
                elif (x, y, -1) in self.players_original_dots[Settings.PLAYER2]:
                    owner = Settings.PLAYER2
                print(owner, end="  ")
            print()
        print()

        # Display directed edges per player
        print("Directed Edges (by player):")
        for player, edges in self.players_pairs.items():
            print(f"\n{player}'s edges ({len(edges)} total):")
            for u, v in sorted(edges):
                print(f"  {u} -> {v}")

        print(f"\nAvailable pairs ({len(self.available_pairs)}):")
        for u, v in sorted(self.available_pairs):
            print(f"  {u} -> {v}")
        print("\n====================\n")


# -------------------------------------------------
# GAME LOGIC: RULE ENFORCEMENT & TURN MANAGEMENT
# -------------------------------------------------
class GameLogic:
    def __init__(self, rows, cols, players_original_dots):
        self.board_obj = Board(rows, cols, players_original_dots)
        self.turn = Settings.PLAYER1

    # --------------------------
    # TURN MANAGEMENT
    # --------------------------

    def next_turn(self):
        """Returns the next player's ID."""
        return Settings.PLAYER2 if self.turn == Settings.PLAYER1 else Settings.PLAYER1

    # --------------------------
    # GRAPH CONNECTIVITY CHECKS
    # --------------------------

    def check_all_outs_reach_all_ins(self, V, E, S):
        """
        Checks strong connectivity for the player's subgraph.
        Every OUT node must be able to reach all IN nodes.
        Uses BFS on the entire graph (V, E).
        """
        adj = {v: [] for v in V}
        for u, v in E:
            adj.setdefault(u, []).append(v)

        outs = [v for v in S if v[2] == 1]
        ins = [v for v in S if v[2] == -1]

        if not ins:
            return True
        if not outs:
            return False

        for out_v in outs:
            visited = set()
            queue = [out_v]

            while queue:
                node = queue.pop(0)
                if node not in visited:
                    visited.add(node)
                    for nbr in adj.get(node, []):
                        if nbr not in visited:
                            queue.append(nbr)

            if not all(in_v in visited for in_v in ins):
                return False

        return True

    # --------------------------
    # WIN CONDITION
    # --------------------------

    def check_win(self):
        """Checks if any player has achieved full connectivity."""
        b = self.board_obj
        if self.check_all_outs_reach_all_ins(b.all_points, b.players_pairs[Settings.PLAYER1],
                                             b.players_original_dots[Settings.PLAYER1]):
            return Settings.PLAYER1
        if self.check_all_outs_reach_all_ins(b.all_points, b.players_pairs[Settings.PLAYER2],
                                             b.players_original_dots[Settings.PLAYER2]):
            return Settings.PLAYER2
        return None

    # --------------------------
    # CONQUER RULE VALIDATION
    # --------------------------

    def check_conquer_input(self, dot):
        """
        Determines if a dot can be legally conquered by the current player:
          1. Dot must be within bounds.
          2. Dot must not already be conquered.
          3. Player must have ≥2 edges connected to this dot.
          4. Conquering must not completely block the opponent.
        """
        x, y = dot
        b = self.board_obj

        if not (0 <= x < b.cols and 0 <= y < b.rows):
            return False

        if (x, y) in b.conquer_dots[Settings.PLAYER1] + b.conquer_dots[Settings.PLAYER2]:
            return False

        # Must be connected by at least two of the player's edges
        connected_edges = [e for e in b.players_pairs[self.turn] if (x, y, -1) in e]
        for internal in [((x, y, 1), (x, y, -1)), ((x, y, -1), (x, y, 1))]:
            if internal in connected_edges:
                connected_edges.remove(internal)

        if len(connected_edges) < 2:
            return False

        # Check blocking rule (simulate conquer, then undo)
        n_turn = self.next_turn()
        b.conquer_dot(self.turn, (x, y))
        if not self.check_all_outs_reach_all_ins(
            b.all_points,
            b.players_pairs[n_turn].union(b.available_pairs),
            b.players_original_dots[n_turn]
        ):
            b.unconquer_dot(self.turn, (x, y))
            return False

        b.unconquer_dot(self.turn, (x, y))
        return True

    # --------------------------
    # EDGE RULE VALIDATION
    # --------------------------

    def check_edge_input(self, point1, point2):
        """
        Determines if an edge between two nodes is a legal move:
          - Must be inside bounds.
          - Must exist in available pairs.
          - Must not fully block opponent (unless it wins).
        """
        x1, y1, _ = point1
        x2, y2, _ = point2
        b = self.board_obj

        if not (0 <= x1 < b.cols and 0 <= y1 < b.rows and 0 <= x2 < b.cols and 0 <= y2 < b.rows):
            return False

        if ((x1, y1, 1), (x2, y2, -1)) not in b.available_pairs and ((x2, y2, 1), (x1, y1, -1)) not in b.available_pairs:
            return False

        # Allow if it creates immediate win
        new_edges = {((x1, y1, 1), (x2, y2, -1)), ((x2, y2, 1), (x1, y1, -1))}
        if self.check_all_outs_reach_all_ins(
            b.all_points, b.players_pairs[self.turn].union(new_edges), b.players_original_dots[self.turn]
        ):
            return True

        # Otherwise, reject if it completely blocks the opponent
        n_turn = self.next_turn()
        other_edges = (
            b.available_pairs.difference(new_edges)
        ).union(b.players_pairs[n_turn])

        if not self.check_all_outs_reach_all_ins(b.all_points, other_edges, b.players_original_dots[n_turn]):
            return False

        return True

    # --------------------------
    # MOVE EXECUTION
    # --------------------------

    def make_move(self, edge):
        """Adds a new edge to the current player's graph and removes it from available pairs."""
        first_point, second_point = edge

        edg_1 = ((first_point[0], first_point[1], 1), (second_point[0], second_point[1], -1))
        edg_2 = ((second_point[0], second_point[1], 1), (first_point[0], first_point[1], -1))

        self.board_obj.players_pairs[self.turn].add(edg_1)
        self.board_obj.players_pairs[self.turn].add(edg_2)

        self.board_obj.available_pairs.discard(edg_1)
        self.board_obj.available_pairs.discard(edg_2)