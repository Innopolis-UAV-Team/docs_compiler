import re
from configparser import ExtendedInterpolation, ConfigParser
from dataclasses import dataclass
from typing import Dict, Callable, Any


class PreprocessingInterp(ExtendedInterpolation):
    """Dummy interpolation that passes the value through with no changes."""
    processing: Dict[str, Callable[[str], Any]]

    def __init__(self, processing: Dict[str, Callable[[str], Any]]):
        self.processing = processing

    def before_get(self, parser: ConfigParser, section, option, value, defaults):
        value = super().before_get(parser, section, option, value, defaults)
        # preprocess both by option and section
        value = self.processing.get(section, lambda x: x)(value)
        return self.processing.get(option, lambda x: x)(value)


@dataclass
class Config:
    project_path: str
    bom_json: str
    docs_folder: str
    templates_folder: str
    part_name_in_meta: str
    part_id_in_meta: str
    out_path: str

    image_pattern: re.Pattern
    template_pattern: re.Pattern
    sw_file_pattern: re.Pattern
    part_id_pattern: re.Pattern
    human_readable_name_pattern: re.Pattern
