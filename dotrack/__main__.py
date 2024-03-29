from guiml.components import Component, Div, UIComponent
from guiml.core import run

from dataclasses import dataclass, field


from guiml.injectables import Injectable, injectable


from guiml.components import Container

from dotrack import icon  # noqa: F401
from dotrack import timer  # noqa: F401
from dotrack.model import TodoService
import dotrack.model as model
from typing import Callable, Optional

from dotrack.shared import component, res, BASE_DIR

import cairocffi as cairo
import peewee
import datetime


@component("application")
class Application(Component):
    pass


def main():
    run(
        global_style=res.style_file("styles.yml", "global"),
        interval=1 / 30
    )


@injectable("application")
class RouterService(Injectable):
    def on_init(self):
        self.view = 'events'


@component("menu")
class Menu(Div):
    @dataclass
    class Dependencies(Div.Dependencies):
        router: RouterService = None

    @dataclass
    class Properties(Div.Properties):
        pass

    def navigate(self, target):
        self.dependencies.router.view = target

    def on_home(self):
        self.navigate('todo')

    def on_lists(self):
        self.navigate('events')


@component(name="router_outlet")
class RouterOutlet(Container):
    @dataclass
    class Dependencies(Container.Dependencies):
        router: RouterService = None

    @dataclass
    class Properties(Container.Properties):
        pass

    @property
    def view(self):
        return self.dependencies.router.view


@component(name="todo_view")
class TodoView(Div):
    @dataclass
    class Dependencies(Div.Dependencies):
        todo_service: TodoService = None

    @dataclass
    class Properties(Div.Properties):
        pass

    def work_time(self):
        timedelta = self.dependencies.todo_service.work_time()
        hours, remainder = divmod(timedelta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}"


@dataclass
class Color:
    """ """

    red: float = 0.
    green: float = 0.
    blue: float = 0.
    alpha: float = 0.

    @classmethod
    def white(cls):
        return Color(1, 1, 1, 1)


@component(name="exp_display")
class ExpDisplay(Div):
    @dataclass
    class Dependencies(Div.Dependencies):
        exp_service: model.ExpService = None

    @property
    def progress(self):
        return self.dependencies.exp_service.progress

    @property
    def text(self):
        exp = self.dependencies.exp_service

        return (f'{exp.exp}/{exp.next_level} '
                f'({int(exp.progress*100)}%) '
                f'Level: {exp.level}')


@component(name="exp_bar", template=None)
class ExpBar(UIComponent):
    @dataclass
    class Dependencies(UIComponent.Dependencies):
        pass

    @dataclass
    class Properties(UIComponent.Properties):
        progress: float = 0.3
        background: Color = field(default_factory=Color)
        border: Color = field(default_factory=Color)
        fill: Color = field(default_factory=Color)
        fill_darken: float = 0.
        width: int = 100
        height: int = 20

    def push_rectangle(self, ctx, progress):
        position = self.properties.position
        ctx.rectangle(position.left + 0.5, position.top + 0.5,
                      (position.width - 1) * progress, position.height - 1)

    @property
    def width(self):
        return self.properties.width

    @property
    def height(self):
        return self.properties.height

    def on_draw(self, ctx):
        with ctx:
            position = self.properties.position

            self.push_rectangle(ctx, 1.0)
            color = self.properties.background
            pat = cairo.SolidPattern(color.red, color.green, color.blue,
                                     color.alpha)
            ctx.set_source(pat)
            ctx.fill()

            self.push_rectangle(ctx, self.properties.progress)
            color = self.properties.fill

            gradient = cairo.LinearGradient(position.left, position.top,
                                            position.left, position.bottom)

            gradient.add_color_stop_rgb(0., color.red, color.green, color.blue)
            darken = self.properties.fill_darken
            gradient.add_color_stop_rgb(1., color.red * darken,
                                        color.green * darken,
                                        color.blue * darken)

            ctx.set_source(gradient)
            ctx.fill()

            ctx.set_line_width(1)
            color = self.properties.border
            pat = cairo.SolidPattern(color.red, color.green, color.blue,
                                     color.alpha)
            ctx.set_source(pat)

            self.push_rectangle(ctx, 1.0)
            ctx.stroke()

            num_ticks = 20
            tick_size = position.width // num_ticks
            pos = position.left + 0.5
            top = position.top
            bottom = position.bottom

            for i in range(1, num_ticks):
                pos += tick_size
                ctx.move_to(pos, top)
                ctx.line_to(pos, bottom)
                ctx.stroke()

        super().on_draw(ctx)


