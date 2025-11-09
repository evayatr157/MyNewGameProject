import socket
import threading
from ServerSettings import *


class GameServer:
    def __init__(self, host='localhost', port=12346):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server listening on {self.host}:{self.port}")

        self.clients = []          # All connected clients
        self.waiting_list = []     # Players waiting for a game
        self.condition = threading.Condition()  # For coordinating waiting threads

    def start(self):
        threading.Thread(target=self.wait_for_clients, daemon=True).start()
        print("Server started. Waiting for clients...")

        while True:
            with self.condition:
                # Wait until there are at least two waiting players
                self.condition.wait_for(lambda: len(self.waiting_list) >= 2)
                player1 = self.waiting_list.pop(0)
                player2 = self.waiting_list.pop(0)
            self.start_game(player1, player2)

    def wait_for_clients(self):
        while True:
            conn, addr = self.server_socket.accept()
            print("Connected by", addr)
            self.clients.append((conn, addr))
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def close_client(self, conn, addr):
        try:
            conn.close()
        finally:
            print(f"Client {addr} disconnected")
            if (conn, addr) in self.clients:
                self.clients.remove((conn, addr))
            if (conn, addr) in self.waiting_list:
                self.waiting_list.remove((conn, addr))

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(1024)
        except ConnectionResetError:
            self.close_client(conn, addr)
            return

        if not data:
            self.close_client(conn, addr)
            return

        received = data.decode()
        if received != ServerSettings.WELCOME_MSG:
            self.close_client(conn, addr)
            return

        conn.sendall(ServerSettings.WELCOME_MSG.encode())
        print(f"SERVER: Client {addr} has connected")
        conn.sendall(ServerSettings.WAITING_FOR_SECOND_PLAYER_MSG.encode())

        # Safely add to waiting list and notify
        with self.condition:
            self.waiting_list.append((conn, addr))
            self.condition.notify_all()  # Wake up threads waiting for enough players

        # Block until this client is removed from the waiting list (i.e. matched)
        with self.condition:
            self.condition.wait_for(lambda: (conn, addr) not in self.waiting_list)

        # TODO: continue to play game

    def start_game(self, player1, player2):
        conn1, addr1 = player1
        conn2, addr2 = player2
        print(f"Starting game between {addr1} and {addr2}")
        # Example:
        conn1.sendall(ServerSettings.GAME_START_MSG.encode())
        conn2.sendall(ServerSettings.GAME_START_MSG.encode())
        # TODO: game logic here


if __name__ == "__main__":
    server = GameServer()
    server.start()