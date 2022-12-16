import json
import logging
import os
import re
from dataclasses import dataclass, field



@dataclass
class Config:
    project_path: str
    bom_json: str
    docs_folder: str
    templates_folder: str
    part_name_in_meta: str
    part_no_in_meta: str
    out_folder: str

    image_pattern: re.Pattern
    template_pattern: re.Pattern
    sw_file_pattern: re.Pattern
    part_id_pattern: re.Pattern
    human_readable_name_pattern: re.Pattern

    def __post_init__(self):
        self.image_pattern = re.compile(self.image_pattern, re.IGNORECASE)
        self.template_pattern = re.compile(self.template_pattern, re.IGNORECASE)
        self.sw_file_pattern = re.compile(self.sw_file_pattern, re.IGNORECASE)
        self.part_id_pattern = re.compile(self.part_id_pattern)
        self.human_readable_name_pattern = re.compile(self.human_readable_name_pattern, re.IGNORECASE)

        self.bom_json = os.path.join(self.project_path, self.bom_json)
        self.templates_folder = os.path.join(self.project_path, self.templates_folder)