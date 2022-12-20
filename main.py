from __future__ import annotations

import json
import logging
import os
import re
from argparse import ArgumentParser
from configparser import ConfigParser
from glob import glob

import jinja2

from config import PreprocessingInterp, Config
from processor import LoaderDispatcher, AcceptAllProcessor, \
    PurchasePartsProcessor
from part import Part

FORMAT = '[%(levelname)s] %(asctime)s : %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('doc_compiler')
logger.setLevel(logging.DEBUG)

parser = ArgumentParser()
parser.add_argument("-c", "--config", help="load configuration file from disk", default='./config.ini')
args = parser.parse_args()

parser = ConfigParser(interpolation=PreprocessingInterp({
    'regex': lambda x: re.compile(x, re.IGNORECASE)
    }
))
parser.read(args.config)
config = Config(**dict(
    sum([list(parser[x].items()) for x in parser.sections()], [])
))


try:
    os.mkdir(config.out_path)
except FileExistsError:
    pass

with open(config.bom_json, encoding='utf-8') as f:
    part_list = json.load(f, )
    # Use Solid-generated bom part id instead of one of form VTOL.something.something.something
    # because this list contains duplicates - parts used in various assys
    parsed_structure = {
        (bom_part_id := x.pop(config.part_id_in_meta)): Part(
            full_name=(full_name := x.pop(config.part_name_in_meta).strip()),
            human_readable_name=config.human_readable_name_pattern.sub('', full_name),
            part_id=match.group() if (match := config.part_id_pattern.match(full_name)) else full_name,
            bom_part_id=bom_part_id.split('.'),
            metadata={k.strip(): v.strip() for k, v in x.items()}
        ) for x in sum(part_list, [])
    }

tree = {}
for part in parsed_structure.values():
    path = tree
    for x in part.bom_part_id:
        path[x] = path.get(x, {})
        path = path[x]
    path['part'] = part

queue = list(tree.values())
while queue:
    item = queue.pop()
    children = [v for k, v in item.items() if k != 'part']
    f = [x['part'] for x in children]
    item['part'].add_children(f)
    queue += children

# We no longer care about duplicates since the tree has already been built
parsed_structure = {
    v.full_name: v for k, v in parsed_structure.items()
}

logger.info(f'Loaded {len(parsed_structure)} parts from BOM table ')
files = (
    glob(config.project_path + '/**/*.SLDPRT', recursive=True) +
    glob(config.project_path + '/**/*.SLDASM', recursive=True)
)

# since Part is passed by-reference, those changes will be reflected in tree as well
filesystem_structure = {
    tuple(os.path.splitext(x[1])): x[0]
    for x in [list(os.path.split(k)) for k in files]
}
logger.info(f'Loaded {len(filesystem_structure)} parts from filesystem')

for k, v in filesystem_structure.items():
    if k[0] in parsed_structure:
        parsed_structure[k[0]].path = v
        parsed_structure[k[0]].full_name = ''.join(k)

if missing_in_bom := [k[0] for k, v in filesystem_structure.items() if k[0] not in parsed_structure]:
    logger.warning(
        f'Following parts {len(missing_in_bom)} appear in file system '
        f'but not in BOM table: {", ".join(missing_in_bom)}')

if missing_in_fs := [k for k, v in parsed_structure.items() if not v.path]:
    logger.warning(
        f'Following parts {len(missing_in_fs)} appear in BOM table '
        f'but not in file system: {", ".join(missing_in_fs)}')
    logger.warning(f'Virtual parts?')

part_tree = Part(
    full_name='VTOL.000.00.000 - Общая сборка.SLDASM',
    human_readable_name='Общая сборка.SLDASM',
    part_id='VTOL.000.00.000',
    bom_part_id='',
    path=config.out_path
)
part_tree.add_children([v['part'] for k, v in tree.items() if k != 'part'])


paths = set(v.path for k, v in parsed_structure.items() if v.path)
# jinja wants to know all template directory paths in advance
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        [config.templates_folder] +
        [os.path.join(x, config.docs_folder) for x in paths]
    )
)

env.trim_blocks = True
env.lstrip_blocks = True
env.filters['zip'] = zip
visited = set()

dispatcher = LoaderDispatcher().\
    register(PurchasePartsProcessor(env, config, fallthrough=True)).\
    register(AcceptAllProcessor(env, config))

for doc_dir in paths:
    files = os.listdir(doc_dir)
    sw_files = [x for x in files if config.sw_file_pattern.match(x)]

    for sw_file in sw_files:
        file_name = os.path.splitext(sw_file)[0]
        if not config.part_id_pattern.match(sw_file):
            logger.warning(f'File {sw_file} has invalid filename. Consider renaming it to follow the convention. '
                           f'This warning may turn into an error and crash the pipeline')
        part: Part = parsed_structure.get(file_name, None)
        if part is None:
            continue
        path = []
        next_part = part.parent
        while next_part.parent is not None:
            path.insert(0, next_part.part_id)
            next_part = next_part.parent
        path.insert(0, next_part.part_id)
        f = dispatcher.get(part)
        f.process(part)
dispatcher.finalize()

