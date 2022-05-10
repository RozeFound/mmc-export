from argparse import ArgumentParser
from aiohttp import ClientSession, TCPConnector, BasicAuth
from importlib import import_module
from pathlib import Path

from jsonpickle import encode as encode_json

from .parser import Parser
from .Helpers.utils import read_config
from .Helpers.resourceAPI import ResourceAPI

async def run():

    formats = ('packwiz', 'Modrinth', 'CurseForge', 'Intermediate')

    modrinth_search_help = """How accurate modrith search will be:\n
                              exact - uses hash to find file (default)\n
                              accurate - uses mod id, will find more mods without risks\n
                              loose - uses mod name, will find most mods, but have chance to find wrong one"""
 
    arg_parser = ArgumentParser(description="Export MMC modpack to other modpack formats", exit_on_error=True)
    arg_parser.add_argument('-c', '--config', dest='config', type=Path, help='Path to config, used to fill the gaps in parsed data')
    arg_parser.add_argument('-i', '--input', dest='input', type=Path, help='Path to pack', required=True)
    arg_parser.add_argument('-f', '--format', dest='formats', type=str, nargs="+", choices=formats, help='Format to convert to', required=True)
    arg_parser.add_argument('-o', '--output', dest='output', type=Path, help='Specify output directory (optional)', default=Path.cwd())
    arg_parser.add_argument('--github_auth', dest='github_auth', type=str, help='Github Auth in format username:token')
    arg_parser.add_argument('--modrinth_search', dest="modrinth_search", type=str, choices=("exact", "accurate", "loose"), help=modrinth_search_help, default="exact")
    args = arg_parser.parse_args()

    if not args.input.exists(): exit("Invalid input!")

    ResourceAPI.modrinth_search_type = args.modrinth_search

    if args.github_auth:
        login, password = args.github_auth.split(":")
        auth = BasicAuth(login, password, "utf-8")
    else: auth = None

    async with ClientSession(connector=TCPConnector(limit=0), auth=auth) as session:

        parser = Parser(args.input, session)
        intermediate = await parser.parse()
        read_config(args.config, intermediate)

        for format in args.formats:

            if format == "Intermediate":
                with open(args.output / "intermediate_output.json", "w") as file:
                    file.write(encode_json(intermediate, indent=4, unpicklable=False))
                continue

            module = import_module(f".Formats.{format.lower()}", "mmc-export")
            Writer = getattr(module, format)

            writer = Writer(args.output, intermediate)
            writer.write()         

    return 0

def main():
    import sys
    import asyncio
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
