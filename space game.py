"""
Space Shooter / Platformer (single-file Pygame game)
Save as: space_platformer.py
Run: python space_platformer.py
Requires: pygame (pip install pygame)

Controls:
      - Left / Right arrows (A / D) : move
  - Up arrow / W / Space         : jump
  - J                           : shoot
  - P                           : pause
  - Enter                       : start / restart from title or game over
"""

import pygame
import random
import math
from collections import deque

# -----------------------------
# Settings
# -----------------------------
WIDTH, HEIGHT = 1000, 640
FPS = 60

GRAVITY = 0.8
PLAYER_ACC = 0.6
PLAYER_FRICTION = -0.12
PLAYER_JUMP_VELOCITY = -14
PLAYER_MAX_SPEED = 8

BULLET_SPEED = 14
ENEMY_BULLET_SPEED = 6

# Colors
WHITE = (245, 245, 245)
BLACK = (10, 10, 12)
SKY1 = (10, 14, 30)
SKY2 = (20, 30, 60)
PLATFORM_COLOR = (40, 132, 120)
PLAYER_COLOR = (200, 200, 40)
ENEMY_COLOR = (200, 60, 60)
BULLET_COLOR = (255, 220, 100)
HUD_COLOR = (220, 220, 220)

# -----------------------------
# Pygame init
# -----------------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Shooter / Platformer")    
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 20)
big_font = pygame.font.SysFont("arial", 48)

# Sound placeholders (commented if not available)
# pygame.mixer.init()
# SHOT_SOUND = pygame.mixer.Sound("shot.wav")  # optional
# HIT_SOUND = pygame.mixer.Sound("hit.wav")


# -----------------------------
# Utility functions
# -----------------------------
def draw_text(surf, text, size, x, y, color=HUD_COLOR, center=False):
    if isinstance(size, int):
        f = pygame.font.SysFont("arial", size)
    else:
        f = size
    t = f.render(text, True, color)
    r = t.get_rect()
    if center:
        r.center = (x, y)
    else:
        r.topleft = (x, y)
    surf.blit(t, r)


