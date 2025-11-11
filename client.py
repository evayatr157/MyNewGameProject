# client.py (updated - threads: UI vs Network)
import socket
import threading
import queue
import time

import pygame
from gameLogic import *
from settings import Settings


# -------------------------
# Mouse detection helpers
# -------------------------
def is_mouse_on_edge(mouse_pos, edge, to_pixel, tolerance=5):
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

    t = max(0, min(1, ((mx - px1) * dx + (my - py1) * dy) / length_sq))
    nearest_x = px1 + t * dx
    nearest_y = py1 + t * dy

    dist_sq = (mx - nearest_x) ** 2 + (my - nearest_y) ** 2
    return dist_sq <= tolerance ** 2


def is_mouse_on_point(mouse_pos, point, to_pixel, tolerance=6):
    mx, my = mouse_pos
    x, y = point
    px, py = to_pixel(x, y)
    dist_sq = (mx - px) ** 2 + (my - py) ** 2
    return dist_sq <= tolerance ** 2


# -------------------------
# Client-side game
# -------------------------
class ClientSideGame:
    def __init__(self, player_color):  # player_color starts as None
        pygame.init()
        self.screen = pygame.display.set_mode((Settings.WINDOW_WIDTH, Settings.WINDOW_HEIGHT))
        pygame.display.set_caption(Settings.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.player_color = player_color  # starts as None

        # Initialize game logic
        self.gameLogic = GameLogic(
            9, 9,
            {
                Settings.PLAYER1: [(2, 2), (5, 4), (2, 6)],
                Settings.PLAYER2: [(6, 2), (3, 4), (6, 6)]
            }
        )

        self.board = self.gameLogic.board_obj

        # Ensure each (x, y) appears only once in empty_dots
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

        # Networking
        self.client_socket = None
        self.net_thread = None
        self.outgoing_moves = queue.Queue()  # UI -> Network: tuples like ("edge", edge_obj) or ("conquer",(x,y))
        self.incoming_events = queue.Queue()  # Network -> UI: dicts with keys: type, payload

        # Local turn/state flags
        self.is_my_turn = False  # updated by server
        self.awaiting_server_ok = False  # waiting for OK/NOT_OK after sending a move

        # Graceful shutdown flags
        self.network_alive = False

    # -------------------------
    # Socket connect & network thread
    # -------------------------
    def start_connection_to_server(self, host='localhost', port=Settings.PORT):
        """Starts network thread which performs handshake and then main network loop."""
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((host, port))
        except Exception as e:
            print("Couldn't connect to server:", e)
            self.incoming_events.put({"type": "error", "payload": f"connect_failed:{e}"})
            return

        # set timeout for non-blocking-ish recv
        self.client_socket.settimeout(0.5)
        self.network_alive = True
        self.net_thread = threading.Thread(target=self._network_loop, daemon=True)
        self.net_thread.start()

    def _network_loop(self):
        """Handles handshake and then bi-directional comms with the server."""
        sock = self.client_socket
        try:
            # HANDSHAKE
            data = self._recv_blocking()
            print(f"CLIENT: Received handshake: {data}")

            if data == "WELCOME 1":
                self.player_color = Settings.PLAYER1
                self.is_my_turn = True
                self.incoming_events.put({"type": "status", "payload": "game_start_P1"})
            elif data == "WELCOME 2":
                self.player_color = Settings.PLAYER2
                self.is_my_turn = False
                self.incoming_events.put({"type": "status", "payload": "game_start_P2"})
            else:
                raise Exception(f"Unexpected handshake message: {data}")

            print(f"CLIENT: I am {self.player_color}. My turn: {self.is_my_turn}")

            # main loop: react to server messages and process outgoing moves
            while self.network_alive:
                srv_msg = None
                try:
                    srv_msg = self._try_recv()
                except ConnectionResetError:
                    print("CLIENT: Connection reset by server")
                    self.incoming_events.put({"type": "error", "payload": "connection_reset"})
                    break
                except Exception as e:
                    print(f"CLIENT: Recv error: {e}")
                    self.incoming_events.put({"type": "error", "payload": f"recv_error:{e}"})
                    break

                if srv_msg:
                    srv_msg = srv_msg.strip()
                    print(f"CLIENT: Received: {srv_msg}")

                    if srv_msg.startswith("UPDATE "):
                        move_data = srv_msg[7:]
                        self.incoming_events.put({"type": "apply_update", "payload": move_data})
                    elif srv_msg == "INVALID_MOVE":
                        self.awaiting_server_ok = False
                        self.incoming_events.put({"type": "not_ok", "payload": None})
                    elif srv_msg.startswith("END "):
                        winner_msg = srv_msg[4:]
                        self.incoming_events.put({"type": "game_over", "payload": winner_msg})
                        self.network_alive = False
                    else:
                        if len(srv_msg) > 0:
                            self.incoming_events.put({"type": "raw", "payload": srv_msg})

                # If it's our turn and we have an outgoing move queued and we're not already awaiting OK -> send it
                if self.is_my_turn and not self.awaiting_server_ok:
                    try:
                        move = self.outgoing_moves.get_nowait()
                    except queue.Empty:
                        move = None

                    if move:
                        msg = ""
                        if move[0] == "edge":
                            ((x1, y1, l1), (x2, y2, l2)) = move[1]
                            msg = f"MOVE ({x1},{y1},{l1})->({x2},{y2},{l2})"
                        elif move[0] == "conquer":
                            (x, y) = move[1]
                            msg = f"MOVE ({x},{y},-1)"

                        try:
                            sock.sendall(msg.encode())
                            self.awaiting_server_ok = True
                        except Exception as e:
                            print("CLIENT: send failed:", e)
                            self.incoming_events.put({"type": "error", "payload": f"send_failed:{e}"})
                            break

                time.sleep(0.01)

        finally:
            try:
                sock.close()
            except Exception:
                pass
            self.network_alive = False
            self.incoming_events.put({"type": "status", "payload": "network_closed"})
            print("CLIENT: network thread exiting")

    def _recv_blocking(self):
        """Blocking recv (ignores timeouts) used during handshake."""
        sock = self.client_socket
        sock.settimeout(None)
        try:
            data = sock.recv(1024)
            if not data:
                return None
            return data.decode()
        finally:
            sock.settimeout(0.5)

    def _try_recv(self):
        """Non-blocking-ish recv returning decoded string or None."""
        sock = self.client_socket
        try:
            data = sock.recv(1024)
            if not data:
                raise ConnectionResetError()
            return data.decode()
        except socket.timeout:
            return None

    # -------------------------
    # UI API to send moves
    # -------------------------
    def send_server_edge_move(self, edge):
        """Called from UI thread when player clicks to place an edge.
           Returns True if move was queued."""
        if not self.network_alive:
            print("CLIENT: network not alive - cannot send move")
            return False
        if not self.is_my_turn:
            print("CLIENT: not my turn")
            return False
        if self.awaiting_server_ok:
            print("CLIENT: awaiting server response for previous move")
            return False

        self.outgoing_moves.put(("edge", edge))
        return True

    def send_server_conquer_move(self, dot):
        """Queue a conquer move. Returns True if queued."""
        if not self.network_alive:
            print("CLIENT: network not alive - cannot send move")
            return False
        if not self.is_my_turn:
            print("CLIENT: not my turn")
            return False
        if self.awaiting_server_ok:
            print("CLIENT: awaiting server response for previous move")
            return False

        (x, y) = dot
        self.outgoing_moves.put(("conquer", (int(x), int(y))))
        return True

    # -------------------------
    # UI loop
    # -------------------------
    def run(self):
        """Main Pygame UI loop. Starts network thread first."""
        self.start_connection_to_server()

        while self.running:
            self._process_incoming_events()
            self.handle_events()

            if self.is_my_turn:
                self.update_hover_state()
            else:
                self.hovered_edge = None
                self.hovered_point = None
                self.hovered_edge_is_valid = False
                self.hovered_point_is_valid = False

            self.draw()
            self.clock.tick(Settings.FPS)

        self.network_alive = False
        if self.net_thread:
            self.net_thread.join(timeout=1)
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        # self.quit()

    # --------------------
    # Mouse detection
    # --------------------
    def update_hover_state(self):
        mouse_pos = pygame.mouse.get_pos()

        self.hovered_edge = None
        self.hovered_point = None
        self.hovered_edge_is_valid = False
        self.hovered_point_is_valid = False

        for dot in self.board.empty_dots:
            if is_mouse_on_point(mouse_pos, dot, self.to_pixel):
                self.hovered_point = dot
                self.hovered_point_is_valid = self.gameLogic.check_conquer_input(dot)
                return

        for edge in self.board.available_pairs:
            if is_mouse_on_edge(mouse_pos, edge, self.to_pixel):
                self.hovered_edge = edge
                self.hovered_edge_is_valid = self.gameLogic.check_edge_input(edge[0], edge[1])
                break

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.is_my_turn:
                if self.hovered_point and self.hovered_point_is_valid:
                    self.send_server_conquer_move(self.hovered_point)
                    return
                if self.hovered_edge and self.hovered_edge_is_valid:
                    self.send_server_edge_move(self.hovered_edge)

    # --------------------
    # Process server/network events
    # --------------------
    def _apply_server_update(self, move_str):
        """Parse move string from server and apply to local gameLogic."""
        try:
            move_str = move_str.replace("(", "").replace(")", "")
            if "->" in move_str:
                parts = move_str.split("->")
                p1_str = parts[0].split(",")
                p2_str = parts[1].split(",")

                p1 = (int(p1_str[0]), int(p1_str[1]))
                p2 = (int(p2_str[0]), int(p2_str[1]))

                self.gameLogic.make_move((p1, p2))
                print(f"CLIENT: Applied server edge move: {p1}->{p2}")
                return True
            else:
                p_str = move_str.split(",")
                p = (int(p_str[0]), int(p_str[1]))
                self.gameLogic.make_conquer_move(p)
                print(f"CLIENT: Applied server conquer move: {p}")
                return True
        except Exception as e:
            print(f"CLIENT: Error applying server update '{move_str}': {e}")
            return False

    def _process_incoming_events(self):
        """Apply events from server/network to local game state & UI."""
        processed_any = False
        while True:
            try:
                ev = self.incoming_events.get_nowait()
            except queue.Empty:
                break

            processed_any = True
            etype = ev.get("type")
            payload = ev.get("payload")

            if etype == "status":
                print("Status:", payload)
                if payload == "game_start_P1" or payload == "game_start_P2":
                    pygame.display.set_caption(f"{Settings.WINDOW_TITLE} - Player: {self.player_color}")
            elif etype == "apply_update":
                move_str = payload
                success = self._apply_server_update(move_str)
                if success:
                    self.gameLogic.turn = self.gameLogic.next_turn()
                    self.is_my_turn = (self.player_color == self.gameLogic.turn)
                    self.awaiting_server_ok = False
                    print(f"CLIENT: Update applied. New turn: {self.gameLogic.turn}. My turn: {self.is_my_turn}")
                else:
                    print(f"CLIENT: !! CRITICAL: Failed to apply server update '{move_str}'")
            elif etype == "not_ok":
                self.awaiting_server_ok = False
                print("Server: NOT OK (move rejected)")
            elif etype == "game_over":
                payload = payload.strip()
                if payload == "DISCONNECTED":
                    print("Game over: Opponent disconnected")
                elif payload == self.player_color:
                    print(f"Game over: YOU WIN! ({payload})")
                else:
                    print(f"Game over: YOU LOSE! ({payload} won)")
                self.running = False
            elif etype == "error":
                print("Network error:", payload)
                self.running = False
            elif etype == "raw":
                print("RAW from server:", payload)
            else:
                print("Unknown event:", etype, payload)

        return processed_any

    # --------------------
    # Drawing
    # --------------------
    def to_pixel(self, x, y):
        return (
            Settings.MARGIN + x * self.space_between_lines_x,
            Settings.MARGIN + y * self.space_between_lines_y
        )

    def draw(self):
        self.screen.fill(Settings.BG_COLOR)

        # Draw existing bridges
        for player, edges in self.board.players_pairs.items():
            for edge in edges:
                color = Settings.PLAYERS_LINE_COLORS[player]
                pygame.draw.line(
                    self.screen, color,
                    self.to_pixel(edge[0][0], edge[0][1]),
                    self.to_pixel(edge[1][0], edge[1][1]),
                    Settings.LINE_WIDTH + 2
                )

        # Draw available edges
        seen = set()
        for edge in self.board.available_pairs:
            p1 = (edge[0][0], edge[0][1])
            p2 = (edge[1][0], edge[1][1])
            key = frozenset({p1, p2})
            if key in seen:
                continue
            seen.add(key)

            is_hovered = False
            if self.hovered_edge:
                hp1 = (self.hovered_edge[0][0], self.hovered_edge[0][1])
                hp2 = (self.hovered_edge[1][0], self.hovered_edge[1][1])
                if frozenset({hp1, hp2}) == key:
                    is_hovered = True

            color = Settings.BASIC_LINE_COLOR
            if is_hovered and self.is_my_turn:
                if self.hovered_edge_is_valid:
                    color = Settings.PLAYER_MOUSE_ON_OBJECT_COLOR[self.gameLogic.turn]
                else:
                    color = Settings.ERROR_LINE_COLOR

            p1_px = self.to_pixel(p1[0], p1[1])
            p2_px = self.to_pixel(p2[0], p2[1])

            pygame.draw.line(self.screen, color, p1_px, p2_px, Settings.LINE_WIDTH)

        # Draw empty points
        for x, y, i in self.board.all_points:
            color = Settings.BG_COLOR
            if i == -1:
                if self.hovered_point == (x, y) and self.is_my_turn:
                    if self.hovered_point_is_valid:
                        color = Settings.PLAYER_MOUSE_ON_OBJECT_COLOR[self.gameLogic.turn]
                    else:
                        color = Settings.ERROR_LINE_COLOR
                pygame.draw.circle(self.screen, color, self.to_pixel(x, y), Settings.EMPTY_POINT_RADIUS)

        # Draw conquered dots
        for player, points in self.board.conquer_dots.items():
            for x, y in points:
                pygame.draw.circle(
                    self.screen, Settings.POINT_COLOR[player],
                    self.to_pixel(x, y),
                    Settings.EMPTY_POINT_RADIUS
                )

        # Draw original player dots
        for player, points in self.board.players_original_dots.items():
            for x, y, _ in points:
                pygame.draw.circle(
                    self.screen, Settings.POINT_COLOR[player],
                    self.to_pixel(x, y),
                    Settings.PLAYER_POINT_RADIUS
                )

        # Draw status bar
        self.draw_status_bar()

        pygame.display.flip()

    def draw_status_bar(self):
        font = pygame.font.SysFont(None, 24)

        my_player_text = f"You are: {self.player_color}" if self.player_color else "Connecting..."
        text1 = font.render(my_player_text, True, (255, 255, 255))
        self.screen.blit(text1, (10, 10))

        turn_text = f"Turn: {self.gameLogic.turn}"
        text2 = font.render(turn_text, True, (255, 255, 255))
        self.screen.blit(text2, (10, 30))

        if self.is_my_turn:
            my_turn_text = font.render("YOUR TURN", True, (0, 255, 0))
            self.screen.blit(my_turn_text, (10, 50))

        if self.awaiting_server_ok:
            wait_text = font.render("Waiting for server...", True, (255, 255, 0))
            self.screen.blit(wait_text, (10, 70))

    def quit(self):
        pygame.quit()


# -------------------------
# Main entry
# -------------------------
if __name__ == "__main__":
    client = ClientSideGame(None)
    client.run()
