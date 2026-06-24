# -*- coding: utf-8 -*-
"""
Hidratación de Ranita — versión Android (Kivy)
Réplica de la app de escritorio para Samsung One UI 5.1 / Android 13.
"""

import os
import json
import datetime
from kivy.utils import platform
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.properties import NumericProperty
from kivy.metrics import dp

# ── Permiso de notificaciones en Android 13+ (One UI 5.1 lo exige) ─────────────
if platform == "android":
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.POST_NOTIFICATIONS])
    except Exception:
        pass

def notify_system(title, msg):
    """Notificación nativa de Android (aparece en la barra de notificaciones)."""
    if platform == "android":
        try:
            from plyer import notification
            notification.notify(title=title, message=msg, timeout=10)
        except Exception:
            pass

# ── Configuración general ───────────────────────────────────────────────────────
META_ML = 2000
BOTELLA_ML = 500
BOTELLAS_META = META_ML // BOTELLA_ML
REMINDER_MINUTES = 45

# ── Paleta pastel ────────────────────────────────────────────────────────────────
def hexc(h, a=1):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b, a)

COLORS = {
    "bg":          hexc("FFF0F5"),
    "bg2":         hexc("FFE4EF"),
    "pink":        hexc("FF85A1"),
    "pink_light":  hexc("FFB3C6"),
    "pink_dark":   hexc("E8638A"),
    "lavender":    hexc("C9B8FF"),
    "mint":        hexc("B8F0D8"),
    "peach":       hexc("FFD4B8"),
    "yellow":      hexc("FFF3B0"),
    "text":        hexc("5A3A4A"),
    "text_light":  hexc("A07080"),
    "water_empty": hexc("F5D0DF"),
    "water_full":  hexc("FF85A1"),
    "white":       hexc("FFFFFF"),
    "shadow":      hexc("F0C8D8"),
}

Window.clearcolor = COLORS["bg"]

# ── Rutas de datos y sonidos ─────────────────────────────────────────────────────
def data_file():
    app = App.get_running_app()
    base = app.user_data_dir if app else "."
    return os.path.join(base, "agua_data.json")

def sound_path(filename):
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "sounds", filename)

_sound_cache = {}

def play_sound(filename):
    """Reproduce un sonido de la carpeta /sounds usando el motor de audio de Kivy."""
    try:
        path = sound_path(filename)
        if not os.path.exists(path):
            print(f"[sonido] no encontrado: {filename}")
            return
        snd = SoundLoader.load(path)
        if snd:
            snd.play()
            _sound_cache[filename] = snd  # evita que el garbage collector lo corte
    except Exception as e:
        print(f"[sonido error] {filename}: {e}")

# ── Persistencia ──────────────────────────────────────────────────────────────────
def load_data():
    today = datetime.date.today().isoformat()
    f = data_file()
    if os.path.exists(f):
        try:
            with open(f) as fh:
                d = json.load(fh)
            if d.get("date") == today:
                return d
        except Exception:
            pass
    return {"date": today, "botellas": 0, "extra": 0}

def load_history():
    f = data_file()
    if os.path.exists(f):
        try:
            with open(f) as fh:
                return json.load(fh).get("history", {})
        except Exception:
            pass
    return {}

def save_data(botellas, extra):
    today = datetime.date.today().isoformat()
    history = load_history()
    history[today] = {
        "botellas": botellas, "extra": extra,
        "ml": botellas * BOTELLA_ML + extra * BOTELLA_ML,
    }
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    history = {k: v for k, v in history.items() if k >= cutoff}
    with open(data_file(), "w") as fh:
        json.dump({"date": today, "botellas": botellas,
                   "extra": extra, "history": history}, fh)

# ── Widgets reutilizables ────────────────────────────────────────────────────────
class RoundedBox(BoxLayout):
    """Frame con fondo de color y bordes redondeados."""
    def __init__(self, bg=COLORS["bg2"], radius=20, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*bg)
            self._rect = RoundedRectangle(radius=[radius])
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class RoundedButton(Button):
    """Botón sin estilo nativo de Kivy, con fondo redondeado custom."""
    def __init__(self, bg=COLORS["pink"], fg=COLORS["white"], radius=28, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = fg
        self._bg = bg
        self._radius = radius
        with self.canvas.before:
            Color(*bg)
            self._rect = RoundedRectangle(radius=[radius])
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, color):
        self._bg = color
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*color)
            self._rect = RoundedRectangle(radius=[self._radius])
        self._update()