# -----------------------------
# Game Objects
# -----------------------------
class Camera:
    def __init__(self, width, height):
        self.offset = pygame.Vector2(0, 0)
        self.width = width
        self.height = height

    def apply(self, rect):
        return rect.move(-self.offset.x, -self.offset.y)

    def update(self, target_rect):
        # center camera on target with bounds
        self.offset.x = max(0, min(target_rect.centerx - WIDTH // 2, self.width - WIDTH))
        self.offset.y = max(0, min(target_rect.centery - HEIGHT // 2, self.height - HEIGHT))


class Platform(pygame.sprite.Sprite):
    def __init__(self, x, y, w, h):
        super().__init__()
        self.image = pygame.Surface((w, h))
        self.image.fill(PLATFORM_COLOR)
        self.rect = self.image.get_rect(topleft=(x, y))


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, dx, dy, owner="player"):
        super().__init__()
        self.image = pygame.Surface((8, 4))
        self.image.fill(BULLET_COLOR)
        if abs(dy) > abs(dx):
            self.image = pygame.Surface((4, 8))
            self.image.fill(BULLET_COLOR)
        self.rect = self.image.get_rect(center=(x, y))
        self.vel = pygame.Vector2(dx, dy)
        self.owner = owner

    def update(self, dt, level_width, level_height):
        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)
        # remove if offscreen in level coordinates
        if (self.rect.right < 0 or self.rect.left > level_width or
                self.rect.bottom < 0 or self.rect.top > level_height):
            self.kill()


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, kind="patrol"):
        super().__init__()
        self.kind = kind
        self.image = pygame.Surface((36, 34))
        self.image.fill(ENEMY_COLOR)
        self.rect = self.image.get_rect(center=(x, y))
        self.health = 2 if kind == "patrol" else 4
        self.speed = 2 if kind == "patrol" else 1.2
        self.direction = random.choice([-1, 1])
        self.shoot_cool = random.randint(40, 120)

    def update(self, dt, platforms, bullets_group, player):
        if self.kind == "patrol":
            self.rect.x += int(self.speed * self.direction * dt)
            # flip on platform edges
            hits = [p for p in platforms if self.rect.colliderect(p.rect.inflate(0, 6))]
            if not hits:
                self.direction *= -1
            else:
                # small chance to change direction
                if random.random() < 0.01:
                    self.direction *= -1
        elif self.kind == "fly":
            # floating movement toward player horizontally, bob vertically
            if player.rect.centerx < self.rect.centerx:
                self.rect.x -= int(self.speed * dt)
            else:
                self.rect.x += int(self.speed * dt)
            self.rect.y += int(math.sin(pygame.time.get_ticks() / 400) * 0.8)

        # shooting
        self.shoot_cool -= 1
        if self.shoot_cool <= 0:
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy) or 1
            vx = (dx / dist) * ENEMY_BULLET_SPEED
            vy = (dy / dist) * ENEMY_BULLET_SPEED
            b = Bullet(self.rect.centerx, self.rect.centery, vx, vy, owner="enemy")
            bullets_group.add(b)
            self.shoot_cool = random.randint(80, 160)


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.width, self.height = 36, 48
        self.image = pygame.Surface((self.width, self.height))
        self.image.fill(PLAYER_COLOR)
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.pos = pygame.Vector2(self.rect.x, self.rect.y)
        self.vel = pygame.Vector2(0, 0)
        self.acc = pygame.Vector2(0, 0)
        self.on_ground = False
        self.facing = 1
        self.shoot_cool = 0
        self.health = 6
        self.max_health = 6
        self.score = 0
        self.lives = 3

    def handle_input(self, keys):
        self.acc = pygame.Vector2(0, GRAVITY)
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        if left:
            self.acc.x = -PLAYER_ACC
            self.facing = -1
        if right:
            self.acc.x = PLAYER_ACC
            self.facing = 1

    def jump(self, platforms):
        # only jump if on ground
        self.rect.y += 2
        hits = pygame.sprite.spritecollide(self, platforms, False)
        self.rect.y -= 2
        if hits or self.on_ground:
            self.vel.y = PLAYER_JUMP_VELOCITY
            self.on_ground = False

    def shoot(self, bullets_group):
        if self.shoot_cool <= 0:
            dx = self.facing * BULLET_SPEED
            b = Bullet(self.rect.centerx + self.facing * 20, self.rect.centery - 6, dx, 0, owner="player")
            bullets_group.add(b)
            self.shoot_cool = 12  # frames cooldown

    def update(self, dt, platforms):
        # apply physics
        self.vel += self.acc
        # friction
        self.vel.x += self.vel.x * PLAYER_FRICTION
        # clamp speed
        if self.vel.x > PLAYER_MAX_SPEED:
            self.vel.x = PLAYER_MAX_SPEED
        if self.vel.x < -PLAYER_MAX_SPEED:
            self.vel.x = -PLAYER_MAX_SPEED

        # update position
        self.pos.x += self.vel.x * dt
        self.rect.x = int(self.pos.x)
        # horizontal collisions
        hits = pygame.sprite.spritecollide(self, platforms, False)
        for p in hits:
            if self.vel.x > 0:
                self.rect.right = p.rect.left
            elif self.vel.x < 0:
                self.rect.left = p.rect.right
            self.pos.x = self.rect.x
            self.vel.x = 0

        # vertical
        self.pos.y += self.vel.y * dt + 0.5 * self.acc.y * dt * dt
        self.rect.y = int(self.pos.y)
        hits = pygame.sprite.spritecollide(self, platforms, False)
        self.on_ground = False
        for p in hits:
            if self.vel.y > 0:
                self.rect.bottom = p.rect.top
                self.on_ground = True
                self.vel.y = 0
            elif self.vel.y < 0:
                self.rect.top = p.rect.bottom
                self.vel.y = 0
            self.pos.y = self.rect.y

        # cooldowns
        if self.shoot_cool > 0:
            self.shoot_cool -= 1

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.lives -= 1
            return True  # died
        return False


