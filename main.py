from random import randint, choice, uniform

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivy import platform
from kivy.core.window import Window
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivymd.uix.widget import MDWidget

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

FPS = 60

BULLET_SPEED = dp(10)
SHIP_SPEED = dp(10)
ENEMY_SPEED = dp(3)
ENEMY_SPAWN_INTERVAL = 1.5  # секунды

BOSS_APPEAR_DISTANCE = 300  # Дистанция появления босса
BOSS_MAX_HP = 200
PLAYER_MAX_HP = 50

ENEMY_IMAGES = [
    'assets/images/drone.png',
    'assets/images/shahed.png',
]

KEY_A = 97
KEY_D = 100

DIR_UP = 1
DIR_DOWN = -1

SCORE_PER_KILL = 1
DISTANCE_SPEED = 15  # Скорость увеличения дистанции

CLOUD_SPEED = dp(1.5)
CLOUD_SPAWN_INTERVAL = 1.2
CLOUD_SIZE = (dp(150), dp(85))

TILT_ANGLE = 20
TILT_SMOOTHING = 0.25

_HITBOX_FRACTION_CACHE = {}


def get_alpha_hitbox_fractions(source):
    """Возвращает точно рассчитанные границы непрозрачных пикселей из PNG."""
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


class Cloud(Widget):
    def update(self):
        self.y -= CLOUD_SPEED


