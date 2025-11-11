import pygame
from gameLogic import *
from settings import Settings


def is_mouse_on_edge(mouse_pos, edge, to_pixel, tolerance=5):
    """
    Checks if the mouse is close enough to a given edge on the board.
    Uses projection of the mouse position onto the line segment.
    """
    mx, my = mouse_pos
    (x1, y1, _), (x2, y2, _) = edge

    px1, py1 = to_pixel(x1, y1)
    px2, py2 = to_pixel(x2, y2)

    # Slightly shrink the edge’s endpoints to avoid false positives near circles
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

    # Compute the nearest point on the line segment
    t = max(0, min(1, ((mx - px1) * dx + (my - py1) * dy) / length_sq))
    nearest_x = px1 + t * dx
    nearest_y = py1 + t * dy

    # Check squared distance between mouse and nearest point
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

        # Initialize game logic
        self.gameLogic = GameLogic(
            9, 9,
            {
                Settings.PLAYER1: [(2, 2), (5, 4), (2, 6)],
                Settings.PLAYER2: [(6, 2), (3, 4), (6, 6)]
            }
        )

        self.board = self.gameLogic.board_obj

        # Fixed: ensure each (x, y) appears only once in empty_dots
        self.board.empty_dots = list({(x, y) for x, y, _ in self.board.all_points})

        # Calculate spacing between lines based on window size
        self.space_between_lines_x = (
                (Settings.WINDOW_WIDTH - 2 * Settings.MARGIN - Settings.LINE_WIDTH)
                / (self.board.cols - 1)
        )
        self.space_between_lines_y = (
                (Settings.WINDOW_HEIGHT - 2 * Settings.MARGIN - Settings.LINE_WIDTH)
                / (self.board.rows - 1)
        )

        # Cache for hover logic (optimization)
        self.hovered_edge = None
        self.hovered_edge_is_valid = False
        self.hovered_point = None
        self.hovered_point_is_valid = False

    def to_pixel(self, x, y):
        """Convert board coordinates (x, y) to pixel coordinates."""
        return (
            Settings.MARGIN + x * self.space_between_lines_x,
            Settings.MARGIN + y * self.space_between_lines_y
        )

    def run(self):
        """Main game loop."""
        while self.running:
            if self.handle_events() == -1:
                return
            self.update_hover_state()
            self.draw()
        self.quit()

    # --------------------
    # MOUSE DETECTION
    # --------------------
    def update_hover_state(self):
        """Efficiently update hover state once per frame instead of checking every edge/point during draw."""
        mouse_pos = pygame.mouse.get_pos()

        # Reset previous hover states
        self.hovered_edge = None
        self.hovered_point = None
        self.hovered_edge_is_valid = False
        self.hovered_point_is_valid = False

        # Check points first (smaller search space)
        for dot in self.board.empty_dots:
            if is_mouse_on_point(mouse_pos, dot, self.to_pixel):
                self.hovered_point = dot
                self.hovered_point_is_valid = self.gameLogic.check_conquer_input(dot)
                return  # Point hover has priority over edges

        # Then check edges (potentially many)
        for edge in self.board.available_pairs:
            if is_mouse_on_edge(mouse_pos, edge, self.to_pixel):
                self.hovered_edge = edge
                self.hovered_edge_is_valid = self.gameLogic.check_edge_input(edge[0], edge[1])
                break

    def handle_events(self):
        """Handle user inputs (quit, mouse clicks, keys)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return -1
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left-click
                # Handle point conquer
                if self.hovered_point and self.hovered_point_is_valid:
                    self.gameLogic.make_conquer_move(self.hovered_point)
                    self.next_turn()
                    return 0

                # Handle edge placement
                if self.hovered_edge and self.hovered_edge_is_valid:
                    self.gameLogic.make_move(self.hovered_edge)
                    self.next_turn()

    # --------------------
    # TURN HANDLING
    # --------------------
    def next_turn(self):
        """Switch to the next player's turn, check win conditions."""
        winner = self.gameLogic.check_win()
        if winner:
            self.board.print_board()
            print(f"{winner} has won!")
            # TODO: Add end-game screen or restart
        self.gameLogic.turn = self.gameLogic.next_turn()

    # --------------------
    # DRAWING
    # --------------------
    def draw(self):
        self.screen.fill(Settings.BG_COLOR)

        # Draw existing bridges (edges owned by players)
        for player, edges in self.board.players_pairs.items():
            for edge in edges:
                color = Settings.PLAYERS_LINE_COLORS[player]
                pygame.draw.line(
                    self.screen, color,
                    self.to_pixel(edge[0][0], edge[0][1]),
                    self.to_pixel(edge[1][0], edge[1][1]),
                    Settings.LINE_WIDTH + 2
                )

        # Draw available edges (dim color, highlighted when hovered)
        seen = set()  # store undirected edges as frozenset({(x1,y1),(x2,y2)}) to draw each once

        for edge in self.board.available_pairs:
            # normalize endpoints to (x,y) ignoring the in/out flag
            p1 = (edge[0][0], edge[0][1])
            p2 = (edge[1][0], edge[1][1])
            key = frozenset({p1, p2})

            # draw each undirected edge only once
            if key in seen:
                continue
            seen.add(key)

            # Determine whether this undirected edge is the hovered one.
            # hovered_edge may be ((x1,y1,1),(x2,y2,-1)) or the reverse – handle both.
            is_hovered = False
            if self.hovered_edge:
                hp1 = (self.hovered_edge[0][0], self.hovered_edge[0][1])
                hp2 = (self.hovered_edge[1][0], self.hovered_edge[1][1])
                if frozenset({hp1, hp2}) == key:
                    is_hovered = True

            # Choose base color
            color = Settings.BASIC_LINE_COLOR

            # If hovered, choose highlight or error color depending on validity
            if is_hovered:
                if self.hovered_edge_is_valid:
                    color = Settings.PLAYER_MOUSE_ON_OBJECT_COLOR[self.gameLogic.turn]
                else:
                    color = Settings.ERROR_LINE_COLOR

            # Draw the line between the two points
            # Use p1 and p2 as pixel coordinates
            p1_px = self.to_pixel(p1[0], p1[1])
            p2_px = self.to_pixel(p2[0], p2[1])

            pygame.draw.line(
                self.screen, color,
                p1_px,
                p2_px,
                Settings.LINE_WIDTH
            )

        # Draw empty points (hovered point glows)
        for x, y, i in self.board.all_points:
            color = Settings.BG_COLOR
            if i == -1:
                if self.hovered_point == (x, y):
                    if self.hovered_point_is_valid:
                        color = Settings.PLAYER_MOUSE_ON_OBJECT_COLOR[self.gameLogic.turn]
                    else:
                        color = Settings.ERROR_LINE_COLOR
                pygame.draw.circle(self.screen, color, self.to_pixel(x, y), Settings.EMPTY_POINT_RADIUS)

        # Draw conquered (owned) dots
        for player, points in self.board.conquer_dots.items():
            for x, y in points:
                pygame.draw.circle(
                    self.screen, Settings.POINT_COLOR[player],
                    self.to_pixel(x, y),
                    Settings.EMPTY_POINT_RADIUS
                )

        # Draw original player dots (stronger visual)
        for player, points in self.board.players_original_dots.items():
            for x, y, _ in points:
                pygame.draw.circle(
                    self.screen, Settings.POINT_COLOR[player],
                    self.to_pixel(x, y),
                    Settings.PLAYER_POINT_RADIUS
                )

        # Draw status info (FPS + current turn)
        self.draw_status_bar()

        pygame.display.flip()

    def draw_status_bar(self):
        """Display FPS and current player's turn."""
        font = pygame.font.SysFont(None, 24)
        turn_text = font.render(f"Turn: {self.gameLogic.turn}", True, (255, 255, 255))
        self.screen.blit(turn_text, (10, 30))

    def quit(self):
        """Clean up pygame on exit."""
        pygame.quit()


# --------------------
# MAIN ENTRY POINT
# --------------------
if __name__ == "__main__":
    game = Game()
    game.run()
