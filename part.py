from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Dict, Union


@dataclass
class Part:
    full_name: str
    part_id: str
    human_readable_name: str

    bom_part_id: str
    path: str = field(default="")
    children: List[Part] = field(default_factory=list)
    parent: Part = field(default=None)
    metadata: Dict[str, str] = field(default_factory=dict)

    def add_children(self, parts: Union[Part, List[Part]]):
        for part in parts:
            self.children.append(part)
            part.parent = self

    def get_tree_path(self) -> str:
        path = []
        next_part = self.parent
        while next_part.parent is not None:
            path.insert(0, next_part.part_id)
            next_part = next_part.parent
        path.insert(0, next_part.part_id)
        return os.path.join(*path)
