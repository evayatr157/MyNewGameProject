gameLogic.py:

from settings import Settings

class Board:
    def __init__(self, rows, cols, players_original_dots):
        self.rows = rows
        self.cols = cols
        # Initialize empty board
        self.board = [["." for _ in range(cols)] for _ in range(rows)]
        # all_points = all coordinates (x, y)
        self.all_points = [(x, y, i) for x in range(cols) for y in range(rows) for i in [-1, 1]]  # -1 is in, 1 is out
        self.players_original_dots = {Settings.PLAYER1: [], Settings.PLAYER2: []}
        for player, dots in players_original_dots.items():
            for x, y in dots:
                self.players_original_dots[player].append((x, y, -1))
                self.players_original_dots[player].append((x, y, 1))

        self.empty_dots = [(x, y) for x, y, i in self.all_points.copy()]
        self.conquer_dots = {Settings.PLAYER1: [], Settings.PLAYER2: []}
        self.available_pairs = set()

        default_edges = {((x, y, -1), (x, y, 1)) for x in range(cols) for y in range(rows)}.union(
            {((x, y, 1), (x, y, -1)) for x in range(cols) for y in range(rows)})
        self.players_pairs = {player: default_edges.copy() for player in [Settings.PLAYER1, Settings.PLAYER2]}

        for player in [Settings.PLAYER1, Settings.PLAYER2]:
            opponent = Settings.PLAYER1 if player == Settings.PLAYER2 else Settings.PLAYER2
            # Get unique (x,y) positions of opponent
            opponent_xy = {(x, y) for x, y, _ in self.players_original_dots[opponent]}
            for x, y in opponent_xy:
                self.conquer_dot(opponent, (x, y))
                for edge in [((x, y, -1), (x, y, 1)), ((x, y, 1), (x, y, -1))]:
                    if edge in self.players_pairs[player]:
                        self.players_pairs[player].remove(edge)

        # Place initial player dots
        for player, dots in self.players_original_dots.items():
            for x, y, trash in dots:  # x, y order
                self.board[y][x] = player

        # Generate all available orthogonal pairs
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

    def conquer_dot(self, player, dot):
        opponent = Settings.PLAYER1 if player == Settings.PLAYER2 else Settings.PLAYER2
        x, y = dot
        for edge in [((x, y, -1), (x, y, 1)), ((x, y, 1), (x, y, -1))]:
            if edge in self.players_pairs[opponent]:
                self.players_pairs[opponent].remove(edge)

        if dot not in self.conquer_dots[player]:
            self.conquer_dots[player].append(dot)
        if dot in self.empty_dots:
            self.empty_dots.remove(dot)

    def unconquer_dot(self, player, dot):
        opponent = Settings.PLAYER1 if player == Settings.PLAYER2 else Settings.PLAYER2
        x, y = dot

        # Remove the dot from the player's conquered list (if exists)
        if dot in self.conquer_dots[player]:
            self.conquer_dots[player].remove(dot)

        # Add it back to the empty dots pool
        if dot not in self.empty_dots:
            self.empty_dots.append(dot)

        # Restore the internal edge between (in) and (out) for the opponent
        restored_edges = [((x, y, -1), (x, y, 1)), ((x, y, 1), (x, y, -1))]
        for edge in restored_edges:
            self.players_pairs[opponent].add(edge)

    def print_board(self):
        """
        Prints a detailed representation of the board:
        - Each player's edges (with direction)
        - The current state of each vertex (who occupies it)
        """

        print("\n=== BOARD STATE ===")
        print(f"Board size: {self.cols} x {self.rows}\n")

        # Show vertex ownership
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

        # Show edges per player
        print("Directed Edges (by player):")
        for player, edges in self.players_pairs.items():
            print(f"\n{player}'s edges ({len(edges)} total):")
            for u, v in sorted(edges):
                print(f"  {u} -> {v}")

        # Optionally: show available pairs for debugging
        print(f"\nAvailable pairs ({len(self.available_pairs)}):")
        for u, v in sorted(self.available_pairs):
            print(f"  {u} -> {v}")

        print("\n====================\n")

