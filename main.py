import os
from random import randint, choice

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.core.audio import SoundLoader
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.slider import MDSlider
from kivy import platform
from kivy.core.window import Window
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivymd.uix.widget import MDWidget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivymd.uix.label import MDLabel
from kivy.graphics import Color, Rectangle, Line

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

FPS = 60

BULLET_SPEED = dp(10)
SHIP_SPEED = dp(10)
ENEMY_SPEED = dp(3)
ENEMY_SPAWN_INTERVAL = 1.5

BOSS_APPEAR_DISTANCE = 700
BOSS_MAX_HP = 200
PLAYER_MAX_HP = 100

ENEMY_IMAGES = [
    'assets/images/drone.png',
    'assets/images/shahed.png',
]

KEY_A = 97
KEY_D = 100

DIR_UP = 1
DIR_DOWN = -1

SCORE_PER_KILL = 1
DISTANCE_SPEED = 15

CLOUD_SPEED = dp(1.5)
CLOUD_SPAWN_INTERVAL = 1.2
CLOUD_SIZE = (dp(150), dp(85))

TILT_ANGLE = 20
TILT_SMOOTHING = 0.25

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


class AnimatedButton(MDRaisedButton):
    def on_press(self):

        anim = Animation(opacity=0.6, d=0.08) + Animation(opacity=1.0, d=0.08)
        anim.start(self)
        super().on_press()


class StoryDialogBox(FloatLayout):
    speaker_text = StringProperty("")
    dialog_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, None)
        self.height = dp(180)
        self.pos_hint = {'x': 0, 'y': 0}

        with self.canvas.before:
            Color(0.08, 0.08, 0.12, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            Color(0.9, 0.6, 0.2, 1)
            self.border_line = Line(rectangle=(self.x, self.y, self.width, self.height), width=dp(2))

        self.bind(pos=self._update_graphics, size=self._update_graphics)

        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(5), pos_hint={'x': 0, 'y': 0}, size_hint=(1, 1))

        self.speaker_label = MDLabel(
            text="",
            font_style="H6",
            bold=True,
            theme_text_color="Custom",
            text_color=(0.9, 0.6, 0.2, 1),
            size_hint_y=None,
            height=dp(30)
        )

        self.dialog_label = MDLabel(
            text="",
            font_style="Subtitle1",
            bold=True,
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            valign="top"
        )
        self.dialog_label.bind(size=self.dialog_label.setter('text_size'))

        hint_label = MDLabel(
            text="[ » ]",
            font_style="Caption",
            halign="right",
            theme_text_color="Custom",
            text_color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None,
            height=dp(20)
        )

        layout.add_widget(self.speaker_label)
        layout.add_widget(self.dialog_label)
        layout.add_widget(hint_label)
        self.add_widget(layout)

    def _update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rectangle = (self.x, self.y, self.width, self.height)

    def set_content(self, speaker, text):
        self.speaker_label.text = speaker
        self.dialog_label.text = text


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
        self.x += self.speed_x
        if self.x <= dp(10) or self.right >= Window.width - dp(10):
            self.speed_x *= -1

        self.attack_timer += 1
        if self.attack_timer >= 40:
            self.attack_timer = 0
            self.shoot_attack()

    def shoot_attack(self):
        game_screen = self.get_game_screen()
        if not game_screen:
            return

        for vx in [-dp(2), 0, dp(2)]:
            bullet = BossBullet(speed_x=vx, speed_y=-dp(4))
            bullet.center_x = self.center_x
            bullet.center_y = self.y
            game_screen.boss_bullets.append(bullet)
            game_screen.ids.front.add_widget(bullet)


class MainScreen(MDScreen):
    def open_settings(self):
        app = MDApp.get_running_app()
        app.open_settings_dialog()


