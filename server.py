import socket
import threading
import time  # הוספנו
from settings import Settings
from gameLogic import GameLogic


class GameServer:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        # self.server_socket.listen(2) # --- העברנו את זה לפונקציית start ---
        print(f"SERVER: socket bound to {self.host}:{self.port}")

        # self.clients = [] # --- אנחנו כבר לא צריכים את זה כמשתנה גלובאלי ---
        self.games = []  # [(player1_conn, player2_conn, game_logic)]
        self.lock = threading.Lock()  # נשאר שימושי אם נרצה לנהל את self.games

    def start(self):
        """
        לולאת השרת הראשית. מקבלת זוגות של שחקנים ומפעילה עבורם משחק.
        """
        self.server_socket.listen(2)
        print(f"SERVER: listening on {self.host}:{self.port}")

        # --- הוספנו לולאה אינסופית ---
        while True:
            print("SERVER: waiting for 2 new players...")

            # רשימה מקומית עבור המשחק הנוכחי
            current_game_clients = []

            while len(current_game_clients) < 2:
                try:
                    conn, addr = self.server_socket.accept()
                    print(f"SERVER: player connected from {addr}")

                    # שלח לשחקן את המספר שלו (1 או 2)
                    conn.sendall(f"WELCOME {len(current_game_clients) + 1}".encode())
                    current_game_clients.append((conn, addr))

                except Exception as e:
                    print(f"SERVER: Error accepting connection: {e}")
                    if 'conn' in locals():
                        conn.close()
                    time.sleep(0.5)  # מנע הצפה במקרה של שגיאה

            # אם הגענו לכאן, יש לנו 2 שחקנים ברשימה המקומית
            print("SERVER: both players connected. Starting game.")
            player1 = current_game_clients[0]
            player2 = current_game_clients[1]

            # הפעל את המשחק ב-Thread
            self.start_game(player1, player2)

            # הלולאה החיצונית (while True) תתחיל מחדש,
            # מוכנה לקבל את שני השחקנים הבאים.

    def broadcast(self, players, msg):
        """Send message to both players."""
        for conn in players.values():
            try:
                conn.sendall(msg.encode())
            except:
                # הנח שהחיבור יטופל בלולאת handle_game
                pass

    def start_game(self, player1, player2):
        conn1, addr1 = player1
        conn2, addr2 = player2

        # Setup game
        game_logic = GameLogic(
            9, 9,
            {
                Settings.PLAYER1: [(2, 2), (5, 4), (2, 6)],
                Settings.PLAYER2: [(6, 2), (3, 4), (6, 6)]
            }
        )

        players = {Settings.PLAYER1: conn1, Settings.PLAYER2: conn2}

        # הוספנו נעילה בטוחה, למרות שכרגע זה לא קריטי
        with self.lock:
            self.games.append((conn1, conn2, game_logic))

        threading.Thread(target=self.handle_game, args=(players, game_logic), daemon=True).start()

    def handle_game(self, players, game_logic):
        # שחקן 1 (P1) תמיד מתחיל
        game_logic.turn = Settings.PLAYER1

        try:
            while True:
                current_player = game_logic.turn
                conn = players[current_player]

                try:
                    msg = conn.recv(1024).decode()
                except Exception:  # תופס ConnectionResetError ובעיות נוספות
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
                        # עדכון לכולם
                        self.broadcast(players, f"UPDATE {move_data}")

                        # --- !!! תיקון קריטי: עדכון התור בשרת !!! ---
                        game_logic.turn = game_logic.next_turn()
                    else:
                        conn.sendall("INVALID_MOVE".encode())

                elif msg == "QUIT":
                    self.broadcast(players, "END DISCONNECTED")
                    break

                # בדוק ניצחון לאחר שהמהלך בוצע והתור התעדכן
                winner = game_logic.check_win()
                if winner:
                    self.broadcast(players, f"END {winner}")
                    break

        finally:
            # נקה משאבים בסוף המשחק
            for conn in players.values():
                conn.close()
            print("SERVER: game ended. Connections closed.")
            # אפשר גם להסיר את המשחק מ-self.games אם רוצים

    def apply_move_str(self, game_logic, move_str, player_id):
        """
        מפרש מחרוזת מהלך מהלקוח ומפעיל אותו על ה-GameLogic.
        move_str בפורמט: "(x1,y1,layer1)->(x2,y2,layer2)" או "(x,y,layer)"
        """
        move_str = move_str.replace("(", "").replace(")", "")
        if "->" in move_str:
            try:
                parts = move_str.split("->")
                p1 = tuple(map(int, parts[0].split(",")))
                p2 = tuple(map(int, parts[1].split(",")))

                # gameLogic מצפה רק ל- (x,y) ולא ל-layer
                # הפונקציה check_edge_input צריכה את הנקודות המלאות (עם 3 רכיבים)
                if game_logic.check_edge_input(p1, p2):
                    # הפונקציה make_move צריכה רק ( (x1,y1), (x2,y2) )
                    game_logic.make_move(((p1[0], p1[1]), (p2[0], p2[1])))
                    return True
            except Exception as e:
                print(f"SERVER: Error parsing edge move '{move_str}': {e}")
                return False
        else:
            try:
                # --- !!! תיקון קריטי כאן !!! ---
                # p המקורי היה (x, y, layer)
                p_with_layer = tuple(map(int, move_str.split(",")))

                # gameLogic מצפה ל- (x,y) בלבד
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
    server.start()  # הפונקציה הזו רצה עכשיו בלולאה אינסופית