class GameLogic:
    def __init__(self, rows, cols, players_original_dots):
        self.board_obj = Board(rows, cols, players_original_dots)
        self.turn = Settings.PLAYER1

    def next_turn(self):
        return Settings.PLAYER2 if self.turn == Settings.PLAYER1 else Settings.PLAYER1

    def check_all_outs_reach_all_ins(self, V, E, S):
        # Build full adjacency list
        adj = {v: [] for v in V}
        for u, v in E:
            adj.setdefault(u, []).append(v)

        outs = [v for v in S if v[2] == 1]
        ins = [v for v in S if v[2] == -1]

        # Edge cases
        if not ins:
            return True
        if not outs:
            return False

        # Each out must reach all ins (possibly via vertices outside S)
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

            # Check if all ins are reachable from this out
            if not all(in_v in visited for in_v in ins):
                return False

        return True

    def check_win(self):
        b = self.board_obj
        if self.check_all_outs_reach_all_ins(b.all_points, b.players_pairs[Settings.PLAYER1],
                                             b.players_original_dots[Settings.PLAYER1]):
            return Settings.PLAYER1
        if self.check_all_outs_reach_all_ins(b.all_points, b.players_pairs[Settings.PLAYER2],
                                             b.players_original_dots[Settings.PLAYER2]):
            return Settings.PLAYER2
        return None

    def check_conquer_input(self, dot):
        x, y = dot
        b = self.board_obj

        # --- Check bounds ---
        if not (0 <= x < b.cols and 0 <= y < b.rows):
            # print("Error: Coordinates out of board range.")
            return False

        # --- Check availability ---
        # The point must not already be conquered by any player
        if (x, y) in b.conquer_dots[Settings.PLAYER1] + b.conquer_dots[Settings.PLAYER2]:
            return False

        # --- Check that this dot is connected by at least two edges of the same player ---
        connected_edges = [e for e in b.players_pairs[self.turn] if (x, y, -1) in e]
        if ((x, y, 1), (x, y, -1)) in connected_edges:
            connected_edges.remove(((x, y, 1), (x, y, -1)))
        if ((x, y, -1), (x, y, 1)) in connected_edges:
            connected_edges.remove(((x, y, -1), (x, y, 1)))
        if len(connected_edges) < 2:
            # print("Error: You must have at least two edges connected to this dot to conquer it.")
            return False

        # --- Check that conquering doesn’t block the opponent completely ---
        n_turn = self.next_turn()
        b.conquer_dot(self.turn, (x, y))
        if not self.check_all_outs_reach_all_ins(b.all_points, b.players_pairs[n_turn].union(b.available_pairs),
                                                 b.players_original_dots[n_turn]):
            b.unconquer_dot(self.turn, (x, y))
            # print("Error: This conquer would fully block the opponent.")
            return False

        b.unconquer_dot(self.turn, (x, y))
        return True

    def check_edge_input(self, point1, point2):
        x1, y1, _ = point1
        x2, y2, _ = point2
        b = self.board_obj

        # Check bounds
        if not (0 <= x1 < b.cols and 0 <= y1 < b.rows and 0 <= x2 < b.cols and 0 <= y2 < b.rows):
            # print("Error: Coordinates out of board range.")
            return False

        # Check availability
        if ((x1, y1, 1), (x2, y2, -1)) not in b.available_pairs and (
                (x2, y2, 1), (x1, y1, -1)) not in b.available_pairs:
            # print("Error: This pair is not available.")
            return False

        # Check if adding this edge results in an immediate win for the current player.
        # If yes — the move is allowed even if it disconnects the opponent.
        edg_1 = ((x1, y1, 1), (x2, y2, -1))
        edg_2 = ((x2, y2, 1), (x1, y1, -1))
        new_edges = {edg_1, edg_2}

        if self.check_all_outs_reach_all_ins(b.all_points, b.players_pairs[self.turn].union(new_edges),
                                             b.players_original_dots[self.turn]):
            return True  # allow this move (winning move)

        # Prevent fully blocking the other player
        n_turn = self.next_turn()
        other_edges = (b.available_pairs.difference({((x1, y1, 1), (x2, y2, -1)), ((x2, y2, 1), (x1, y1, -1))})).union(
            b.players_pairs[n_turn])
        if not self.check_all_outs_reach_all_ins(b.all_points, other_edges, b.players_original_dots[n_turn]):
            # self.board_obj.print_board()
            # print("Error: This pair will fully block the other player.")
            return False
        return True

    def make_move(self, edge):
        first_point = edge[0]
        second_point = edge[1]

        # הוספת הקשת לשחקן הנוכחי
        edg_1 = ((first_point[0], first_point[1], 1), (second_point[0], second_point[1], -1))
        edg_2 = ((second_point[0], second_point[1], 1), (first_point[0], first_point[1], -1))
        self.board_obj.players_pairs[self.turn].add(edg_1)
        self.board_obj.players_pairs[self.turn].add(edg_2)

        # הסרתן מהרשימה הכללית
        self.board_obj.available_pairs.discard(edg_1)
        self.board_obj.available_pairs.discard(edg_2)

