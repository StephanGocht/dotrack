from dataclasses import dataclass
from enum import Enum

import datetime

import peewee
import time

from guiml.injectables import Injectable, injectable, Observable, Subscriber

from dotrack.shared import BASE_DIR


class DatabaseManger:
    SAVE_FILE = BASE_DIR / 'dotrack.db'

    def __init__(self):
        self.db = peewee.SqliteDatabase(None)

    def connect(self):
        exists = self.SAVE_FILE.exists()
        self.db.init(str(self.SAVE_FILE))
        self.db.connect()
        if not exists:
            self.create_database()

        EventType.init_events()

    def create_database(self):
        self.db.create_tables([Todo, EventType, Event])

    def __call__(self):
        return self.db


db = DatabaseManger()


@injectable("application")
class TodoService(Injectable):
    @dataclass
    class Dependencies(Injectable.Dependencies):
        pass

    def on_init(self):
        super().on_init()

        global db
        db.connect()

        self.on_selected_changed = Observable()

        self._selected = None

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value):
        self.on_selected_changed(value)
        self._selected = value

    def on_destroy(self):
        super().on_destroy()

    @property
    def todos(self):
        display_time = (datetime.datetime.now()
                        - datetime.timedelta(minutes=1))
        return (Todo
                .select()
                .where(
                    (Todo.done.is_null())
                    | (Todo.done > display_time))
                )

    def select(self, item):
        if self.is_selected(item):
            self.selected = None
        else:
            self.selected = item

    def is_selected(self, item):
        if self.selected is None:
            return False
        else:
            return self.selected.todo_id == item.todo_id

    def add(self, text):
        Todo.create(text=text)

    def remove(self, item):
        item.delete_instance()

    def toggle_done(self, item):
        if item.done is None:
            item.done = datetime.now()
        else:
            item.done = None
        item.save()


@injectable("application")
class Timer(Injectable, Subscriber):
    @dataclass
    class Dependencies(Injectable.Dependencies):
        todo_service: TodoService

    def on_init(self):
        super().on_init()
        self.subscribe('on_selected_changed', self.todo_service)

        self.duration = 10
        self.last_start = None
        self.selected = None

    def on_destroy(self):
        super().on_destroy()
        self.cancel_subscriptions()

    @property
    def progress(self):
        result = max(0, self.remaining) * 100 / self.duration
        return result

    @property
    def remaining(self):
        duration = self.duration
        if self.last_start is None:
            return duration
        else:
            return duration - (time.monotonic() - self.last_start)

    def on_selected_changed(self, todo):
        self.stop()
        self.selected = todo

    def is_running(self):
        return self.last_start is not None

    def is_active(self):
        return self.selected is not None

    def start(self):
        if not self.is_active():
            return

        print('start')
        self.last_start = time.monotonic()

        selected = self.selected

        if selected is not None:
            Event.create(
                todo=selected,
                event_type=EventType.START,
                time=datetime.datetime.now())

    def stop(self):
        if not self.is_active():
            return

        print('stop')
        self.last_start = None

        selected = self.selected
        if selected is not None:
            Event.create(
                todo=selected,
                event_type=EventType.STOP,
                time=datetime.datetime.now())


class Todo(peewee.Model):
    todo_id = peewee.AutoField(primary_key=True)
    text = peewee.TextField()
    done = peewee.DateTimeField(null=True)

    class Meta:
        database = db()

    def __init__(self, **kwargs):
        self.selected = False
        super().__init__(**kwargs)


class EventType(peewee.Model):
    event_type_id = peewee.AutoField(primary_key=True)
    name = peewee.TextField()

    class Meta:
        database = db()

    class Values(Enum):
        START = 'start'
        STOP = 'stop'

    @classmethod
    def init_events(cls):
        events = set((x.value for x in iter(cls.Values)))

        for event_type in cls.select():
            if event_type in events:
                setattr(cls, event_type.name.upper(), event_type)
                events.discard(event_type.name)

        for event_name in events:
            event_type = cls.create(name=event_name)
            setattr(cls, event_type.name.upper(), event_type)


class Event(peewee.Model):
    event_id = peewee.AutoField(primary_key=True)
    todo = peewee.ForeignKeyField(Todo, backref='events')
    event_type = peewee.ForeignKeyField(EventType)
    time = peewee.DateTimeField()

    class Meta:
        database = db()
