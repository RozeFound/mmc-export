from argparse import ArgumentParser
from aiohttp import ClientSession, TCPConnector
from pathlib import Path

from json import dump as write_json
from tomli import load as parse_toml

from .Helpers.utils import get_pack_format, get_default_config, get_pack_manager

async def main():

    formats = ['packwiz', 'multimc', 'modrinth', 'curseforge', 'intermediate']
 
    parser = ArgumentParser(description="Converts modpack formats to each other", exit_on_error=True)
    parser.add_argument('-c', '--config', dest='config', type=Path, help='Path to config, used to fill the gaps in parsed data')
    parser.add_argument('-i', '--input', dest='input', type=Path, help='Path to pack', required=True)
    parser.add_argument('-f', '--format', dest='formats', type=str, nargs="+", choices=formats, help='Format to convert to', required=True)
    parser.add_argument('-o', '--output', dest='output', type=Path, help='Specify output directory (optional)', default=Path.cwd())
    #args = parser.parse_args()

    # test MultiMC to ALL
    args = parser.parse_args(['-i', 'C:/users/Rozef/Desktop/dev/Optimized & Beautiful.zip',
                              '-f', 'intermediate', 'curseforge', 'packwiz',
                              '-c', 'example_config.toml',
                              '-o', 'C:/users/Rozef/Desktop'])

    # test packwiz to ALL
    args = parser.parse_args(['-i', 'C:/users/Rozef/Desktop/dev/FO',
                              '-f', 'intermediate', 'curseforge', 'packwiz',
                              '-c', 'example_config.toml',
                              '-o', 'C:/users/Rozef/Desktop'])

    if not args.input.exists(): exit("Invalid input!")
    input_format = get_pack_format(args.input)
    if input_format == "Unknown": exit("Invalid pack input format!")

    config = get_default_config()

    if args.config:
        with open(args.config, "rb") as file:
            config.update(parse_toml(file))

    async with ClientSession(connector=TCPConnector(limit=0)) as session:
        input_manager = get_pack_manager(input_format)(args.input, session, config)
        await input_manager.parse()

        if not config['author']: config['author'] = input("Author: ")
        if not config['name']: config['name'] = input("Name: ")
        if not config['version']: config['version'] = input("Version: ")
        if not config['description']: config['description'] = input("Description: ")

        if "Resource" in config: del config['Resource']

        for format in args.formats:

            if format == "intermediate":
                with open(args.output / "intermediate_output.json", "w") as file:
                    write_json(config, file, indent=4)
                continue
            
            if input_format == format:
                print(f"{format} to {format}? Why? Anyway it's a bad idea. I will prevent it.")
                continue

            output_manager = get_pack_manager(format)(args.output, session, config)
            output_manager.write()