# -----------------------------
# Level generator
# -----------------------------
class Level:
    def __init__(self, width=3000, height=HEIGHT):
        self.width = width
        self.height = height
        self.platforms = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self._make_level()

    def _make_level(self):
        # ground
        ground = Platform(0, self.height - 40, self.width, 40)
        self.platforms.add(ground)

        # basic platforms
        x = 200
        while x < self.width - 200:
            w = random.randint(120, 260)
            h = 18
            y = random.randint(160, self.height - 120)
            p = Platform(x, y, w, h)
            self.platforms.add(p)
            # occasionally add enemy on top
            if random.random() < 0.4:
                e = Enemy(x + w // 2, y - 30, kind=random.choice(["patrol", "fly"]))
                self.enemies.add(e)
            x += random.randint(180, 420)

        # some tall tower platforms
        for i in range(8):
            px = random.randint(500, self.width - 300)
            py = random.randint(100, self.height - 280)
            p = Platform(px, py, random.randint(80, 140), 18)
            self.platforms.add(p)
            if random.random() < 0.6:
                e = Enemy(px + 40, py - 30, kind="patrol")
                self.enemies.add(e)

    def draw_background(self, surf, camera):
        # parallax starfield-like gradient using bands
        surf.fill(SKY1)
        # simple stars
        star_count = 120
        random.seed(123)  # deterministic star pattern
        for i in range(star_count):
            sx = random.randint(0, self.width) - int(camera.offset.x * 0.3)
            sy = random.randint(0, self.height)
            if 0 <= sx - camera.offset.x < WIDTH + 50:
                surf.set_at((int(sx - camera.offset.x), int(sy - camera.offset.y) if 0 <= sy < HEIGHT else 0), (190, 190, 255))


# -----------------------------
# Game Manager
# -----------------------------
class Game:
    def __init__(self):
        self.level = Level(width=4000, height=HEIGHT)
        self.player = Player(120, HEIGHT - 200)
        self.camera = Camera(self.level.width, self.level.height)
        self.player_group = pygame.sprite.GroupSingle(self.player)
        self.bullets = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.hud_surf = pygame.Surface((WIDTH, 60), pygame.SRCALPHA)
        self.state = "title"  # title, playing, paused, gameover
        self.spawn_timer = 0

    def reset(self):
        self.__init__()

    def update(self, dt, keys):
        if self.state == "playing":
            self.player.handle_input(keys)
            # update player
            self.player.update(dt, self.level.platforms)

            # update enemies
            for e in list(self.level.enemies):
                e.update(dt, self.level.platforms, self.enemy_bullets, self.player)

            # update bullets
            for b in list(self.bullets):
                b.update(1.0, self.level.width, self.level.height)
            for b in list(self.enemy_bullets):
                b.update(1.0, self.level.width, self.level.height)

            # collisions: player bullets -> enemies
            for b in list(self.bullets):
                hit = pygame.sprite.spritecollideany(b, self.level.enemies)
                if hit:
                    hit.health -= 1
                    # HIT_SOUND.play() if defined
                    b.kill()
                    if hit.health <= 0:
                        hit.kill()
                        self.player.score += 150

            # enemy bullets -> player
            for b in list(self.enemy_bullets):
                if self.player.rect.colliderect(b.rect):
                    b.kill()
                    died = self.player.take_damage(1)
                    if died:
                        self.player.health = self.player.max_health
                        if self.player.lives < 0:
                            self.state = "gameover"

            # enemies touching player
            hits = pygame.sprite.spritecollide(self.player, self.level.enemies, False)
            for e in hits:
                # simple bounce knockback
                if self.player.rect.centery < e.rect.centery:
                    # landed on enemy -> damage enemy
                    e.health -= 2
                    self.player.vel.y = PLAYER_JUMP_VELOCITY / 2
                    if e.health <= 0:
                        e.kill()
                        self.player.score += 200
                else:
                    died = self.player.take_damage(1)
                    if died:
                        self.player.health = self.player.max_health
                        if self.player.lives < 0:
                            self.state = "gameover"

            # camera follow
            self.camera.update(self.player.rect)

            # spawn new enemies if too few
            if len(self.level.enemies) < 6:
                self.spawn_timer += 1
                if self.spawn_timer > 90:
                    sx = int(self.player.rect.x + random.choice([-600, 800, 1000]))
                    sx = max(100, min(sx, self.level.width - 80))
                    e = Enemy(sx, random.randint(100, self.level.height - 120), kind=random.choice(["patrol", "fly"]))
                    self.level.enemies.add(e)
                    self.spawn_timer = 0

    def draw(self, surf):
        # background
        bg = pygame.Surface((WIDTH, HEIGHT))
        self.level.draw_background(bg, self.camera)
        surf.blit(bg, (0, 0))

        # parallax distant shapes
        # draw platforms and sprites with camera
        for p in self.level.platforms:
            surf.blit(p.image, self.camera.apply(p.rect))
        for e in self.level.enemies:
            surf.blit(e.image, self.camera.apply(e.rect))

        # bullets
        for b in self.bullets:
            surf.blit(b.image, self.camera.apply(b.rect))
        for b in self.enemy_bullets:
            surf.blit(b.image, self.camera.apply(b.rect))

        # player
        surf.blit(self.player.image, self.camera.apply(self.player.rect))

        # HUD
        self.hud_surf.fill((0, 0, 0, 0))
        draw_text(self.hud_surf, f"Score: {self.player.score}", 20, 12, 8)
        draw_text(self.hud_surf, f"Lives: {self.player.lives}", 20, 160, 8)
        # health bar
        draw_text(self.hud_surf, "Health:", 20, 260, 8)
        for i in range(self.player.max_health):
            col = (200, 20, 20) if i < self.player.health else (100, 100, 100)
            pygame.draw.rect(self.hud_surf, col, (335 + i * 18, 10, 14, 14))
        surf.blit(self.hud_surf, (0, 0))

        # mini map indicator for level end (simple)
        draw_text(surf, "Level length: " + str(self.level.width), font, WIDTH - 220, 8)

    def title_screen(self, surf):
        surf.fill(SKY2)
        draw_text(surf, "SPACE PLATFORMER", big_font, WIDTH // 2, HEIGHT // 3, color=WHITE, center=True)
        draw_text(surf, "Arrow keys / A-D: Move   Up/Space: Jump   J: Shoot", font, WIDTH // 2, HEIGHT // 2, center=True)
        draw_text(surf, "Press ENTER to Start", font, WIDTH // 2, HEIGHT // 2 + 40, center=True)
        draw_text(surf, "P to Pause during gameplay", font, WIDTH // 2, HEIGHT // 2 + 80, center=True)

    def pause_screen(self, surf):
        draw_text(surf, "PAUSED", big_font, WIDTH // 2, HEIGHT // 2 - 20, center=True)
        draw_text(surf, "Press P to resume", font, WIDTH // 2, HEIGHT // 2 + 30, center=True)

    def gameover_screen(self, surf):
        surf.fill((12, 6, 18))
        draw_text(surf, "GAME OVER", big_font, WIDTH // 2, HEIGHT // 3, color=WHITE, center=True)
        draw_text(surf, f"Score: {self.player.score}", font, WIDTH // 2, HEIGHT // 2, center=True)
        draw_text(surf, "Press ENTER to Restart", font, WIDTH // 2, HEIGHT // 2 + 40, center=True)


# -----------------------------
# Main loop
# -----------------------------
def main():
    game = Game()
    dt = 1
    running = True

    while running:
        clock.tick(FPS)
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if game.state == "title":
                    if event.key == pygame.K_RETURN:
                        game.state = "playing"
                elif game.state == "playing":
                    if event.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                        game.player.jump(game.level.platforms)
                    if event.key == pygame.K_j:
                        game.player.shoot(game.bullets)
                    if event.key == pygame.K_p:
                        game.state = "paused"
                elif game.state == "paused":
                    if event.key == pygame.K_p:
                        game.state = "playing"
                elif game.state == "gameover":
                    if event.key == pygame.K_RETURN:
                        game.reset()
                        game.state = "playing"

        # quick keys outside events (hold shooting)
        if game.state == "playing":
            if keys[pygame.K_j]:
                game.player.shoot(game.bullets)

        # update
        if game.state == "playing":
            game.update(dt, keys)

        # draw
        if game.state == "title":
            game.title_screen(screen)
        elif game.state == "playing":
            game.draw(screen)
        elif game.state == "paused":
            game.draw(screen)
            game.pause_screen(screen)
        elif game.state == "gameover":
            game.gameover_screen(screen)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
