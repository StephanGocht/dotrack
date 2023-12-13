from pathlib import Path
from guiml.resources import ResourceManager
from guiml.components import component as guiml_component
from dotrack import icon  # noqa: F401

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "../data"

res = ResourceManager(
    basedir=BASE_DIR
)


def component(name, template='auto'):
    if template == 'auto':
        template = res.template_file("templates.xml")

    return guiml_component(
        name=name,
        template=template,
        style=res.style_file("styles.yml"),
    )
