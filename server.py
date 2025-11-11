import socket
import threading
import time
from settings import Settings
from gameLogic import GameLogic


class GameServer:
    def __init__(self, host='localhost', port=Settings.PORT):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        print(f"SERVER: socket bound to {self.host}:{self.port}")

        self.games = []  # [(player1_conn, player2_conn, game_logic)]
        self.lock = threading.Lock()  # for managing self.games

    def start(self):
        """
        Main server loop. Accepts pairs of players and starts a game for them.
        """
        self.server_socket.listen(2)
        print(f"SERVER: listening on {self.host}:{self.port}")

        while True:
            print("SERVER: waiting for 2 new players...")

            # local list for the current game
            current_game_clients = []

            while len(current_game_clients) < 2:
                try:
                    conn, addr = self.server_socket.accept()
                    print(f"SERVER: player connected from {addr}")

                    # send player number (1 or 2)
                    conn.sendall(f"WELCOME {len(current_game_clients) + 1}".encode())
                    current_game_clients.append((conn, addr))

                except Exception as e:
                    print(f"SERVER: Error accepting connection: {e}")
                    if 'conn' in locals():
                        conn.close()
                    time.sleep(0.2)  # prevent flooding in case of error

            # if we reach here, we have 2 players in the local list
            print("SERVER: both players connected. Starting game.")
            player1 = current_game_clients[0]
            player2 = current_game_clients[1]

            # start the game in a new thread
            self.start_game(player1, player2)

            # the outer loop (while True) will restart,
            # ready to accept the next two players.

    def broadcast(self, players, msg):
        """Send message to both players."""
        for conn in players.values():
            try:
                conn.sendall(msg.encode())
            except:
                # assume connection issues are handled in handle_game loop
                pass

    def start_game(self, player1, player2):
        conn1, addr1 = player1
        conn2, addr2 = player2

        # setup game
        game_logic = GameLogic(
            9, 9,
            {
                Settings.PLAYER1: [(2, 2), (5, 4), (2, 6)],
                Settings.PLAYER2: [(6, 2), (3, 4), (6, 6)]
            }
        )

        players = {Settings.PLAYER1: conn1, Settings.PLAYER2: conn2}

        # added safe lock, although currently not critical
        with self.lock:
            self.games.append((conn1, conn2, game_logic))

        threading.Thread(target=self.handle_game, args=(players, game_logic), daemon=True).start()

    def handle_game(self, players, game_logic):
        # player 1 (P1) always starts
        game_logic.turn = Settings.PLAYER1

        try:
            while True:
                current_player = game_logic.turn
                conn = players[current_player]

                try:
                    msg = conn.recv(1024).decode()
                except Exception:  # catches ConnectionResetError and other issues
                    print(f"SERVER: connection lost from P{current_player}")
                    self.broadcast(players, "END DISCONNECTED")
                    break

                if not msg:
                    print(f"SERVER: P{current_player} disconnected gracefully.")
                    self.broadcast(players, "END DISCONNECTED")
                    break

                msg = msg.strip()
                print(f"SERVER: received from P{current_player}: {msg}")

                if msg.startswith("MOVE"):
                    move_data = msg[5:]  # remove "MOVE "
                    success = self.apply_move_str(game_logic, move_data, current_player)
                    if success:
                        # update all players
                        self.broadcast(players, f"UPDATE {move_data}")

                        # --- critical fix: update turn on server ---
                        game_logic.turn = game_logic.next_turn()
                    else:
                        conn.sendall("INVALID_MOVE".encode())

                elif msg == "QUIT":
                    self.broadcast(players, "END DISCONNECTED")
                    break

                # check win after move is applied and turn is updated
                winner = game_logic.check_win()
                if winner:
                    self.broadcast(players, f"END {winner}")
                    break

        finally:
            # clean up resources at the end of the game
            for conn in players.values():
                conn.close()
            print("SERVER: game ended. Connections closed.")
            # could also remove the game from self.games if desired

    def apply_move_str(self, game_logic, move_str, player_id):
        """
        Parse move string from client and apply it to GameLogic.
        move_str format: "(x1,y1,layer1)->(x2,y2,layer2)" or "(x,y,layer)"
        """
        move_str = move_str.replace("(", "").replace(")", "")
        if "->" in move_str:
            try:
                parts = move_str.split("->")
                p1 = tuple(map(int, parts[0].split(",")))
                p2 = tuple(map(int, parts[1].split(",")))

                # gameLogic expects only (x,y), not layer
                # check_edge_input expects full points (with 3 components)
                if game_logic.check_edge_input(p1, p2):
                    # make_move expects ((x1,y1), (x2,y2))
                    game_logic.make_move(((p1[0], p1[1]), (p2[0], p2[1])))
                    return True
            except Exception as e:
                print(f"SERVER: Error parsing edge move '{move_str}': {e}")
                return False
        else:
            try:
                # --- critical fix here ---
                # original p was (x, y, layer)
                p_with_layer = tuple(map(int, move_str.split(",")))

                # gameLogic expects (x,y) only
                p_xy = (p_with_layer[0], p_with_layer[1])

                if game_logic.check_conquer_input(p_xy):
                    game_logic.make_conquer_move(p_xy)
                    return True
            except Exception as e:
                print(f"SERVER: Error parsing conquer move '{move_str}': {e}")
                return False
        return False


if __name__ == "__main__":
    server = GameServer()
    server.start()  # this function now runs in an infinite loop
