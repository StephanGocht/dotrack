from dataclasses import dataclass
from enum import Enum

import datetime

import peewee
import time

from guiml.injectables import Injectable, injectable, Observable, Subscriber

from dotrack.shared import BASE_DIR
from dotrack.config import Config


class DatabaseManger:
    SAVE_FILE = BASE_DIR / '../data/dotrack.db'

    def __init__(self):
        self.db = peewee.SqliteDatabase(None)

    def connect(self):
        exists = self.SAVE_FILE.exists()
        self.db.init(str(self.SAVE_FILE))
        self.db.connect()
        self.evolve(exists)

        EventType.init_events()
        ExpType.init_events()

    def models(self):
        return [Todo, EventType, Event, ExpType, ExpEvent]

    def evolve(self, exists):
        modify = False
        models = dict()
        for model in self.models():
            models[model._meta.table_name] = {
                'model': model,
                'schema': None
            }

        tables = SqliteSchema.select().where(SqliteSchema.type_ == 'table')
        for table in tables:
            models[table.tbl_name]['schema'] = table.sql

        to_create = list()
        for key, value in models.items():
            if value['schema'] is None:
                to_create.append(value['model'])

        if to_create:
            modify = True
            names = [model._meta.table_name for model in to_create]
            print(f'create tables: {", ".join(names)}')

        if modify:
            if not exists or input("Apply modification y/n? ") == "y":
                if to_create:
                    self.db.create_tables(to_create)
            else:
                print('Exiting, database not up to date.')
                exit(0)

    def __call__(self):
        return self.db


db = DatabaseManger()


class SqliteSchema(peewee.Model):
    type_ = peewee.TextField(column_name='type')
    name = peewee.TextField()
    tbl_name = peewee.TextField()
    rootpage = peewee.IntegerField()
    sql = peewee.TextField()

    class Meta:
        database = db()
        table_name = 'sqlite_schema'
        primary_key = False


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

    def work_time(self):
        today = datetime.date.today()
        end_of_today = today + datetime.timedelta(days=1)

        events = (
            Event.select()
            .where((today <= Event.time) & (Event.time < end_of_today))
            .where((Event.event_type == EventType.START)
                   | (Event.event_type == EventType.STOP))
            .order_by(Event.time)
        )

        def fold(events):
            events = iter(events)
            try:
                start = None
                while True:
                    nxt = next(events)
                    if nxt.event_type == EventType.START:
                        if start is not None:
                            yield start, None
                        start = nxt
                    elif nxt.event_type == EventType.STOP:
                        if start is not None:
                            assert start.todo_id == nxt.todo_id
                            assert start.time < nxt.time
                            yield start, nxt
                            start = None
                        else:
                            continue

            except StopIteration:
                if start is not None:
                    yield start, None

        last_time = datetime.datetime.now()
        work_time = datetime.timedelta()

        for start, stop in reversed(list(fold(events))):
            if stop is None:
                duration = last_time - start.time
            else:
                duration = stop.time - start.time
            work_time += duration
            last_time = start.time

        return work_time

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
            item.done = datetime.datetime.now()
        else:
            item.done = None
        item.save()

@injectable("application")
class ExpService(Injectable, Subscriber):
    @dataclass
    class Dependencies(Injectable.Dependencies):
        todo: TodoService

    def on_init(self):
        self.subscribe('on_todo_toggle', self.todo)

    def on_destroy(self):
        self.cancel_subscriptions()

    def on_todo_toggle(self, item):
        pass

class SimpleTimer:
    def __init__(self, duration):
        self.duration = duration
        self.last_start = None
        self.elapsed = 0
        self.reset()

    def is_running(self):
        return self.last_start is not None

    @property
    def remaining(self):
        result = self.duration - self.elapsed
        if self.is_running():
            result -= time.monotonic() - self.last_start
        return result

    @property
    def progress(self):
        result = max(0, self.remaining) / self.duration
        return result

    def reset(self):
        self.last_start = None
        self.elapsed = 0

    def start(self):
        self.last_start = time.monotonic()

    def stop(self):
        self.elapsed += time.monotonic() - self.last_start
        self.last_start = None


@injectable("application")
class Timer(Injectable, Subscriber):
    @dataclass
    class Dependencies(Injectable.Dependencies):
        todo_service: TodoService
        config: Config

    def on_init(self):
        super().on_init()
        self.subscribe('on_selected_changed', self.todo_service)

        config = self.config.get().pomodoro

        self.timer = SimpleTimer(config.duration)
        self.selected = None

    def on_destroy(self):
        super().on_destroy()
        self.cancel_subscriptions()

    def on_selected_changed(self, todo):
        self.stop()
        self.selected = todo

    def is_running(self):
        return self.timer.is_running()

    @property
    def progress(self):
        return self.timer.progress

    @property
    def remaining(self):
        return self.timer.remaining

    def is_active(self):
        return self.selected is not None

    def start(self):
        if not self.is_active():
            return

        self.timer.start()

        if self.selected is not None:
            Event.create(
                todo=self.selected,
                event_type=EventType.START,
                time=datetime.datetime.now())

    def stop(self):
        if not self.is_active() or not self.is_running():
            return

        self.timer.stop()

        selected = self.selected
        if selected is not None:
            Event.create(
                todo=selected,
                event_type=EventType.STOP,
                time=datetime.datetime.now())

    def reset(self):
        self.stop()
        self.timer.reset()


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
            if event_type.name in events:
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
