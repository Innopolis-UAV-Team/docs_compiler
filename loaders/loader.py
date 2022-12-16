from __future__ import annotations

import logging
import os
import re
import shutil
from typing import Union, List

import jinja2
from jinja2 import Environment, TemplateNotFound

from config import Config
from part import Part


class BaseLoader:
    pattern = None
    fallthrough: bool = False

    def __init__(self, pattern: Union[str, re.Pattern], fallthrough=False):
        self.pattern = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern)
        self.fallthrough = fallthrough

    def load(self, part: Part):
        pass


class JinjaLoggedLoader(BaseLoader):
    env: jinja2.Environment = None
    logger: logging.Logger = None

    def __init__(self, pattern: Union[str, re.Pattern], env: jinja2.Environment, logger: logging.Logger = None):
        super().__init__(pattern)
        self.env = env
        if logger is None:
            logging.basicConfig(format='[%(levelname)s] %(asctime)s : %(message)s')
            self.logger = logging.getLogger(str(type(self)))
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger = logger


class AcceptAllLoader(JinjaLoggedLoader):
    config: Config

    def __init__(self, env: jinja2.Environment, config: Config):
        super().__init__('.*', env)
        self.config = config

    def load(self, part: Part):
        file_name = os.path.splitext(part.full_name)[0]
        doc_files = os.listdir(os.path.join(part.path, self.config.docs_folder))
        image_files = [x for x in doc_files if self.config.image_pattern.match(x) and x.startswith(file_name)]
        # skip parts that are not in BOM
        if not part:
            return
        try:
            template = self.env.get_template(f'{file_name}.md')
        except TemplateNotFound:
            self.logger.warning(f'File {part.full_name} does not have corresponding .md doc. '
                                f'Using default structure')
            match os.path.splitext(part.full_name)[-1].lower():
                case '.sldprt':
                    template = self.env.get_template('part.md')
                case '.sldasm':
                    template = self.env.get_template('assy.md')
                case _:
                    template = self.env.get_template('part.md')

        template_text = template.render(
            part_name=part.human_readable_name,
            part_info=str(part.metadata),
            images=image_files,
            children=part.children,
        )
        out_path = os.path.join(self.config.out_folder, *[
            match.group() if (match := self.config.part_id_pattern.match(x)) else x
            for x in os.path.normpath(os.path.relpath(part.path, self.config.project_path)).split(os.sep)
        ])

        os.makedirs(out_path, exist_ok=True)

        with open(os.path.join(out_path, f'{file_name}.md'), 'w', encoding='utf-8') as f:
            f.write(template_text)
        for image_file in image_files:
            shutil.copy(os.path.join(part.path, self.config.docs_folder, image_file), out_path)


class LoaderDispatcher:
    loaders: List[BaseLoader] = []

    def register(self, loader: BaseLoader) -> LoaderDispatcher:
        self.loaders.append(loader)
        return self

    def load(self, part: Part):
        for x in self.loaders:
            if x.pattern.match(part.full_name):
                x.load(part)
                if not x.fallthrough:
                    break