class BottleRow(Widget):
    """Dibuja las 4 botellas de 500ml según el progreso del día."""
    filled = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._redraw, size=self._redraw, filled=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        total = BOTELLAS_META
        bw, bh = dp(46), dp(86)
        gap = dp(16)
        total_w = total * bw + (total - 1) * gap
        start_x = self.x + (self.width - total_w) / 2
        y = self.y + dp(10)

        with self.canvas:
            for i in range(total):
                x = start_x + i * (bw + gap)
                is_filled = i < self.filled
                # cuello
                Color(*(COLORS["pink_light"] if is_filled else COLORS["water_empty"]))
                Rectangle(pos=(x + bw*0.32, y + bh), size=(bw*0.36, dp(12)))
                # tapa
                Color(*(COLORS["pink_dark"] if is_filled else COLORS["shadow"]))
                Rectangle(pos=(x + bw*0.28, y + bh + dp(10)), size=(bw*0.44, dp(8)))
                # cuerpo
                Color(*(COLORS["water_full"] if is_filled else COLORS["water_empty"]))
                RoundedRectangle(pos=(x, y), size=(bw, bh), radius=[dp(6)])


class ProgressTrack(Widget):
    """Barra de progreso redondeada custom."""
    ratio = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._redraw, size=self._redraw, ratio=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*COLORS["water_empty"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.height/2])
            Color(*COLORS["pink"])
            w = max(self.height, self.width * min(self.ratio, 1.0))
            RoundedRectangle(pos=self.pos, size=(w, self.height), radius=[self.height/2])


# ── App principal ─────────────────────────────────────────────────────────────────
MOTIVATIONS = [
    "¡Vamos mi vida, vos podés! 💪🐸",
    "¡Muy bien corazón, seguí así! Te amo 🌸",
    "¡Ya la mitad! Sos la mejor Jime 💧",
    "¡Dale mi amor, ya casi estás! 🎀",
    "🎉 ¡Lo lograste mi vida! ¡Te amo tanto! 🎉",
    "✨ ¡Sos increíble! ¡Te amo con todo! ✨",
]

DIAS_ES = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles",
           "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}
MESES_ES = {"January":"enero","February":"febrero","March":"marzo","April":"abril",
            "May":"mayo","June":"junio","July":"julio","August":"agosto",
            "September":"septiembre","October":"octubre","November":"noviembre",
            "December":"diciembre"}
