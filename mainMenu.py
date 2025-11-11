import pygame
import sys
from settings import *

FPS = 60
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER_COLOR = (100, 160, 210)
TEXT_COLOR = (255, 255, 255)
FONT_SIZE = 36


class Button:
    def __init__(self, text, rect, action):
        self.text = text
        self.rect = pygame.Rect(rect)
        self.action = action
        self.hovered = False

    def draw(self, screen, font):
        color = BUTTON_HOVER_COLOR if self.hovered else BUTTON_COLOR
        pygame.draw.rect(screen, color, self.rect)
        text_surf = font.render(self.text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def check_hover(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def check_click(self, mouse_pos):
        if self.rect.collidepoint(mouse_pos):
            self.action()


def main():
    pygame.init()
    screen = pygame.display.set_mode((Settings.WINDOW_WIDTH, Settings.WINDOW_HEIGHT))
    pygame.display.set_caption("Main Menu")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, FONT_SIZE)

    # -------------------------
    # Actions for buttons
    # -------------------------
    def online_game():
        print("Online game selected")
        from client import ClientSideGame
        client_game = ClientSideGame(None)
        client_game.run()

    def offline_game():
        print("Offline game with friend selected")
        from offline_game import Game
        game = Game()
        game.run()

    def vs_computer():
        print("Game vs computer selected")  # placeholder

    def exit_action():
        pygame.quit()
        sys.exit()

    # -------------------------
    # Create buttons
    # -------------------------
    button_width = 300
    button_height = 60
    button_margin = 20
    start_y = (Settings.WINDOW_HEIGHT - (4 * button_height + 3 * button_margin)) // 2

    buttons = [
        Button("Online Game",
               (Settings.WINDOW_WIDTH // 2 - button_width // 2, start_y, button_width, button_height),
               online_game),
        Button("Offline Game with Friend",
               (Settings.WINDOW_WIDTH // 2 - button_width // 2, start_y + (button_height + button_margin), button_width,
                button_height),
               offline_game),
        Button("Play vs Computer",
               (Settings.WINDOW_WIDTH // 2 - button_width // 2, start_y + 2 * (button_height + button_margin),
                button_width,
                button_height),
               vs_computer),
        Button("Exit",
               (Settings.WINDOW_WIDTH // 2 - button_width // 2, start_y + 3 * (button_height + button_margin),
                button_width,
                button_height),
               exit_action),
    ]

    # -------------------------
    # Main loop
    # -------------------------
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button in buttons:
                    button.check_click(mouse_pos)

        for button in buttons:
            button.check_hover(mouse_pos)

        screen.fill(Settings.BG_COLOR)
        for button in buttons:
            button.draw(screen, font)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
