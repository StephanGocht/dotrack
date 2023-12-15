import yaml
import dataclasses
import typing


from dataclasses import dataclass, field
from dotrack.shared import DATA_DIR
from guiml.injectables import Injectable, injectable


@dataclass
class PomodoroTimer:
    duration: int = 20 * 60


@dataclass
class ConfigRoot:
    pomodoro: PomodoroTimer = field(default_factory=PomodoroTimer)
    task_groups: list[str] = field(default_factory=list)


def structure(data, data_type):
    origin = typing.get_origin(data_type)
    type_args = typing.get_args(data_type)
    if data is None:
        return None
    elif origin is not None and isinstance(data, origin):
        if isinstance(data, list):
            data = [structure(x, type_args[0]) for x in data]
            return data
    elif isinstance(data, data_type):
        return data
    elif dataclasses.is_dataclass(data_type):
        args = dict()
        for field in dataclasses.fields(data_type):  # noqa: F402
            try:
                value = data[field.name]
            except KeyError:
                pass
            else:
                args[field.name] = structure(value, field.type)

        return data_type(**args)
    else:
        return data


def destructure(data):
    if dataclasses.is_dataclass(data):
        result = dataclasses.asdict(data)
        return destructure(result)
    elif isinstance(data, dict):
        return {key: destructure(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [destructure(value) for value in data]
    else:
        return data


@injectable("application")
class Config(Injectable):
    CONFIG_FILE = DATA_DIR / "config.yml"

    @dataclass
    class Dependencies(Injectable.Dependencies):
        pass

    def on_init(self):
        self.config = None
        self.load_config()
        self.write_config()

    def load_config(self):
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, 'r') as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)

            self.config = structure(data, ConfigRoot)
        else:
            self.config = ConfigRoot()

    def write_config(self):
        data = destructure(self.config)

        with open(self.CONFIG_FILE, 'w') as f:
            yaml.dump(data, f)

    def get(self):
        return self.config
