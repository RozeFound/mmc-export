import asyncio
import sys
from argparse import SUPPRESS, ArgumentParser, Namespace
from ctypes import ArgumentError
from pathlib import Path
from pprint import pformat
from typing import IO
from urllib.parse import urlparse

import keyring as secret_store
from aiohttp_client_cache.session import CachedSession
from pytoml import loads as parse_toml

from .structures import Intermediate, Resource


def get_hash(file: Path | IO | bytes, hash_type: str = "sha256") -> str:

    if isinstance(file, Path): data = file.read_bytes()
    elif isinstance(file, IO): data = file.read()
    elif isinstance(file, bytes): data = file
    else: raise ArgumentError("Incorrect file type!")
        
    from hashlib import sha1, sha256, sha512

    from murmurhash2 import murmurhash2 as murmur2
    from xxhash import xxh3_64_hexdigest

    match hash_type:
        case "sha1": hash = sha1(data).hexdigest()
        case "sha256": hash = sha256(data).hexdigest()
        case "sha512": hash = sha512(data).hexdigest()
        case "xxhash": hash = xxh3_64_hexdigest(data)
        case "murmur2": hash = murmur2(bytes([b for b in data if b not in (9, 10, 13, 32)]), seed=1)
        case _: raise ArgumentError("Incorrect hash type!")

    return str(hash)

def get_hashes(file: Path | IO | bytes, *args: str):
    return [get_hash(file, hash_type) for hash_type in args]

async def add_github_token(session: CachedSession) -> None:

    client_id = "8011f22f502b091464de"
    session.headers['Accept'] = "application/json"

    async with session.disabled():
        url = "https://github.com/login/device/code"
        async with session.post(url, params={"client_id": client_id}) as response:
            data = await response.json()

            device_code = data['device_code']
            user_code = data['user_code']
            verification_uri = data['verification_uri']
            interval = data['interval']

            print(f" To proceed, enter the code: {user_code}")
            print(f"Here: {verification_uri}")

        payload = {"client_id": client_id, "device_code": device_code, 
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}

        while(True):      
            url = "https://github.com/login/oauth/access_token"
            async with session.post(url, params=payload) as response:
                data = await response.json()

                match data.get('error'):
                    case "authorization_pending": await asyncio.sleep(interval); continue
                    case "expired_token": print("Confirmation time is expired"); return
                    case "access_denied": print("Token request declined"); return

                if token := data.get('access_token'):
                    secret_store.set_password("mmc-export", "github-token", token)
                    print("Succsesfully authorized!")
                    return

def delete_github_token() -> None:
    try: secret_store.delete_password("mmc-export", "github-token")
    except secret_store.core.backend.errors.PasswordDeleteError: return

def get_github_token() -> str | None:
    return secret_store.get_password("mmc-export", "github-token")

def parse_args() -> Namespace:

    formats = ('packwiz', 'Modrinth', 'CurseForge', 'Intermediate')
    mr_search = ('exact', 'accurate', 'loose')
    providers = ('GitHub', 'CurseForge', 'Modrinth')
 
    arg_parser = ArgumentParser(usage=SUPPRESS, add_help=False)
    arg_parser.add_argument('-h', '--help', dest="help", action='store_true')
    arg_parser.add_argument('-c', '--config', dest='config', type=Path)
    arg_parser.add_argument('-i', '--input', dest='input', type=Path)
    arg_parser.add_argument('-f', '--format', dest='formats', type=str, nargs="+", choices=formats)
    arg_parser.add_argument('-o', '--output', dest='output', type=Path, default=Path.cwd())
    arg_parser.add_argument('--modrinth-search', dest='modrinth_search', type=str, choices=mr_search, default='exact')
    arg_parser.add_argument('--exclude-providers', dest='excluded_providers', type=str, nargs="+", choices=providers, default=str())
    arg_parser.add_argument('--exclude-forbidden', dest='ignore_CF_flag', action='store_false')
    arg_parser.add_argument('--skip-cache', dest='skip_cache', action='store_true')
    arg_parser.add_argument('-v', '--version', dest='modpack_version', type=str)

    arg_subs = arg_parser.add_subparsers(dest='cmd')
    arg_subs.add_parser('gh-login', add_help=False)
    arg_subs.add_parser('gh-logout', add_help=False)

    arg_cache = arg_subs.add_parser('purge-cache', add_help=False)
    arg_cache.add_argument('--web', dest='cache_web', action='store_true')
    arg_cache.add_argument('--files', dest='cache_files', action='store_true')
    arg_cache.add_argument('--all', dest='cache_all', action='store_true')
    
    args = arg_parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    if args.help: 
        print("mmc-export: Export MMC modpack to other modpack formats")
        print("Usage examples you can find here: https://github.com/RozeFound/mmc-export#how-to-use")

    if args.cmd and args.cmd == "purge-cache":
        if not args.cache_web or not args.cache_files or not args.cache_all:
            args.cache_all = True

    if not args.cmd:
        if not args.input: arg_parser.error("Input must be specified!")
        if not args.formats: arg_parser.error("At least one format must be specified!")
        if not args.input.exists(): arg_parser.error("Invalid input!")

    return args

