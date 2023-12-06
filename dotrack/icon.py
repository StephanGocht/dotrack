import re

from dataclasses import dataclass
from pathlib import Path

from guiml.resources import ResourceManager
from guiml.components import Container
from guiml.components import component as guiml_component

BASE_DIR = Path(__file__).parent.resolve()

res = ResourceManager(
    basedir=BASE_DIR
)


def component(name):
    return guiml_component(
        name=name,
        template=res.template_file("templates.xml"),
        style=res.style_file("styles.yml"),
    )


_icon_codepoints = None


def load_icon_codepoints_css():
    css_path = "/usr/share/fonts-material-design-icons-iconfont/css/material-design-icons.css"  # noqa: E501

    re_name = re.compile(r".material-icons.([\w-]+):before {")
    re_codepoint = re.compile(r'content: "([^"]+)";')

    result = dict()

    with open(css_path) as f:
        lines = iter(f)
        while True:
            try:
                line = next(lines)
                match = re_name.search(line)
                if match:
                    name = match.group(1)
                    line = next(lines)
                    match = re_codepoint.search(line)
                    assert match

                    codepoint = match.group(1)[1:]
                    result[name] = chr(int(codepoint, 16))
            except StopIteration:
                break

    return result


def load_icon_codepoints_simple():
    css_path = Path.home() / ".local/share/fonts/MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints"  # noqa: E501

    result = dict()

    with open(css_path) as file:
        for line in file:
            name, codepoint = line.split()
            result[name] = chr(int(codepoint, 16))

    return result


def get_icon(name):
    global _icon_codepoints
    if _icon_codepoints is None:
        _icon_codepoints = load_icon_codepoints_simple()

    icon = _icon_codepoints.get(name, None)
    if icon is None:
        icon = _icon_codepoints.get("help")
    return icon


@component("icon")
class Icon(Container):
    @dataclass
    class Dependencies(Container.Dependencies):
        pass

    @dataclass
    class Properties(Container.Properties):
        name: str = ""
        color: str = "black"
        size: str = "large"

    @property
    def text(self):

        return (f'<span font="Material Symbols Outlined" '
                f'size="{self.properties.size}" '
                f'color="{self.properties.color}"'
                f'>'
                f'{get_icon(self.properties.name)}'
                '</span>')


def main():
    codepoints = load_icon_codepoints_simple()
    for name in codepoints.keys():
        print(name)


if __name__ == '__main__':
    main()
