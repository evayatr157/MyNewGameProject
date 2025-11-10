from gameLogic import *
from settings import Settings


class ServerSideGame:
    def __init__(self):
        # Initialize game logic
        self.gameLogic = GameLogic(
            9, 9,
            {
                Settings.PLAYER1: [(2, 2), (5, 4), (2, 6)],
                Settings.PLAYER2: [(6, 2), (3, 4), (6, 6)]
            }
        )

        self.board = self.gameLogic.board_obj

    def get_input(self):
        pass

    def make_move(self):
        pass

    def next_turn(self):
        pass


# --------------------
# MAIN ENTRY POINT
# --------------------
if __name__ == "__main__":
    game = ServerSideGame()
