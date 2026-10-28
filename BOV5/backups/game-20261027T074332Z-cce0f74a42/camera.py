class Camera:
    def __init__(self, screen_width, level_width):
        self.screen_width = screen_width
        self.level_width = level_width
        self.offset_x = 0

    def update(self, player_rect):
        # center player when possible
        target_x = player_rect.centerx - self.screen_width // 2
        if target_x < 0:
            target_x = 0
        if target_x > self.level_width - self.screen_width:
            target_x = max(0, self.level_width - self.screen_width)
        self.offset_x = int(target_x)
