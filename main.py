from adodbapi.ado_consts import directions
from docutils.nodes import image
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy import platform
from kivy.core.window import Window
from kivy.uix.image import Image
from kivymd.uix.widget import MDWidget

FPS = 60

BULLET_SPEED = dp(10)
SHIP_SPEED = dp(10)

class MainScreen(MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.eventkeys = {}
        self.cartide = []

    def update(self): #todo
        ...

    def releaseKey(self, key): #todo
        ...


class GameScreen(MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.eventkeys = {}
        self.bullets = []

        self.ship = self.ids.ship

    def update(self): #todo керування кораблем та кулями
        self.ship.update(self.eventkeys)

    def pressKey(self, key): #todo
        ...

    def releaseKey(self, key): #todo
        ...

DIR_UP = 1
DIR_DOWN = -1

class Shot(MDWidget):
    def __init__(self, direction, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction

class Ship(Image):
    def __init__(self,direction = DIR_UP, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction


    def moveleft(self):  # todo
        self.pos[0] -= SHIP_SPEED


    def moveRight(self):  # todo
        self.pos[0] -= SHIP_SPEED


    def shot(self):  # todo
        shot = Shot(self.direction)
        shot.center_x = self.center_x
        shot.center_y = self.top
        self.parent.parent.parent.parent.bullets.append(shot)
        self.parent.add.widget(shot)

class PlayerShip(Ship):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update(self, keys):
        for key in keys:
            if keys[key] == True:
                if key == "left" and self.center_x > 0:
                    self.moveleft()
                if key == "left" and self.center_x < Window.width:
                    self.moveRight()
                if key == "shot":
                    self.shot()

    ...


class EnemyShip(Ship):
    def __init__(self, **kwargs):
        super().__init__(directions=DIR_DOWN, **kwargs)
        self.flame = 0

    def update(self): #todo make a logic
        ...

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
