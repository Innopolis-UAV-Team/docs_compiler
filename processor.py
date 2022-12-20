from __future__ import annotations

import logging
import os
import re
import shutil
from typing import Union, List, Dict, Optional, Tuple

import jinja2
from jinja2 import Environment, TemplateNotFound

from config import Config
from part import Part

Assets = Dict[str, List[str]]


class BaseProcessor:
    pattern = None
    fallthrough: bool = False
    _next: BaseProcessor = None

    def __init__(self, pattern: Union[str, re.Pattern], fallthrough=False):
        self.pattern = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern)
        self.fallthrough = fallthrough

    def process(self, part: Part):
        if self._next is not None:
            self._next.process(part)

    def finalize(self, *args, **kwargs):
        if self._next is not None:
            self._next.finalize(*args, **kwargs)

    def _register_next(self, other: BaseProcessor):
        self._next = other


class JinjaLoggedProcessor(BaseProcessor):
    env: jinja2.Environment = None
    logger: logging.Logger = None
    template_text: str
    config: Config = None

    def __init__(self, pattern: Union[str, re.Pattern], env: jinja2.Environment,
                 config: Config, logger: logging.Logger = None, fallthrough=False):
        super().__init__(pattern, fallthrough=fallthrough)
        self.env = env
        self.config = config
        if logger is None:
            logging.basicConfig(format='[%(levelname)s] %(asctime)s : %(message)s')
            self.logger = logging.getLogger(str(type(self)))
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger = logger


class AcceptAllProcessor(JinjaLoggedProcessor):
    def __init__(self, env: jinja2.Environment, config: Config, fallthrough=False):
        super().__init__('.*', env, config, fallthrough=fallthrough)

    def process(self, part: Part):
        super().process(part)
        file_name = os.path.splitext(part.full_name)[0]

        doc_files = os.listdir(
            os.path.join(part.path, self.config.docs_folder))
        image_files = [
            x for x in doc_files if
            self.config.image_pattern.match(x)
            and x.startswith(file_name)
        ]

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

        self.template_text = template.render(
            part_name=part.human_readable_name,
            part_info=str(part.metadata),
            images=image_files,
            children=part.children,
        )

        path = os.path.join(self.config.out_path, part.get_tree_path())
        os.makedirs(path, exist_ok=True)

        with open(os.path.join(path, f"{part.part_id}.md"), 'w',
                  encoding='utf-8') as f:
            f.write(self.template_text)
        for image_file in image_files:
            shutil.copy(
                os.path.join(path, self.config.docs_folder, image_file), path)


class PurchasePartsProcessor(JinjaLoggedProcessor):
    parts: List[Part]

    def __init__(self, env: jinja2.Environment, config: Config, fallthrough=False):
        super().__init__('VTOL.900*', env, config, fallthrough=fallthrough)
        self.parts = []

    def process(self, part: Part):
        super().process(part)
        self.parts.append(part)

    def finalize(self, *args, **kwargs):
        template = self.env.get_template('purchase.md')
        text = template.render(
            parts=self.parts,
            paths=[x.get_tree_path() for x in self.parts]
        )
        with open(os.path.join(
                self.config.out_path,
                'VTOL.000.00.000/VTOL.900.00.000.md'), 'w') as f:
            f.write(text)


class LoaderDispatcher:
    processors: List[BaseProcessor] = []

    def register(self, loader: BaseProcessor) -> LoaderDispatcher:
        self.processors.append(loader)
        return self

    def get(self, part: Part) -> BaseProcessor:
        processors = []
        for x in self.processors:
            if x.pattern.match(part.full_name):
                processors.append(x)
                if not x.fallthrough:
                    break
        processor = processors[0]
        for proc in processors[1:]:
            processor._register_next(proc)
            processor = proc
        return processors[0]

    def finalize(self, *args, **kwargs):
        for x in self.processors:
            x.finalize(*args, **kwargs)

