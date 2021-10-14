from argparse import ArgumentParser
from aiohttp import ClientSession
from pathlib import Path

from json import dump as write_json
from tomli import load as parse_toml

from .Helpers.utils import get_pack_format, get_default_config, get_pack_manager

async def main():

    formats = ['packwiz', 'multimc', 'modrinth', 'curseforge', 'intermediate']
 
    parser = ArgumentParser(description="Converts modpack formats to each other", exit_on_error=True)
    parser.add_argument('-c', '--config', dest='config', type=Path, help='Path to config, used to fill the gaps in parsed data')
    parser.add_argument('-i', '--input', dest='input', type=Path, help='Path to pack', required=True)
    parser.add_argument('-f', '--format', dest='format', type=str, nargs="+", choices=formats, help='Format to convert to', required=True)
    parser.add_argument('-o', '--output', dest='output_dir', type=Path, help='Specify output directory (optional)')
    args = parser.parse_args()

    if not args.input.exists(): exit("Invalid input!")
    pack_format = get_pack_format(args.input)
    if pack_format == "Unknown": exit("Invalid pack input format!")

    config = get_default_config()

    if args.config:
        with open(args.config) as file:
            config.update(parse_toml(file))

    manager_class = get_pack_manager(pack_format)

    async with ClientSession() as session:
        input_manager = manager_class(session, config)
        config = await input_manager.parse(args.input)

        if not config['author']: config['author'] = input("Author: ")
        if not config['name']: config['name'] = input("Name: ")
        if not config['version']: config['version'] = input("Version: ")
        if not config['description']: config['description'] = input("Description: ")

    if "intermediate" in args.format:
        with open("intermediate_outout.json", "w") as file:
            write_json(config, file, indent=4)