class Shot(MDWidget):
    def __init__(self, direction, speed=BULLET_SPEED, speed_x=0, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
        self.speed = speed
        self.speed_x = speed_x

    def update(self):
        self.center_y += self.speed * self.direction
        self.center_x += self.speed_x

    def get_hitbox(self):
        return self.x, self.y, self.right, self.top

    def collides_with(self, other):
        return rects_overlap(self.get_hitbox(), other.get_hitbox())


class BossBullet(Widget):
    """Белые круглые пули босса в стиле Undertale."""
    def __init__(self, speed_x=0, speed_y=-dp(4), **kwargs):
        super().__init__(**kwargs)
        self.speed_x = speed_x
        self.speed_y = speed_y
        self.size = (dp(14), dp(14))

    def update(self):
        self.center_x += self.speed_x
        self.center_y += self.speed_y

    def get_hitbox(self):
        return self.x, self.y, self.right, self.top

    def collides_with(self, other):
        return rects_overlap(self.get_hitbox(), other.get_hitbox())


class Ship(Image):
    tilt_angle = NumericProperty(0)

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
        if game_screen:
            game_screen.bullets.append(shot)
            game_screen.ids.front.add_widget(shot)

    def get_game_screen(self):
        widget = self
        while widget is not None and not isinstance(widget, GameScreen):
            widget = widget.parent
        return widget

    def get_hitbox(self):
        left_frac, right_frac, bottom_frac, top_frac = get_alpha_hitbox_fractions(self.source)
        img_w, img_h = self.norm_image_size if self.norm_image_size[0] > 0 else self.size
        img_left = self.center_x - img_w / 2
        img_bottom = self.center_y - img_h / 2
        x1 = img_left + left_frac * img_w
        x2 = img_left + right_frac * img_w
        y1 = img_bottom + bottom_frac * img_h
        y2 = img_bottom + top_frac * img_h
        return x1, y1, x2, y2

    def collides_with(self, other):
        return rects_overlap(self.get_hitbox(), other.get_hitbox())


class PlayerShip(Ship):
    def __init__(self, **kwargs):
        super().__init__(direction=DIR_UP, **kwargs)

    def update(self, keys):
        moving_left = keys.get('left', False)
        moving_right = keys.get('right', False)

        if moving_left and self.center_x > dp(20):
            self.moveLeft()
        if moving_right and self.center_x < Window.width - dp(20):
            self.moveRight()
        if keys.get('shot'):
            self.shot()
            keys['shot'] = False

        if moving_left and not moving_right:
            target_angle = TILT_ANGLE
        elif moving_right and not moving_left:
            target_angle = -TILT_ANGLE
        else:
            target_angle = 0
        self.tilt_angle += (target_angle - self.tilt_angle) * TILT_SMOOTHING


class EnemyShip(Ship):
    def __init__(self, *args, **kwargs):
        super().__init__(direction=DIR_DOWN, **kwargs)
        self.source = choice(ENEMY_IMAGES)

    def update(self):
        self.pos[1] += ENEMY_SPEED * self.direction


class BossShip(Ship):
    hp = NumericProperty(BOSS_MAX_HP)
    max_hp = NumericProperty(BOSS_MAX_HP)

    def __init__(self, **kwargs):
        super().__init__(direction=DIR_DOWN, **kwargs)
        self.source = 'assets/images/boss.png'
        self.speed_x = dp(2.5)
        self.attack_timer = 0

    def update(self):
        # Движение влево-вправо
        self.x += self.speed_x
        if self.x <= dp(10) or self.right >= Window.width - dp(10):
            self.speed_x *= -1

        # Атака белыми пулями каждые 40 кадров
        self.attack_timer += 1
        if self.attack_timer >= 40:
            self.attack_timer = 0
            self.shoot_attack()

    def shoot_attack(self):
        game_screen = self.get_game_screen()
        if not game_screen:
            return

        # Залп из пуль под разными углами
        for vx in [-dp(2), 0, dp(2)]:
            bullet = BossBullet(speed_x=vx, speed_y=-dp(4))
            bullet.center_x = self.center_x
            bullet.center_y = self.y
            game_screen.boss_bullets.append(bullet)
            game_screen.ids.front.add_widget(bullet)


class MainScreen(MDScreen):
    pass


class GameScreen(MDScreen):
    score = NumericProperty(0)
    distance = NumericProperty(0)
    player_hp = NumericProperty(PLAYER_MAX_HP)
    player_max_hp = NumericProperty(PLAYER_MAX_HP)
    boss_hp = NumericProperty(BOSS_MAX_HP)
    boss_max_hp = NumericProperty(BOSS_MAX_HP)
    is_boss_fight = ObjectProperty(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eventkeys = {}
        self.bullets = []
        self.enemyShips = []
        self.boss_bullets = []
        self.clouds = []
        self.boss = None

    def on_enter(self, *args):
        self.ship = self.ids.ship
        if not hasattr(self, 'ship_start_pos'):
            self.ship_start_pos = tuple(self.ship.pos)
        self.reset_state()
        self.resume_game()
        Window.bind(on_key_down=self.on_key_down, on_key_up=self.on_key_up)
        return super().on_enter(*args)

    def on_leave(self, *args):
        self.pause_game()
        Window.unbind(on_key_down=self.on_key_down, on_key_up=self.on_key_up)
        return super().on_leave(*args)

    def reset_state(self):
        for shot in self.bullets[:]:
            self.remove_bullet(shot)
        for enemy in self.enemyShips[:]:
            self.remove_enemy(enemy)
        for bb in self.boss_bullets[:]:
            self.remove_boss_bullet(bb)
        for cloud in self.clouds[:]:
            self.remove_cloud(cloud)

        if self.boss:
            self.ids.front.remove_widget(self.boss)
            self.boss = None

        self.eventkeys = {}
        self.score = 0
        self.distance = 0
        self.player_hp = PLAYER_MAX_HP
        self.is_boss_fight = False
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
        if self.is_boss_fight:
            return
        ship = EnemyShip()
        ship.pos = (randint(0, int(Window.width - ship.width)), Window.height)
        self.enemyShips.append(ship)
        self.ids.front.add_widget(ship)

    def spawn_cloud(self, dt):
        cloud = Cloud(size=CLOUD_SIZE)
        cloud.pos = (randint(0, int(Window.width - cloud.width)), Window.height)
        self.clouds.append(cloud)
        self.ids.back.add_widget(cloud)

    def start_boss_fight(self):
        self.is_boss_fight = True
        # Очищаем рядовых врагов
        for enemy in self.enemyShips[:]:
            self.remove_enemy(enemy)

        # Создаём босса
        self.boss = BossShip(size=(dp(120), dp(120)))
        self.boss.pos = (Window.width / 2 - dp(60), Window.height - dp(140))
        self.boss_hp = BOSS_MAX_HP
        self.ids.front.add_widget(self.boss)

    def update(self, dt):
        self.ship.update(self.eventkeys)

        if not self.is_boss_fight:
            self.distance += dt * DISTANCE_SPEED
            if self.distance >= BOSS_APPEAR_DISTANCE:
                self.start_boss_fight()
        else:
            if self.boss:
                self.boss.update()
                self.boss_hp = self.boss.hp

        # Обновление пуль игрока
        for shot in self.bullets[:]:
            shot.update()
            if shot.y > Window.height or shot.top < 0:
                self.remove_bullet(shot)

        # Обновление белых пуль босса
        for bb in self.boss_bullets[:]:
            bb.update()
            if bb.top < 0 or bb.right < 0 or bb.x > Window.width:
                self.remove_boss_bullet(bb)

        # Рядовые враги
        for enemy in self.enemyShips[:]:
            enemy.update()
            if enemy.top < 0:
                self.remove_enemy(enemy)

        # Облака
        for cloud in self.clouds[:]:
            cloud.update()
            if cloud.top < 0:
                self.remove_cloud(cloud)

        self.check_collisions()

    def check_collisions(self):
        # 1. Пули игрока с обычными врагами
        for shot in self.bullets[:]:
            for enemy in self.enemyShips[:]:
                if shot.collides_with(enemy):
                    self.remove_bullet(shot)
                    self.remove_enemy(enemy)
                    self.score += SCORE_PER_KILL
                    break

        # 2. Пули игрока с Боссом (каждая пуля сносит 10 HP)
        if self.is_boss_fight and self.boss:
            for shot in self.bullets[:]:
                if shot.collides_with(self.boss):
                    self.remove_bullet(shot)
                    self.boss.hp -= 10
                    self.boss_hp = max(0, self.boss.hp)
                    if self.boss.hp <= 0:
                        self.remove_boss()
                        self.game_victory()
                        return

        # 3. Белые пули Босса с Игроком (-10 HP)
        for bb in self.boss_bullets[:]:
            if bb.collides_with(self.ship):
                self.remove_boss_bullet(bb)
                self.player_hp -= 10
                if self.player_hp <= 0:
                    self.player_hp = 0
                    self.game_over()
                    return

        # 4. Столкновение Игрока с обычными врагами или с самим Боссом (смерть)
        for enemy in self.enemyShips[:]:
            if self.ship.collides_with(enemy):
                self.player_hp = 0
                self.game_over()
                return

        if self.is_boss_fight and self.boss and self.ship.collides_with(self.boss):
            self.player_hp = 0
            self.game_over()

    def game_over(self):
        if getattr(self, 'game_over_dialog', None) is not None:
            return
        self.pause_game()
        self.open_dialog(title="Тібі підбілі", text="Політіть знову?")

    def game_victory(self):
        if getattr(self, 'game_over_dialog', None) is not None:
            return
        self.pause_game()
        self.open_dialog(title="Перемога!", text="Босс знищений! Політіть знову?")

    def pause_game(self):
        if hasattr(self, 'updateEvent'):
            self.updateEvent.cancel()
        if hasattr(self, 'spawnEvent'):
            self.spawnEvent.cancel()
        if hasattr(self, 'cloudSpawnEvent'):
            self.cloudSpawnEvent.cancel()

    def resume_game(self):
        self.updateEvent = Clock.schedule_interval(self.update, 1 / FPS)
        self.spawnEvent = Clock.schedule_interval(self.spawn_enemy, ENEMY_SPAWN_INTERVAL)
        self.cloudSpawnEvent = Clock.schedule_interval(self.spawn_cloud, CLOUD_SPAWN_INTERVAL)

    def open_dialog(self, title, text):
        self.game_over_dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDFlatButton(text="НЕ ПОТУЖНО", on_release=lambda *a: self.on_game_over_menu()),
                MDFlatButton(text="ЗНОВУ", on_release=lambda *a: self.on_game_over_restart()),
            ],
        )
        self.game_over_dialog.open()

    def close_game_over_dialog(self):
        if getattr(self, 'game_over_dialog', None) is not None:
            self.game_over_dialog.dismiss()
            self.game_over_dialog = None

    def on_game_over_restart(self):
        self.close_game_over_dialog()
        self.reset_state()
        self.resume_game()

    def on_game_over_menu(self):
        self.close_game_over_dialog()
        self.manager.current = 'main'

    def remove_bullet(self, shot):
        if shot in self.bullets:
            self.bullets.remove(shot)
        self.ids.front.remove_widget(shot)

    def remove_boss_bullet(self, bb):
        if bb in self.boss_bullets:
            self.boss_bullets.remove(bb)
        self.ids.front.remove_widget(bb)

    def remove_enemy(self, enemy):
        if enemy in self.enemyShips:
            self.enemyShips.remove(enemy)
        self.ids.front.remove_widget(enemy)

    def remove_boss(self):
        if self.boss:
            self.ids.front.remove_widget(self.boss)
            self.boss = None

    def remove_cloud(self, cloud):
        if cloud in self.clouds:
            self.clouds.remove(cloud)
        self.ids.back.remove_widget(cloud)

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