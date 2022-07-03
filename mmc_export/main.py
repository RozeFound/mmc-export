from importlib import import_module
from json import dump as write_json
from shutil import rmtree

from aiohttp import TCPConnector
from aiohttp_client_cache.backends.filesystem import FileBackend
from aiohttp_client_cache.session import CachedSession

from .Helpers.resourceAPI import ResourceAPI
from .Helpers.utils import (JsonEncoder, add_github_token, parse_args,
                            read_config_into, resolve_conflicts)
from .parser import Parser
from . import config


async def program():

    args = parse_args()

    ResourceAPI.modrinth_search_type = args.modrinth_search
    ResourceAPI.excluded_providers = args.excluded_providers

    cache = FileBackend("mmc-export", use_temp=True, urls_expire_after={'*.jar': -1}, allowed_methods=("GET", "POST", "HEAD"))
    async with CachedSession(cache=cache, connector=TCPConnector(limit=0)) as session: 
        if args.skip_cache: session.cache.disabled = True # type: ignore

        match args.cmd:
            case "gh-login": await add_github_token(session); return # type: ignore
            case "gh-logout": 
                url = "https://github.com/settings/connections/applications/8011f22f502b091464de"
                print(f"You can revoke your access token by the following link: \n{url}"); return
            case "purge-cache":
                if args.cache_web or args.cache_all: await session.cache.clear() # type: ignore
                if args.cache_files or args.cache_all: rmtree(config.DEFAULT_CACHE_DIR, ignore_errors=True)
                return

        parser = Parser(args.input, session) # type: ignore
        intermediate = await parser.parse()
        
        if version := args.modpack_version: intermediate.version = version
        read_config_into(args.config, intermediate)
        await resolve_conflicts(session, intermediate) # type: ignore

        for format in args.formats:

            if format == "Intermediate":
                with open(args.output / "intermediate_output.json", "w") as file:
                    write_json(intermediate, file, indent=4, cls=JsonEncoder)
                continue

            module = import_module(f".Formats.{format.lower()}", "mmc_export")
            Writer = getattr(module, format)

            writer = Writer(args.output, intermediate)
            writer.write()         

    return 0

def main():
    import asyncio, sys
    if sys.platform.startswith("win"):
        policy = asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore
        asyncio.set_event_loop_policy(policy)
                
    try: asyncio.run(program())
    except KeyboardInterrupt: 
        print("Operation aborted by user.")
