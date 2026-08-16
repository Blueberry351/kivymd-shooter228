from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy import platform
from kivy.core.window import Window

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

    def moveleft(self): #todo
        ...

    def moveRight(self):  # todo
        ...

    def shot(self): #todo
        ...

class GameScreen(MDScreen):
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