def read_config_into(cfg_path: Path, intermediate: Intermediate, exclude_forbidden: bool) -> None:

    forbidden_domains = ("edge.forgecdn.net", "media.forgecdn.net")
    allowed_domains = ("cdn.modrinth.com", "edge.forgecdn.net", "media.forgecdn.net", "github.com", "raw.githubusercontent.com")
    if exclude_forbidden: allowed_domains = tuple(domain for domain in allowed_domains if domain not in forbidden_domains)
    
    lost_resources = [res for res in intermediate.resources if not res.providers]

    if cfg_path is not None and cfg_path.exists():
        config = parse_toml(cfg_path.read_text())
    else: config = {}

    intermediate.name = config.get('name', intermediate.name)
    intermediate.author = config.get('author', intermediate.author)
    intermediate.version = config.get('version', intermediate.version)
    intermediate.description = config.get('description', intermediate.description)
    if not intermediate.version: intermediate.version = input("Specify modpack version: ")

    for resource_config in config.get('Resource', []):

        url = resource_config.get('url')
        name = resource_config.get('name', "")
        filename = resource_config.get('filename', "")

        resource = next((x for x in intermediate.resources if name == x.name or filename == x.file.name), None)
        if not resource: continue

        match resource_config.get("action"):

            case None: # if action not specified, try to add a provider
                if not url: 
                    print(f"Failed to read config for {resource.name}, you must specify url!")
                elif urlparse(url).netloc not in allowed_domains:
                    print(f"Failed to read config for {resource.name}, wrong url domain!")
                    print(f"Allowed domains: {pformat(allowed_domains)}")
                else: resource.providers['Other'] = Resource.Provider(url = url)

            case "remove": 
                intermediate.resources.remove(resource)
            case "override": 
                intermediate.overrides.append(resource.file)
                intermediate.resources.remove(resource)
            case "ignore": pass
            case _: print(f"Wrong action for {resource.name}!")

        if resource in lost_resources:
            lost_resources.remove(resource)

    for resource in lost_resources:
        print("No config entry found for resource:", resource.name)
        
async def resolve_conflicts(session: CachedSession, intermediate: Intermediate) -> None: 

    async def download_file(url: str) -> tuple[str, bytes]:
        async with session.get(url) as response:
            assert response.status == 200
            return url, await response.read()

    futures = [download_file(r.providers['Other'].url) for r 
        in intermediate.resources if "Other" in r.providers]
    files = await asyncio.gather(*futures)

    for resource in intermediate.resources:
        if provider := resource.providers.get('Other'):
            cloud_file = next(file for url, file in files if url == provider.url)
            sha1, sha256, sha512 = get_hashes(cloud_file, "sha1", "sha256", "sha512")
            if "Modrinth" in resource.providers:
                if resource.file.hash.sha1 != sha1 or resource.file.hash.sha512 != sha512:
                    resource.providers.pop("Other")
            else: 
                resource.file.hash.sha1 = sha1
                resource.file.hash.sha256 = sha256 
                resource.file.hash.sha512 = sha512 
            