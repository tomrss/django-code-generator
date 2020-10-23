import os
from pathlib import Path

from django.db import models
from django.template import Engine, Context

from django_code_generator.exceptions import DjangoCodeGeneratorError, TemplateNotFound
from django.template.loader import render_to_string

from django_code_generator.models import get_models, Models

if hasattr(models, 'get_apps'):
    def get_apps():
        for app in models.get_apps():
            yield app.__name__.rsplit('.', 1)[0], app
else:
    from django.apps.registry import apps

    def get_apps():
        for app_config in apps.get_app_configs():
            yield app_config.name, app_config


def relative(root, path):
    return path.replace(root, '', 1).lstrip('/')


def walk(path):
    yield path
    if not path.is_dir():
        return
    for node in path.iterdir():
        yield from walk(node)


def get_template_directory(directories, template):
    for directory in filter(lambda x: bool(x), directories):
        template_dir = os.path.join(directory, template)
        if os.path.lexists(template_dir):
            return template_dir
    raise TemplateNotFound(directories, template)


class Template:
    def __init__(self, directory, app_name):
        self.directory = directory
        self.app_name = app_name

        installed_apps = dict(get_apps())
        self.app = installed_apps.get(app_name)

        if self.app is None:
            raise DjangoCodeGeneratorError('App {} is not available'.format(app_name))

    def render(self):
        path = Path(self.directory)
        engine = Engine(debug=True, dirs=[self.directory], libraries={
            'code_generator_tags': 'django_code_generator.templatetags.code_generator_tags'
        })
        for node in walk(path):
            relative_path = relative(str(path), str(node))
            to_path = os.path.join(self.app.path, relative_path)
            if node.is_dir():
                os.makedirs(to_path, exist_ok=True)
            else:
                (root, ext) = os.path.splitext(to_path)
                if ext != '.tpl':
                    continue
                to_path_py_ext = root + '.py'
                template = engine.get_template(str(node))
                rendered = template.render(Context({'models': Models(self.app), 'app': self.app}))
                with open(to_path_py_ext, 'w') as f:
                    f.write(rendered)
