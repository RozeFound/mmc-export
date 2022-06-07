from importlib import import_module
from pathlib import Path
from shutil import rmtree

from aiohttp import TCPConnector
from aiohttp_client_cache.backends.filesystem import FileBackend
from aiohttp_client_cache.session import CachedSession
from json import dump as write_json

from .Helpers.resourceAPI import ResourceAPI
from .Helpers.utils import (add_github_token, parse_args, read_config_into,
                            resolve_conflicts)
from .parser import Parser


async def run():

    args = parse_args()

    ResourceAPI.modrinth_search_type = args.modrinth_search
    ResourceAPI.excluded_providers = args.excluded_providers
    ResourceAPI.ignore_CF_flag = args.ignore_CF_flag

    cache = FileBackend("mmc-export", use_temp=True, allowed_methods=("GET", "POST", "HEAD"))
    async with CachedSession(cache=cache, connector=TCPConnector(limit=0)) as session: 
        if args.skip_cache: session.cache.disabled = True # type: ignore

        match args.cmd:
            case "gh-login": await add_github_token(session); return # type: ignore
            case "gh-logout": 
                url = "https://github.com/settings/connections/applications/8011f22f502b091464de"
                print(f"You can revoke your access token by the following link: \n{url}"); return
            case "purge-cache":
                if args.cache_web or args.cache_all: 
                    await session.cache.clear() # type: ignore
                if args.cache_files or args.cache_all: 
                    cache_directory = Path().home() / ".cache/mmc-export"
                    rmtree(cache_directory, ignore_errors=True)
                return

        parser = Parser(args.input, session) # type: ignore
        intermediate = await parser.parse()
        
        if version := args.modpack_version: intermediate.version = version
        read_config_into(args.config, intermediate, not args.ignore_CF_flag)
        await resolve_conflicts(session, intermediate) # type: ignore

        for format in args.formats:

            if format == "Intermediate":
                with open(args.output / "intermediate_output.json", "w") as file:
                    write_json(intermediate.to_dict(), file, indent=4)
                continue

            module = import_module(f".Formats.{format.lower()}", "mmc_export")
            Writer = getattr(module, format)

            writer = Writer(args.output, intermediate)
            writer.write()         

    return 0

def main():
    import asyncio
    import sys
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore
                
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())
    except KeyboardInterrupt: 
        print("Operation aborted by user.")
