from guiml.components import Component, Div
from guiml.core import run

from dataclasses import dataclass, field


from guiml.injectables import Injectable, injectable


from guiml.components import Container

from dotrack import icon  # noqa: F401
from dotrack import timer  # noqa: F401
from dotrack.model import TodoService, Todo

from dotrack.shared import component, res, BASE_DIR


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
        self.view = 'todo'


@component("menu")
class Menu(Div):
    @dataclass
    class Dependencies(Div.Dependencies):
        router: RouterService

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
    class Dependencies(Div.Dependencies):
        router: RouterService

    @dataclass
    class Properties(Container.Properties):
        pass

    @property
    def view(self):
        return self.dependencies.router.view


@component(name="todo_view")
class TodoView(Div):
    pass


@component(name="event_view")
class EventView(Div):
    pass


@component("todo")
class TodoComponent(Container):

    @dataclass
    class Dependencies:
        todo_service: TodoService

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
class TodoItemComponent(Container):
    @dataclass
    class Dependencies(Container.Dependencies):
        todo_service: TodoService

    @dataclass
    class Properties(Container.Properties):
        item: Todo = None

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


def main():
    pass


if __name__ == '__main__':
    main()