class GameScreen(MDScreen):
    score = NumericProperty(0)
    distance = NumericProperty(0)
    player_hp = NumericProperty(PLAYER_MAX_HP)
    player_max_hp = NumericProperty(PLAYER_MAX_HP)
    boss_hp = NumericProperty(BOSS_MAX_HP)
    boss_max_hp = NumericProperty(BOSS_MAX_HP)
    is_boss_fight = ObjectProperty(False)
    in_dialog = BooleanProperty(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eventkeys = {}
        self.bullets = []
        self.enemyShips = []
        self.boss_bullets = []
        self.clouds = []
        self.boss = None
        self.dialog_box = None
        self.current_dialog_sequence = []
        self.dialog_index = 0
        self.on_dialog_finish_callback = None
        self.boss_defeated = False
        self.current_dialog_sound = None

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
        self.stop_dialog_sound()
        app = MDApp.get_running_app()
        app.stop_music()
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

        if self.dialog_box:
            self.remove_widget(self.dialog_box)
            self.dialog_box = None

        self.stop_dialog_sound()
        self.eventkeys = {}
        self.score = 0
        self.distance = 0
        self.player_hp = PLAYER_MAX_HP
        self.is_boss_fight = False
        self.in_dialog = False
        self.boss_defeated = False
        self.ship.pos = self.ship_start_pos

        app = MDApp.get_running_app()
        app.play_bg_music()

    def stop_dialog_sound(self):
        if self.current_dialog_sound:
            self.current_dialog_sound.stop()
            self.current_dialog_sound = None

    def play_dialog_voice(self, speaker):
        self.stop_dialog_sound()
        app = MDApp.get_running_app()

        sound_file = None
        if speaker == "Балістіка":
            sound_file = 'assets/audio/voice_boss.mp3'
        elif speaker == "Зеленский":
            sound_file = 'assets/audio/zelensky.mp3'

        if sound_file and os.path.exists(sound_file):
            sound = SoundLoader.load(sound_file)
            if sound:
                sound.volume = app.voice_volume
                sound.play()
                self.current_dialog_sound = sound

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
        if self.in_dialog:
            self.advance_dialog()
            return True

        if super().on_touch_down(touch):
            return True
        if getattr(touch, 'button', 'left') == 'left':
            self.pressKey('shot')
            return True
        return False

    def start_story_dialog(self, sequence, finish_callback=None):
        self.in_dialog = True
        self.current_dialog_sequence = sequence
        self.dialog_index = 0
        self.on_dialog_finish_callback = finish_callback

        app = MDApp.get_running_app()
        app.stop_music()

        if not self.dialog_box:
            self.dialog_box = StoryDialogBox()
            self.add_widget(self.dialog_box)

        self.show_current_dialog_step()

    def show_current_dialog_step(self):
        if self.dialog_index < len(self.current_dialog_sequence):
            speaker, text = self.current_dialog_sequence[self.dialog_index]
            self.dialog_box.set_content(speaker, text)
            self.play_dialog_voice(speaker)
        else:
            self.finish_story_dialog()

    def advance_dialog(self):
        self.dialog_index += 1
        if self.dialog_index < len(self.current_dialog_sequence):
            self.show_current_dialog_step()
        else:
            self.finish_story_dialog()

    def finish_story_dialog(self):
        self.stop_dialog_sound()
        self.in_dialog = False
        if self.dialog_box:
            self.remove_widget(self.dialog_box)
            self.dialog_box = None

        if self.on_dialog_finish_callback:
            callback = self.on_dialog_finish_callback
            self.on_dialog_finish_callback = None
            callback()

    def spawn_enemy(self, dt):
        if self.is_boss_fight or self.in_dialog:
            return
        ship = EnemyShip()
        ship.pos = (randint(0, int(Window.width - ship.width)), Window.height)
        self.enemyShips.append(ship)
        self.ids.front.add_widget(ship)

    def spawn_cloud(self, dt):
        if self.is_boss_fight or self.in_dialog:
            return
        cloud = Cloud(size=CLOUD_SIZE)
        cloud.pos = (randint(0, int(Window.width - cloud.width)), Window.height)
        self.clouds.append(cloud)
        self.ids.back.add_widget(cloud)

    def trigger_boss_encounter(self):
        self.is_boss_fight = True

        for enemy in self.enemyShips[:]:
            self.remove_enemy(enemy)
        for cloud in self.clouds[:]:
            self.remove_cloud(cloud)

        self.boss = BossShip(size=(dp(160), dp(160)))
        self.boss.pos = (Window.width / 2 - dp(80), Window.height - dp(200))
        self.boss_hp = BOSS_MAX_HP
        self.ids.front.add_widget(self.boss)

        intro_dialog = [
            ("", "*летіть що то не потужне*"),
            ("Балістіка", "Зілінський?! опять ті!??"),
            ("Зеленский", "ну готовся, щя будемо тобі moggати")
        ]

        def start_boss_music_fight():
            app = MDApp.get_running_app()
            app.play_boss_music()

        self.start_story_dialog(intro_dialog, finish_callback=start_boss_music_fight)

    def trigger_boss_defeat(self):
        self.score += 50

        app = MDApp.get_running_app()
        app.stop_music()

        outro_dialog = [
            ("Балістіка", "це ще ні кініць!!!"),
            ("Зеленский", "я же говорив що я тебе moggну")
        ]

        def resume_normal_flight():
            self.remove_boss()
            for bb in self.boss_bullets[:]:
                self.remove_boss_bullet(bb)
            self.is_boss_fight = False
            self.boss_defeated = True
            app.play_bg_music()

        self.start_story_dialog(outro_dialog, finish_callback=resume_normal_flight)

    def update(self, dt):
        if self.in_dialog:
            return

        self.ship.update(self.eventkeys)

        if not self.is_boss_fight:
            self.distance += dt * DISTANCE_SPEED
            if self.distance >= BOSS_APPEAR_DISTANCE and not self.boss_defeated and self.boss is None:
                self.trigger_boss_encounter()
        else:
            if self.boss:
                self.boss.update()
                self.boss_hp = self.boss.hp

        for shot in self.bullets[:]:
            shot.update()
            if shot.y > Window.height or shot.top < 0:
                self.remove_bullet(shot)

        for bb in self.boss_bullets[:]:
            bb.update()
            if bb.top < 0 or bb.right < 0 or bb.x > Window.width:
                self.remove_boss_bullet(bb)

        for enemy in self.enemyShips[:]:
            enemy.update()
            if enemy.top < 0:
                self.remove_enemy(enemy)

        for cloud in self.clouds[:]:
            cloud.update()
            if cloud.top < 0:
                self.remove_cloud(cloud)

        self.check_collisions()

    def check_collisions(self):
        if self.in_dialog:
            return

        for shot in self.bullets[:]:
            for enemy in self.enemyShips[:]:
                if shot.collides_with(enemy):
                    self.remove_bullet(shot)
                    self.remove_enemy(enemy)
                    self.score += SCORE_PER_KILL
                    break

        if self.is_boss_fight and self.boss:
            for shot in self.bullets[:]:
                if shot.collides_with(self.boss):
                    self.remove_bullet(shot)
                    self.boss.hp -= 10
                    self.boss_hp = max(0, self.boss.hp)
                    if self.boss.hp <= 0:
                        self.trigger_boss_defeat()
                        return

        for bb in self.boss_bullets[:]:
            if bb.collides_with(self.ship):
                self.remove_boss_bullet(bb)
                self.player_hp -= 10
                if self.player_hp <= 0:
                    self.player_hp = 0
                    self.game_over()
                    return

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
        self.stop_dialog_sound()
        app = MDApp.get_running_app()
        app.stop_music()
        self.open_dialog(title="Тібі підбілі", text="Політіть знову?")

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
            auto_dismiss=False,
            buttons=[
                AnimatedButton(text="НЕ ПОТУЖНО", on_release=lambda *a: self.on_game_over_menu()),
                AnimatedButton(text="ЗНОВУ", on_release=lambda *a: self.on_game_over_restart()),
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
    music_volume = NumericProperty(0.7)
    voice_volume = NumericProperty(0.9)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_music = None
        self.settings_dialog = None

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"

        self.sm = MDScreenManager()
        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(GameScreen(name='game'))
        return self.sm

    def play_bg_music(self):
        self.stop_music()
        path = 'assets/audio/Glamour.mp3'
        if os.path.exists(path):
            self.current_music = SoundLoader.load(path)
            if self.current_music:
                self.current_music.loop = True
                self.current_music.volume = self.music_volume
                self.current_music.play()

    def play_boss_music(self):
        self.stop_music()
        path = 'assets/audio/Thundersnail.mp3'
        if os.path.exists(path):
            self.current_music = SoundLoader.load(path)
            if self.current_music:
                self.current_music.loop = True
                self.current_music.volume = self.music_volume
                self.current_music.play()

    def stop_music(self):
        if self.current_music:
            self.current_music.stop()
            self.current_music = None

    def update_music_volume(self, instance, value):
        self.music_volume = value / 100.0
        if self.current_music:
            self.current_music.volume = self.music_volume

    def update_voice_volume(self, instance, value):
        self.voice_volume = value / 100.0

    def open_settings_dialog(self):
        content = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(160))

        content.add_widget(MDLabel(text="Громкость музыки", theme_text_color="Secondary", size_hint_y=None, height=dp(20)))
        slider_music = MDSlider(min=0, max=100)
        slider_music.value = self.music_volume * 100
        slider_music.bind(value=self.update_music_volume)
        content.add_widget(slider_music)

        content.add_widget(MDLabel(text="Громкость диалогов", theme_text_color="Secondary", size_hint_y=None, height=dp(20)))
        slider_voice = MDSlider(min=0, max=100)
        slider_voice.value = self.voice_volume * 100
        slider_voice.bind(value=self.update_voice_volume)
        content.add_widget(slider_voice)

        self.settings_dialog = MDDialog(
            title="Настройки звука",
            type="custom",
            content_cls=content,
            buttons=[
                AnimatedButton(text="ЗАКРЫТЬ", on_release=lambda *a: self.settings_dialog.dismiss())
            ]
        )
        self.settings_dialog.open()


if platform != 'android':
    Window.size = (450, 900)
    Window.top = 100
    Window.left = 600

app = ShooterApp()
app.run()