@component(name="event_list")
class EventList(Div):
    @dataclass
    class Dependencies(Div.Dependencies):
        pass

    @dataclass
    class Properties(Div.Properties):
        pass

    @property
    def events(self):
        data = (model.Event

                .select(model.Event, model.EventType, model.Todo)
                .where(model.Event.todo_id.is_null(False))
                .join(model.Todo, join_type=peewee.JOIN.LEFT_OUTER)
                .switch(model.Event)
                .join(model.EventType)
                .order_by(model.Event.time.desc())
                .limit(15)
                )
        return data


@component("time_edit")
class TimeEdit(Div):
    @dataclass
    class Dependencies(Div.Dependencies):
        event_edit: model.EventEditService

    @dataclass
    class Properties(Div.Properties):
        event: Optional[model.Event] = None
        on_update: Optional[Callable[datetime.datetime, None]] = None

    @property
    def edit(self):
        return self.time is not None

    @property
    def time(self):
        return self.dependencies.event_edit.get_edit(self.properties.event)

    @property
    def valid(self):
        try:
            self.as_date()
        except ValueError:
            return False
        else:
            return True

    def as_date(self):
        return datetime.datetime.fromisoformat(self.time)

    @time.setter
    def time(self, value):
        self.dependencies.event_edit.set_edit(self.properties.event, value)

    def format_time(self):
        return str(self.properties.event.time)[:19]

    def start_edit(self):
        self.time = self.format_time()

    def save(self, text):
        if self.valid:
            event = self.properties.event
            self.dependencies.event_edit.write_edit(event, self.time)


@component(name="event")
class EventComponent(Div):
    @dataclass
    class Properties(Div.Properties):
        event: model.Event = None

    @dataclass
    class Dependencies(Div.Dependencies):
        pass

    @property
    def event(self):
        return self.properties.event

    def format_time(self):
        return str(self.event.time)[:19]


@component("todo")
class TodoComponent(Container):

    @dataclass
    class Dependencies(Container.Dependencies):
        todo_service: TodoService = None

    @dataclass
    class Properties(Container.Properties):
        pass

    def on_init(self):
        self.text = ''

    def on_destroy(self):
        pass

    @property
    def todos(self):
        return self.dependencies.todo_service.todos

    @property
    def task_groups(self):
        return self.dependencies.todo_service.task_groups

    def select_group(self, group):
        return self.dependencies.todo_service.select_group(group)

    @property
    def num_open_todos(self):
        return sum((1 for todo in self.todos if not todo.done))

    def add_clicked(self):
        todo_service = self.dependencies.todo_service
        todo_service.add(self.text)
        self.text = ''

    def input_submit(self, text):
        self.add_clicked()


@component(name="todolist")
class TodoList(Container):

    @dataclass
    class Properties(Container.Properties):
        todos: list = field(default_factory=list)

    @property
    def todos(self):
        return self.properties.todos


@component("todo_item")
class Todo(Container):
    @dataclass
    class Dependencies(Container.Dependencies):
        todo_service: TodoService

    @dataclass
    class Properties(Container.Properties):
        item: model.Todo = None

    def on_init(self):
        self.destroyed = False
        super().on_init()

    def on_draw(self, canvas):
        super().on_draw(canvas)

    @property
    def item(self):
        return self.properties.item

    def checkbox_clicked(self):
        self.dependencies.todo_service.toggle_done(self.item)

    def checkbox_svg(self):
        if self.item.done:
            return res.paths['checkbox_ticked']
        else:
            return res.paths['checkbox_blank']

    def delete_svg(self):
        return res.paths['delete']

    def get_checkbox_class(self):
        if self.item.done:
            return 'checkbox_ticked'
        else:
            return 'checkbox'

    def delete_clicked(self):
        self.dependencies.todo_service.remove(self.item)

    def on_destroy(self):
        self.destroyed = True
        super().on_destroy()

    def on_select(self):
        self.dependencies.todo_service.select(self.item)

    def is_selected(self):
        return self.dependencies.todo_service.is_selected(self.item)


if __name__ == '__main__':
    main()
