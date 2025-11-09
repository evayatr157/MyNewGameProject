import socket
from ServerSettings import *


def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 12346))

    # Send initial handshake
    client_socket.sendall(ServerSettings.WELCOME_MSG.encode())
    data = client_socket.recv(1024).decode()
    if data == ServerSettings.WELCOME_MSG:
        print("CLIENT: connected to server")
    else:
        print("Something weird happened (handshake)")
        return

    # Wait for the “waiting” message
    data = client_socket.recv(1024).decode()
    if data == ServerSettings.WAITING_FOR_SECOND_PLAYER_MSG:
        print("CLIENT: Waiting for the second player...")
    else:
        print("Something weird happened (waiting)")
        return

    # Wait for the game start
    data = client_socket.recv(1024).decode()
    if data == ServerSettings.GAME_START_MSG:
        print("CLIENT: Game starting!")
        play_game(client_socket)
    else:
        print("Something weird happened (game start)")
        return


def play_game(sock):
    print("CLIENT: Game loop started.")
    try:
        while True:
            data = sock.recv(1024)
            if not data:
                print("CLIENT: Server disconnected.")
                break
            message = data.decode()
            print("SERVER:", message)

            # Example interaction: echo user input back to server
            msg = input("Your move (or 'quit' to exit): ")
            sock.sendall(msg.encode())
            if msg.lower() == "quit":
                break

    except ConnectionResetError:
        print("CLIENT: Lost connection to server.")
    finally:
        sock.close()
        print("CLIENT: Disconnected.")


if __name__ == "__main__":
    main()
