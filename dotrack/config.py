import yaml
import dataclasses
import typing


from dataclasses import dataclass, field
from dotrack.shared import DATA_DIR
from guiml.injectables import Injectable, injectable


def structure(data, data_type):
    origin = typing.get_origin(data_type)
    type_args = typing.get_args(data_type)
    if data is None:
        return None
    elif origin is not None:

        if origin is typing.Union:
            if len(type_args) == 2 and type(None) in type_args:
                if data is None:
                    return None
                else:
                    field_type = next(
                        iter((t for t in type_args
                              if t is not type(None))))
                    return structure(
                        data, field_type)

        elif isinstance(data, origin):
            if isinstance(data, list):
                data = [structure(x, type_args[0]) for x in data]
                return data

        raise NotImplementedError(f'Trying to structure {data_type.__name__}')

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
    CONFIG_CLASSES = dict()

    @dataclass
    class Dependencies(Injectable.Dependencies):
        pass

    @classmethod
    def get_key(cls, config_class):
        return config_class.__name__

    @classmethod
    def register(cls, config_class):
        key = cls.get_key(config_class)
        if key in cls.CONFIG_CLASSES:
            raise ValueError('Doublicate config class name.')

        cls.CONFIG_CLASSES[key] = config_class
        return config_class

    def on_init(self):
        self.config = None
        self.load_config()
        self.write_config()

    def load_config(self):
        data = None
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, 'r') as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
        if data is None:
            data = {}

        self.config = dict()
        for key, config_class in self.CONFIG_CLASSES.items():
            if key in data:
                self.config[key] = structure(data[key], config_class)
            else:
                self.config[key] = config_class()

    def write_config(self):
        data = {key: destructure(value) for key, value in self.config.items()}

        with open(self.CONFIG_FILE, 'w') as f:
            yaml.dump(data, f)

    def __getitem__(self, config_class):
        return self.config[self.get_key(config_class)]


@injectable("application")
class SaveState(Config):
    CONFIG_FILE = DATA_DIR / "state.yml"
    CONFIG_CLASSES = dict()

    def on_init(self):
        self.config = None
        self.load_config()

    def on_destroy(self):
        self.write_config()