DIAS_CORTO = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
MESES_CORTO = ["","ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]


class HidratacionApp(App):
    def build(self):
        self.title = "🐸 Hidratación de Ranita"
        d = load_data()
        self.botellas = d["botellas"]
        self.extra = d["extra"]
        self.last_reminder = Clock.get_boottime() if hasattr(Clock, "get_boottime") else 0
        self.last_reminder_time = datetime.datetime.now()
        self.popup_open = False
        self.last_date = datetime.date.today()

        root = FloatLayout()
        scroll = ScrollView(size_hint=(1, 1))
        col = BoxLayout(orientation="vertical", size_hint_y=None,
                        padding=[dp(16), dp(20), dp(16), dp(24)], spacing=dp(12))
        col.bind(minimum_height=col.setter("height"))

        # Título
        col.add_widget(Label(text="💧 Tu Hidratación 🌸",
                             font_size=dp(24), bold=True, color=COLORS["pink_dark"],
                             size_hint_y=None, height=dp(40)))
        self.lbl_date = Label(text="", font_size=dp(13), color=COLORS["text_light"],
                              size_hint_y=None, height=dp(22))
        col.add_widget(self.lbl_date)
        self.lbl_motivation = Label(text="", font_size=dp(14), color=COLORS["pink_dark"],
                                    size_hint_y=None, height=dp(50),
                                    halign="center", valign="middle")
        self.lbl_motivation.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        col.add_widget(self.lbl_motivation)

        # Botellas
        bottle_box = RoundedBox(bg=COLORS["bg2"], orientation="vertical",
                                size_hint_y=None, height=dp(170), padding=dp(10))
        bottle_box.add_widget(Label(text="Meta diaria: 2 litros", font_size=dp(12),
                                    color=COLORS["text_light"],
                                    size_hint_y=None, height=dp(24)))
        self.bottles = BottleRow(size_hint_y=1)
        bottle_box.add_widget(self.bottles)
        col.add_widget(bottle_box)

        # Progreso
        prog_box = RoundedBox(bg=COLORS["bg2"], orientation="vertical",
                              size_hint_y=None, height=dp(96), padding=dp(12), spacing=dp(6))
        prog_box.add_widget(Label(text="Progreso del día", font_size=dp(13), bold=True,
                                  color=COLORS["text"], size_hint_y=None, height=dp(20)))
        self.progress = ProgressTrack(size_hint_y=None, height=dp(20))
        prog_box.add_widget(self.progress)
        self.lbl_progress_text = Label(text="", font_size=dp(12),
                                       color=COLORS["text_light"],
                                       size_hint_y=None, height=dp(20))
        prog_box.add_widget(self.lbl_progress_text)
        col.add_widget(prog_box)

        # Botón principal
        self.btn_drink = RoundedButton(text="Tomé una botella (500 ml)",
                                       bg=COLORS["pink"], font_size=dp(16), bold=True,
                                       size_hint_y=None, height=dp(58))
        self.btn_drink.bind(on_release=lambda *_: self.on_drink())
        col.add_widget(self.btn_drink)

        # Bonus extra
        extra_box = RoundedBox(bg=COLORS["bg2"], orientation="vertical",
                               size_hint_y=None, height=dp(70), padding=dp(8))
        extra_box.add_widget(Label(text="✨ Bonus Extra", font_size=dp(13), bold=True,
                                   color=COLORS["lavender"], size_hint_y=None, height=dp(22)))
        self.lbl_extra = Label(text="", font_size=dp(12), color=COLORS["text_light"],
                               size_hint_y=None, height=dp(30))
        extra_box.add_widget(self.lbl_extra)
        col.add_widget(extra_box)

        # Próximo recordatorio
        rem_box = RoundedBox(bg=COLORS["bg2"], size_hint_y=None, height=dp(50))
        self.lbl_reminder = Label(text="", font_size=dp(12), color=COLORS["text_light"])
        rem_box.add_widget(self.lbl_reminder)
        col.add_widget(rem_box)

        # Botones secundarios
        self.btn_reset = RoundedButton(text="🔄 Reiniciar día manualmente",
                                       bg=COLORS["shadow"], font_size=dp(12),
                                       size_hint_y=None, height=dp(40))
        self.btn_reset.color = COLORS["text"]
        self.btn_reset.bind(on_release=lambda *_: self.manual_reset())
        col.add_widget(self.btn_reset)

        self.btn_history = RoundedButton(text="📅 Ver registro de las últimas 2 semanas",
                                         bg=COLORS["lavender"], font_size=dp(12),
                                         size_hint_y=None, height=dp(40))
        self.btn_history.color = COLORS["text"]
        self.btn_history.bind(on_release=lambda *_: self.show_history())
        col.add_widget(self.btn_history)

        scroll.add_widget(col)
        root.add_widget(scroll)

        self.refresh_ui()
        Clock.schedule_interval(self.tick, 1)
        return root

    # ── Ciclo de actualización ───────────────────────────────────────────────────
    def tick(self, dt):
        # Chequeo de medianoche
        if datetime.date.today() != self.last_date:
            self.last_date = datetime.date.today()
            self.botellas = 0
            self.extra = 0
            self.last_reminder_time = datetime.datetime.now()
            self.refresh_ui()

        # Cuenta regresiva de recordatorio
        elapsed = (datetime.datetime.now() - self.last_reminder_time).total_seconds()
        remaining = max(0, REMINDER_MINUTES * 60 - elapsed)
        mins, secs = int(remaining // 60), int(remaining % 60)
        self.lbl_reminder.text = f"🔔 Próximo recordatorio en {mins}:{secs:02d} min"

        if remaining <= 0 and not self.popup_open:
            self.last_reminder_time = datetime.datetime.now()
            self.show_reminder_popup()

    def refresh_ui(self):
        today_txt = datetime.date.today().strftime("%A %d de %B de %Y")
        for en, es in {**DIAS_ES, **MESES_ES}.items():
            today_txt = today_txt.replace(en, es)
        self.lbl_date.text = today_txt

        idx = min(self.botellas, len(MOTIVATIONS) - 1)
        if self.botellas >= BOTELLAS_META:
            idx = 4 if self.extra == 0 else 5
        self.lbl_motivation.text = MOTIVATIONS[idx]

        self.bottles.filled = self.botellas

        ml_total = self.botellas * BOTELLA_ML
        ratio = min(ml_total / META_ML, 1.0)
        self.progress.ratio = ratio
        self.lbl_progress_text.text = f"{ml_total} ml de {META_ML} ml  ({int(ratio*100)}%)"

        if self.extra > 0:
            self.lbl_extra.text = f"🌟 {self.extra * BOTELLA_ML} ml extra — ¡sorprendente!"
        else:
            self.lbl_extra.text = "Completá los 2L para desbloquear el bonus ✨"

        if self.botellas >= BOTELLAS_META:
            self.btn_drink.text = "🌟 ¡Botella extra! (+500 ml)"
            self.btn_drink.set_bg(COLORS["lavender"])
        else:
            remaining = BOTELLAS_META - self.botellas
            self.btn_drink.text = f"Tomé una botella (500 ml) — {remaining} restante{'s' if remaining != 1 else ''}"
            self.btn_drink.set_bg(COLORS["pink"])

        save_data(self.botellas, self.extra)

    # ── Acción principal ─────────────────────────────────────────────────────────
    def on_drink(self):
        was_at_meta = self.botellas >= BOTELLAS_META
        if self.botellas < BOTELLAS_META:
            self.botellas += 1
        else:
            self.extra += 1

        self.last_reminder_time = datetime.datetime.now()

        total = self.botellas + self.extra
        hitos = {4: "muchachos.mp3", 6: "boeee.mp3", 8: "paraaa.mp3"}
        play_sound(hitos.get(total, "levelup.mp3"))

        self.refresh_ui()

        if not was_at_meta and self.botellas >= BOTELLAS_META:
            Clock.schedule_once(lambda dt: self.show_love_popup(), 0.8)

    # ── Popup de recordatorio ────────────────────────────────────────────────────
    def show_reminder_popup(self):
        if self.popup_open:
            return
        self.popup_open = True

        ml = self.botellas * BOTELLA_ML
        remaining = max(0, META_ML - ml)
        msg = (f"Llevás {ml} ml — te faltan {remaining} ml para la meta."
               if remaining > 0 else
               f"Ya tomaste {ml} ml hoy. ¡Sos una campeona! 🌟")

        play_sound("preparate.mp3")
        notify_system("💧 ¡Hora de hidratarse!", msg)

        content = RoundedBox(bg=COLORS["pink"], orientation="vertical",
                             padding=dp(20), spacing=dp(10))
        content.add_widget(Label(text="💧 ¡Hora de hidratarse! 🌸",
                                 font_size=dp(16), bold=True, color=COLORS["white"],
                                 size_hint_y=None, height=dp(30)))
        lbl_msg = Label(text=msg, font_size=dp(13), color=COLORS["white"],
                       halign="center")
        lbl_msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        content.add_widget(lbl_msg)

        btn = RoundedButton(text="¡Ya tomo! 💪", bg=COLORS["white"],
                            size_hint_y=None, height=dp(46))
        btn.color = COLORS["pink_dark"]
        content.add_widget(btn)

        popup = Popup(title="", content=content, size_hint=(0.85, 0.4),
                      auto_dismiss=False, separator_height=0,
                      background_color=(0, 0, 0, 0))

        def on_close(*_):
            self.popup_open = False
            play_sound("yahoo.mp3")
            popup.dismiss()

        btn.bind(on_release=on_close)

        def retry(dt):
            if self.popup_open:
                play_sound("preparate.mp3")
                notify_system("💧 ¡Seguís sin tomar agua!", msg)
                Clock.schedule_once(retry, 5 * 60)

        Clock.schedule_once(retry, 5 * 60)
        popup.open()

    # ── Popup de amor (al llegar a 2L) ───────────────────────────────────────────
    def show_love_popup(self):
        content = RoundedBox(bg=COLORS["bg"], orientation="vertical",
                             padding=dp(18), spacing=dp(6))
        content.add_widget(Label(text="— ❤ — ❤ — ❤ —", font_size=dp(15),
                                 color=COLORS["pink"], size_hint_y=None, height=dp(26)))
        content.add_widget(Label(text="SOS LA MUJER MÁS\nINCREÍBLE QUE\nCONOCÍ EN MI VIDA",
                                 font_size=dp(17), bold=True, color=COLORS["pink_dark"],
                                 halign="center", size_hint_y=None, height=dp(80)))
        lbl2 = Label(text="Ni el mismísimo Alduin pudo detenerte.\n"
                          "Alcanzaste la meta y mi corazón es tuyo.\n"
                          "¡Felicidades, mi Dovahkiin favorita!",
                    font_size=dp(11), color=COLORS["text_light"],
                    halign="center", size_hint_y=None, height=dp(60))
        lbl2.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        content.add_widget(lbl2)

        btn = RoundedButton(text="Todo se cura con amor  ❤", bg=COLORS["pink"],
                            font_size=dp(14), size_hint_y=None, height=dp(46))
        content.add_widget(btn)

        popup = Popup(title="", content=content, size_hint=(0.85, 0.5),
                      auto_dismiss=False, separator_height=0,
                      background_color=(0, 0, 0, 0))

        def on_close(*_):
            play_sound("amor1.mp3")
            popup.dismiss()
        btn.bind(on_release=on_close)
        popup.open()

    # ── Historial de 2 semanas ───────────────────────────────────────────────────
    def show_history(self):
        history = load_history()
        today = datetime.date.today()

        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        content.add_widget(Label(text="📅 Últimas 2 semanas", font_size=dp(16), bold=True,
                                 color=COLORS["pink_dark"], size_hint_y=None, height=dp(30)))

        scroll = ScrollView(size_hint=(1, 1))
        rows = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        rows.bind(minimum_height=rows.setter("height"))

        for i in range(13, -1, -1):
            day = today - datetime.timedelta(days=i)
            key = day.isoformat()
            data = history.get(key)
            fecha = f"{DIAS_CORTO[day.weekday()]} {day.day} {MESES_CORTO[day.month]}"
            if key == today.isoformat():
                fecha += " (hoy)"

            row = RoundedBox(bg=COLORS["white"], size_hint_y=None, height=dp(42),
                             padding=[dp(10), 0])
            if data:
                ml = data.get("ml", data.get("botellas", 0) * 500)
                emoji = "✅" if ml >= META_ML else "💧"
                row.add_widget(Label(text=f"{emoji} {fecha}", font_size=dp(12),
                                     color=COLORS["text"], halign="left"))
                row.add_widget(Label(text=f"{ml} ml", font_size=dp(12),
                                     color=COLORS["pink_dark"]))
            else:
                row.add_widget(Label(text=f"— {fecha}", font_size=dp(12),
                                     color=COLORS["text_light"]))
                row.add_widget(Label(text="sin registro", font_size=dp(11),
                                     color=COLORS["shadow"]))
            rows.add_widget(row)

        scroll.add_widget(rows)
        content.add_widget(scroll)

        btn_close = RoundedButton(text="Cerrar", bg=COLORS["pink"],
                                  size_hint_y=None, height=dp(44))
        content.add_widget(btn_close)

        popup = Popup(title="", content=content, size_hint=(0.92, 0.85),
                      separator_height=0, background_color=(0, 0, 0, 0))
        btn_close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    # ── Reset manual ─────────────────────────────────────────────────────────────
    def manual_reset(self):
        self.botellas = 0
        self.extra = 0
        self.last_reminder_time = datetime.datetime.now()
        self.refresh_ui()


if __name__ == "__main__":
    HidratacionApp().run()
