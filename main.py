from random import randint, choice

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy import platform
from kivy.core.window import Window
from kivy.uix.image import Image
from kivymd.uix.widget import MDWidget

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

FPS = 60

BULLET_SPEED = dp(10)
SHIP_SPEED = dp(10)
ENEMY_SPEED = dp(3)
ENEMY_SPAWN_INTERVAL = 1.5  # секунди

ENEMY_IMAGES = [
    'assets/images/drone.png',
    'assets/images/shahed.png',
]

KEY_A = 97
KEY_D = 100

DIR_UP = 1
DIR_DOWN = -1

SCORE_PER_KILL = 10  # Очки за збитий ворожий корабель
DISTANCE_SPEED = 5   # Дистанція в метрах за секунду

_HITBOX_FRACTION_CACHE = {}


def get_alpha_hitbox_fractions(source):
    if source in _HITBOX_FRACTION_CACHE:
        return _HITBOX_FRACTION_CACHE[source]

    fractions = (0.0, 1.0, 0.0, 1.0)
    if PILImage is not None:
        try:
            img = PILImage.open(source).convert('RGBA')
            bbox = img.getbbox()
            if bbox is not None:
                w, h = img.size
                left, upper, right, lower = bbox
                left_frac = left / w
                right_frac = right / w
                bottom_frac = 1 - (lower / h)
                top_frac = 1 - (upper / h)
                fractions = (left_frac, right_frac, bottom_frac, top_frac)
        except Exception:
            pass

    _HITBOX_FRACTION_CACHE[source] = fractions
    return fractions


def rects_overlap(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


class Shot(MDWidget):
    def __init__(self, direction, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction

    def update(self):
        self.center_y += BULLET_SPEED * self.direction

    def get_hitbox(self):
        return self.x, self.y, self.right, self.top

    def collides_with(self, other):
        return rects_overlap(self.get_hitbox(), other.get_hitbox())


class Ship(Image):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction

    def moveLeft(self):
        self.pos[0] -= SHIP_SPEED

    def moveRight(self):
        self.pos[0] += SHIP_SPEED

    def shot(self):
        shot = Shot(self.direction)
        shot.center_x = self.center_x
        shot.center_y = self.top
        game_screen = self.get_game_screen()
        game_screen.bullets.append(shot)
        self.parent.add_widget(shot)

    def get_game_screen(self):
        widget = self
        while widget is not None and not isinstance(widget, GameScreen):
            widget = widget.parent
        return widget

    def get_hitbox(self):
        left_frac, right_frac, bottom_frac, top_frac = get_alpha_hitbox_fractions(self.source)
        img_w, img_h = self.norm_image_size
        img_left = self.center_x - img_w / 2
        img_bottom = self.center_y - img_h / 2
        x1 = img_left + left_frac * img_w
        x2 = img_left + right_frac * img_w
        y1 = img_bottom + bottom_frac * img_h
        y2 = img_bottom + top_frac * img_h
        return x1, y1, x2, y2

    def collides_with(self, other):
        return rects_overlap(self.get_hitbox(), other.get_hitbox())

    def update(self):
        ...


class PlayerShip(Ship):
    def __init__(self, **kwargs):
        super().__init__(direction=DIR_UP, **kwargs)

    def update(self, keys):
        for key in keys:
            if keys[key]:
                if key == 'left' and self.center_x > 0:
                    self.moveLeft()
                if key == 'right' and self.center_x < Window.width:
                    self.moveRight()
                if key == 'shot':
                    self.shot()
                    keys[key] = False


class EnemyShip(Ship):
    def __init__(self, *args, **kwargs):
        super().__init__(direction=DIR_DOWN, **kwargs)
        self.frame = 0
        self.source = choice(ENEMY_IMAGES)

    def update(self):
        self.pos[1] += ENEMY_SPEED * self.direction


class MainScreen(MDScreen):
    ...


class GameScreen(MDScreen):
    score = NumericProperty(0)
    distance = NumericProperty(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.eventkeys = {}
        self.bullets = []
        self.enemyShips = []

    def on_enter(self, *args):
        self.ship = self.ids.ship
        if not hasattr(self, 'ship_start_pos'):
            self.ship_start_pos = tuple(self.ship.pos)
        self.reset_state()
        self.updateEvent = Clock.schedule_interval(self.update, 1 / FPS)
        self.spawnEvent = Clock.schedule_interval(self.spawn_enemy, ENEMY_SPAWN_INTERVAL)
        Window.bind(on_key_down=self.on_key_down, on_key_up=self.on_key_up)
        return super().on_enter(*args)

    def on_leave(self, *args):
        if hasattr(self, 'updateEvent'):
            self.updateEvent.cancel()
        if hasattr(self, 'spawnEvent'):
            self.spawnEvent.cancel()
        Window.unbind(on_key_down=self.on_key_down, on_key_up=self.on_key_up)
        return super().on_leave(*args)

    def reset_state(self):
        for shot in self.bullets[:]:
            self.remove_bullet(shot)
        for enemy in self.enemyShips[:]:
            self.remove_enemy(enemy)
        self.eventkeys = {}
        self.score = 0
        self.distance = 0
        self.ship.pos = self.ship_start_pos

    def on_key_down(self, window, key, scancode, codepoint, modifier):
        if key == KEY_A:
            self.pressKey('left')
        elif key == KEY_D:
            self.pressKey('right')

    def on_key_up(self, window, key, scancode, *args):
        if key == KEY_A:
            self.releaseKey('left')
        elif key == KEY_D:
            self.releaseKey('right')

    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        if getattr(touch, 'button', 'left') == 'left':
            self.pressKey('shot')
            return True
        return False

    def spawn_enemy(self, dt):
        ship = EnemyShip()
        ship.pos = (randint(0, int(Window.width - ship.width)), Window.height)
        self.enemyShips.append(ship)
        self.ids.front.add_widget(ship)

    def update(self, dt):
        self.ship.update(self.eventkeys)
        self.distance += dt * DISTANCE_SPEED

        for shot in self.bullets[:]:
            shot.update()
            if shot.top < 0 or shot.center_y > Window.height:
                self.remove_bullet(shot)

        for enemy in self.enemyShips[:]:
            enemy.update()
            if enemy.top < 0:
                self.remove_enemy(enemy)

        self.check_collisions()

    def check_collisions(self):
        for shot in self.bullets[:]:
            for enemy in self.enemyShips[:]:
                if shot.collides_with(enemy):
                    self.remove_bullet(shot)
                    self.remove_enemy(enemy)
                    self.score += SCORE_PER_KILL  # Нараховуємо очки за знищення ворога
                    break

        for enemy in self.enemyShips[:]:
            if self.ship.collides_with(enemy):
                self.game_over()
                return

    def game_over(self):
        self.manager.current = 'main'

    def remove_bullet(self, shot):
        if shot in self.bullets:
            self.bullets.remove(shot)
        self.ids.front.remove_widget(shot)

    def remove_enemy(self, enemy):
        if enemy in self.enemyShips:
            self.enemyShips.remove(enemy)
        self.ids.front.remove_widget(enemy)

    def show_menu(self):
        self.manager.current = 'main'

    def pressKey(self, key):
        self.eventkeys[key] = True

    def releaseKey(self, key):
        self.eventkeys[key] = False


class ShooterApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"

        self.sm = MDScreenManager()

        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(GameScreen(name='game'))

        return self.sm


if platform != 'android':
    Window.size = (450, 900)
    Window.top = 100
    Window.left = 600

app = ShooterApp()
app.run()