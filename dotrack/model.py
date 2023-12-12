from dataclasses import dataclass
from enum import Enum

import datetime

import peewee
import time

from guiml.injectables import Injectable, injectable

from dotrack.shared import BASE_DIR


class DatabaseManger:
    SAVE_FILE = BASE_DIR / 'dotrack.db'

    def __init__(self):
        self.db = peewee.SqliteDatabase(None)

    def connect(self):
        print(self.SAVE_FILE)
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

        self.selected = None

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
        if self.selected is not None:
            self.selected.selected = False

        if self.selected == item:
            self.selected = None
        else:
            self.selected = item
            self.selected.selected = True

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
class Timer(Injectable):
    @dataclass
    class Dependencies(Injectable.Dependencies):
        pass

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

    def is_running(self):
        return self.last_start is not None

    def on_init(self):
        super().on_init()

        self.duration = 10
        self.last_start = None

    def on_destroy(self):
        super().on_destroy()

    def start(self):
        self.last_start = time.monotonic()

    def stop(self):
        self.last_start = None


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
