from guiml.components import UIComponent

from dataclasses import dataclass

import cairocffi as cairo

from guiml.components import Container
import math
import time

from dotrack.shared import component
from dotrack.model import Timer


@component("timer")
class TimerComponent(Container):
    @dataclass
    class Dependencies(Container.Dependencies):
        timer: Timer

    @dataclass
    class Properties(Container.Properties):
        duration: int = 10
        """Timer duration in seconds"""

    @property
    def progress(self):
        return self.dependencies.timer.progress

    @property
    def remaining(self):
        return self.dependencies.timer.remaining

    @property
    def remaining_str(self):
        remaining = int(round(self.remaining))
        if remaining < 0:
            sign = True
            remaining = -remaining
        else:
            sign = False

        return f'{"-" if sign else " "}{remaining//60:02}:{ remaining % 60:02}'

    def on_init(self):
        super().on_init()

    def on_destroy(self):
        super().on_destroy()

    def on_start(self):
        timer = self.dependencies.timer
        if not timer.is_running():
            timer.start()
        else:
            timer.stop()


@component("circle_progress", template=None)
class CircleProgress(UIComponent):
    @dataclass
    class Dependencies(UIComponent.Dependencies):
        pass

    @dataclass
    class Properties(UIComponent.Properties):
        width: int = 150
        height: int = 150
        progress: float = 0

    @property
    def width(self):
        return self.properties.width

    @property
    def height(self):
        return self.properties.height

    def on_draw(self, ctx):
        center_x = self.properties.position.left + self.width // 2
        center_y = self.properties.position.top + self.height // 2
        radius = min(self.width, self.height) // 2
        progress = self.properties.progress

        with ctx:
            ctx.move_to(center_x, center_y)
            ctx.arc(center_x, center_y, radius, -math.pi/2, -math.pi/2 + 2 * math.pi / 100 * progress)
            pat = cairo.SolidPattern(0, 0.8, 0, 1)
            ctx.set_source(pat)
            ctx.fill()

        super().on_draw(ctx)