main.py:
import pygame
from gameLogic import *
from settings import Settings

def is_mouse_on_edge(mouse_pos, edge, to_pixel, tolerance=5):
    """
    Checks if the mouse is close enough to a given edge on the board.
    """
    mx, my = mouse_pos
    (x1, y1, _), (x2, y2, _) = edge

    px1, py1 = to_pixel(x1, y1)
    px2, py2 = to_pixel(x2, y2)

    if px1 == px2:
        if py1 < py2:
            py1 += tolerance * 2
            py2 -= tolerance * 2
        else:
            py1 -= tolerance * 2
            py2 += tolerance * 2
    else:
        if px1 < px2:
            px1 += tolerance * 2
            px2 -= tolerance * 2
        else:
            px1 -= tolerance * 2
            px2 += tolerance * 2

    dx = px2 - px1
    dy = py2 - py1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return False
    t = max(0, min(1, ((mx - px1) * dx + (my - py1) * dy) / length_sq))
    nearest_x = px1 + t * dx
    nearest_y = py1 + t * dy
    dist_sq = (mx - nearest_x) ** 2 + (my - nearest_y) ** 2
    return dist_sq <= tolerance ** 2

def is_mouse_on_point(mouse_pos, point, to_pixel, tolerance=6):
    """
    Checks if the mouse is close enough to a given point (node) on the board.
    """
    mx, my = mouse_pos
    x, y = point

    px, py = to_pixel(x, y)

    dist_sq = (mx - px) ** 2 + (my - py) ** 2
    return dist_sq <= tolerance ** 2

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((Settings.WINDOW_WIDTH, Settings.WINDOW_HEIGHT))
        pygame.display.set_caption(Settings.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.gameLogic = GameLogic(9, 9,
                                   {Settings.PLAYER1: [(2, 2), (5, 4), (2, 6)],
                                    Settings.PLAYER2: [(6, 2), (3, 4), (6, 6)]})
        self.board = self.gameLogic.board_obj
        self.space_between_lines_x = (
                                             Settings.WINDOW_WIDTH - 2 * Settings.MARGIN - Settings.LINE_WIDTH
                                     ) / (self.board.cols - 1)
        self.space_between_lines_y = (
                                             Settings.WINDOW_HEIGHT - 2 * Settings.MARGIN - Settings.LINE_WIDTH
                                     ) / (self.board.rows - 1)

    def to_pixel(self, x, y):
        """Convert board coordinates (x, y) to pixel coordinates."""
        return (
            Settings.MARGIN + x * self.space_between_lines_x,
            Settings.MARGIN + y * self.space_between_lines_y
        )

    def run(self):
        while self.running:
            self.handle_events()
            self.draw()
        self.quit()

    def get_hovered_edge(self):
        """Returns the available edge currently under the mouse, or None."""
        mouse_pos = pygame.mouse.get_pos()
        for edge in self.board.available_pairs:
            if is_mouse_on_edge(mouse_pos, (edge[0], edge[1]), self.to_pixel):
                return edge
        return None

    def get_hovered_point(self):
        mouse_pos = pygame.mouse.get_pos()
        for dot in self.board.empty_dots:
            if is_mouse_on_point(mouse_pos, dot, self.to_pixel):
                return dot
        return None

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
                hovered_point = self.get_hovered_point()
                if hovered_point:
                    if self.gameLogic.check_conquer_input(hovered_point):
                        self.board.conquer_dot(self.gameLogic.turn, hovered_point)
                        self.next_turn()
                        continue

                hovered_edge = self.get_hovered_edge()
                if hovered_edge:
                    if self.gameLogic.check_edge_input(hovered_edge[0], hovered_edge[1]):
                        self.gameLogic.make_move(hovered_edge)
                        self.next_turn()

    def next_turn(self):
        winner = self.gameLogic.check_win()
        if winner:
            self.board.print_board()
            print(f"{winner} has won!")
            # TODO: end game
        self.gameLogic.turn = self.gameLogic.next_turn()

    def draw(self):
        self.screen.fill(Settings.BG_COLOR)
        mouse_pos = pygame.mouse.get_pos()

        # Draw bridges (edges)
        for player, edges in self.board.players_pairs.items():
            for edge in edges:
                color = Settings.PLAYERS_LINE_COLORS[player]
                pygame.draw.line(
                    self.screen, color,
                    self.to_pixel(edge[0][0], edge[0][1]),
                    self.to_pixel(edge[1][0], edge[1][1]),
                    Settings.LINE_WIDTH + 2
                )

        for edge in self.board.available_pairs:
            color = Settings.BASIC_LINE_COLOR
            if is_mouse_on_edge(mouse_pos, edge, self.to_pixel):
                if self.gameLogic.check_edge_input(edge[0], edge[1]):
                    color = Settings.PLAYER_MOUSE_ON_OBJECT_COLOR[self.gameLogic.turn]  # highlight color
                else:
                    color = Settings.ERROR_LINE_COLOR
            pygame.draw.line(
                self.screen, color,
                self.to_pixel(edge[0][0], edge[0][1]),
                self.to_pixel(edge[1][0], edge[1][1]),
                Settings.LINE_WIDTH + 2
            )

        # Draw all empty points
        for x, y, i in self.board.all_points:
            color = Settings.BG_COLOR
            if is_mouse_on_point(mouse_pos, (x, y), self.to_pixel):
                if self.gameLogic.check_conquer_input((x, y)):
                    color = Settings.PLAYER_MOUSE_ON_OBJECT_COLOR[self.gameLogic.turn]  # highlight color
            if i == -1:
                pygame.draw.circle(self.screen, color, self.to_pixel(x, y), Settings.EMPTY_POINT_RADIUS)

        # Draw player dots
        for player, points in self.board.conquer_dots.items():
            for x, y in points:
                pygame.draw.circle(
                    self.screen, Settings.POINT_COLOR[player],
                    self.to_pixel(x, y),
                    Settings.EMPTY_POINT_RADIUS
                )

        for player, points in self.board.players_original_dots.items():
            for x, y, trash in points:
                pygame.draw.circle(
                    self.screen, Settings.POINT_COLOR[player],
                    self.to_pixel(x, y),
                    Settings.PLAYER_POINT_RADIUS
                )
        pygame.display.flip()

    def quit(self):
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()

Settings.py:
class Settings:
    WINDOW_WIDTH = 800
    WINDOW_HEIGHT = 600
    MARGIN = 20
    LINE_WIDTH = 5
    WINDOW_TITLE = "Pygame Skeleton"
    FPS = 60
    PLAYER1 = "r"
    PLAYER2 = "b"

    BG_COLOR = (30, 30, 40)
    BASIC_LINE_COLOR = (60, 60, 80)
    PLAYERS_LINE_COLORS = {PLAYER1: (200, 20, 20), PLAYER2: (20, 20, 200)}
    PLAYER_MOUSE_ON_OBJECT_COLOR = {PLAYER1: (200, 60, 60), PLAYER2: (60, 60, 200)}
    ERROR_LINE_COLOR = (0, 0, 0)
    PLAYER_POINT_RADIUS = 20
    EMPTY_POINT_RADIUS = 8
    POINT_COLOR = {PLAYER1: (255, 0, 0), PLAYER2: (0, 0, 255)}