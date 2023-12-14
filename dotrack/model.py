from dataclasses import dataclass
from enum import Enum

import datetime

import peewee
import time
import re

from guiml.injectables import Injectable, injectable, Observable, Subscriber

from dotrack.shared import BASE_DIR
from dotrack.config import Config


class EvolveField:
    def __init__(self, schema=None, target_schema=None):
        self.schema = schema
        self.target_schema = target_schema


class EvolveTable:
    def __init__(self, model: peewee.Model):
        self.model = model
        self.name = model._meta.table_name
        self.schema = None
        self.target_schema = None
        self.determine_target_schema()

    def determine_target_schema(self):
        query = self.model._schema._create_table(safe=False)
        ctx = self.model._meta.database.get_sql_context()
        sql, params = ctx.sql(query).query()
        self.target_schema = sql

    def needs_change(self):
        return self.schema != self.target_schema

    def iter_fields(self, sql):
        start = f'CREATE TABLE "{self.name}" ('
        end = ')'
        sql = sql.strip()
        assert sql.startswith(start) and sql.endswith(end)

        sql = sql[len(start):-len(end)]
        for text in sql.split(','):
            text = text.strip()

            # after splitting, we will either have a column def or a table
            # constraint, constraints start with a keyword, so everything
            # starting with " will be a column def, see also
            # https://www.sqlite.org/lang_createtable.html
            match = re.match(r'^"([^"]+)"', text)
            if match:
                yield match.group(1), text

    def check_fields(self):
        actions = []

        fields = dict()
        for field, schema in self.iter_fields(self.schema):
            fields[field] = EvolveField(schema=schema)

        for field, schema in self.iter_fields(self.target_schema):
            fields.setdefault(field, EvolveField()).target_schema = schema

        for name, field in fields.items():
            if field.schema is None:
                sql = f'ALTER TABLE "{self.name}" ADD COLUMN {field.target_schema};'
                print(sql)
                db = self.model._meta.database

                def add_column(db=db, sql=sql):
                    db.execute_sql(sql)

                actions.append(add_column)

            # # Dropping columns may not be supported by your sqlite version
            # if field.target_schema is None:
            #     sql = f'ALTER TABLE "{self.name}" DROP COLUMN "{name}";'
            #     print(sql)
            #     db = self.model._meta.database

            #     def add_column(db=db, sql=sql):
            #         db.execute_sql(sql)

            #     actions.append(add_column)

        return actions


class Evolve:
    def __init__(self, db, models, require_confirm=True):
        self.db = db
        self.models = models
        self.require_confirm = require_confirm
        self.load_tables()

        self.evolution_steps = list()

    def load_tables(self):
        self.tables = dict()
        for model in self.models:
            self.tables[model._meta.table_name] = EvolveTable(model)

        tables = SqliteSchema.select().where(SqliteSchema.type_ == 'table')
        for table in tables:
            self.tables[table.tbl_name].schema = table.sql

    def check_create_tables(self):
        tables_to_create = list()
        for key, value in self.tables.items():
            if value.schema is None:
                self.tables_to_create.append(value.model)

        if tables_to_create:
            def create_tables():
                self.db.create_tables(tables_to_create)

            self.evolution_steps.append(create_tables)
            names = [model._meta.table_name for model in self.tables_to_create]
            print(f'create tables: {", ".join(names)}')

    def check_fields(self):
        for name, table in self.tables.items():
            if table.needs_change():
                self.evolution_steps.extend(table.check_fields())

    def user_confirm(self):
        if input("Apply modification y/n? ") == "y":
            return True
        else:
            return False

    def evolve(self):
        self.check_create_tables()
        self.check_fields()

        if self.evolution_steps:
            if not self.require_confirm or self.user_confirm():
                for step in self.evolution_steps:
                    step()
            else:
                print('Exiting, database not up to date.')
                exit(0)


class DatabaseManger:
    SAVE_FILE = BASE_DIR / '../data/dotrack.db'

    def __init__(self):
        self.db = peewee.SqliteDatabase(None)

    def connect(self):
        exists = self.SAVE_FILE.exists()
        self.db.init(str(self.SAVE_FILE))
        self.db.connect()
        evolve = Evolve(self.db, self.models(), require_confirm=exists)
        evolve.evolve()

        EventType.init_events()
        ExpType.init_events()

    def models(self):
        return [Todo, EventType, Event, ExpType, ExpEvent]

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
        self.on_todo_toggle = Observable()

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
                .where(~Todo.deleted)
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
        item.deleted = True
        item.save()

    def toggle_done(self, item):
        if item.done is None:
            item.done = datetime.datetime.now()
        else:
            item.done = None
        item.save()

        self.on_todo_toggle(item)


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

        self.on_reset = Observable()
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
        self.on_reset(self.remaining)
        self.timer.reset()


exp_table = {
    'raw_exp': {
        'toggle': 100,
        'reset': 100
    },
    'exp_per_level': 1000
}


@injectable("application")
class ExpService(Injectable, Subscriber):
    @dataclass
    class Dependencies(Injectable.Dependencies):
        todo: TodoService
        timer: Timer

    def on_init(self):
        self.subscribe('on_todo_toggle', self.todo)
        self.subscribe('on_reset', self.timer, self.on_timer_reset)

    def on_destroy(self):
        self.cancel_subscriptions()

    @property
    def next_level(self):
        return exp_table['exp_per_level']

    @property
    def progress(self):
        return self.exp / self.next_level

    def raw_exp(self):
        value = (
            ExpEvent
            .select(peewee.fn.Sum(ExpEvent.exp))
            .scalar()
        )
        if value is None:
            return 0
        else:
            return value

    @property
    def exp(self):
        return self.raw_exp() % exp_table['exp_per_level']

    @property
    def level(self):
        return self.raw_exp() // exp_table['exp_per_level']

    def on_timer_reset(self, remaining):
        if remaining < 0:
            ExpEvent.create(
                exp=exp_table['raw_exp']['reset'],
                event_type=ExpType.RESET,
                time=datetime.datetime.now(),
            )

    def on_todo_toggle(self, item):
        if item.done:
            ExpEvent.create(
                exp=exp_table['raw_exp']['toggle'],
                event_type=ExpType.DONE,
                time=datetime.datetime.now(),
                todo=item
            )
        else:
            (ExpEvent
                .delete()
                .where(ExpEvent.todo == item)
                .where(ExpEvent.event_type == ExpType.DONE)
                .execute())


class Todo(peewee.Model):
    todo_id = peewee.AutoField(primary_key=True)
    text = peewee.TextField()
    done = peewee.DateTimeField(null=True)
    # todo db reset: make non nullable
    deleted = peewee.BooleanField(default=False, null=True)

    class Meta:
        database = db()

    def __init__(self, **kwargs):
        self.selected = False
        super().__init__(**kwargs)


class ExpType(peewee.Model):
    exp_type_id = peewee.AutoField(primary_key=True)
    name = peewee.TextField()

    class Meta:
        database = db()

    class Values(Enum):
        DONE = 'done'
        """Todo done"""

        RESET = 'reset'
        """pomodoro timer reset"""

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


class ExpEvent(peewee.Model):
    exp_event_id = peewee.AutoField(primary_key=True)
    exp = peewee.IntegerField()
    event_type = peewee.ForeignKeyField(ExpType)
    time = peewee.DateTimeField()
    todo = peewee.ForeignKeyField(Todo, null=True, backref='exp_events')

    class Meta:
        database = db()


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
