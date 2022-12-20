import re
from dataclasses import dataclass


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
