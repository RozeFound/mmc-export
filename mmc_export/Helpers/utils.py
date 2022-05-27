import asyncio
from ctypes import ArgumentError
from pathlib import Path
from pprint import pformat
from typing import IO
from urllib.parse import urlparse

import keyring as secret_store
from aiohttp_client_cache.session import CachedSession
from tomli import loads as parse_toml

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

def delete_github_token() -> None:
    try: secret_store.delete_password("mmc-export", "github-token")
    except secret_store.core.backend.errors.PasswordDeleteError: return

async def get_github_token(session: CachedSession) -> str | None:

    if token := secret_store.get_password("mmc-export", "github-token"):
        return token

    client_id = "8011f22f502b091464de"
    url = "https://github.com/login/device/code"
    session.headers['Accept'] = "application/json"

    async with session.disabled():

        async with session.post(url, params={"client_id": client_id}) as response:
            data = await response.json()

            device_code = data['device_code']
            user_code = data['user_code']
            verification_uri = data['verification_uri']
            interval = data['interval']

            print(f"Enter the code: {user_code}")
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
                        return token

def read_config(cfg_path: Path, modpack_info: Intermediate):

    allowed_domains = ("cdn.modrinth.com", "edge.forgecdn.net", "media.forgecdn.net", "github.com", "raw.githubusercontent.com")
    lost_resources = [res for res in modpack_info.resources if not res.providers]

    if cfg_path is not None and cfg_path.exists():
        config = parse_toml(cfg_path.read_text())
    else: config = {}

    modpack_info.name = config.get('name', modpack_info.name)
    modpack_info.author = config.get('author', modpack_info.author)
    modpack_info.version = config.get('version', modpack_info.version)
    modpack_info.description = config.get('description', modpack_info.description)
    if not modpack_info.version: modpack_info.version = input("Specify modpack version: ")

    for resource_config in config.get('Resource', []):

        url = resource_config.get('url')
        name = resource_config.get('name')
        filename = resource_config.get('filename')

        resource = next((x for x in lost_resources if name in x.name or filename in x.file.name), None)
        if not resource: continue

        match resource_config.get("action"):
            case "remove": 
                modpack_info.resources.remove(resource)
                lost_resources.remove(resource)
                continue
            case "override": 
                modpack_info.overrides.append(resource.file)
                modpack_info.resources.remove(resource)
                lost_resources.remove(resource)

                continue

        if not url: print(f"Failed to read config for {resource.name}, you must specify url!"); continue
        if urlparse(url).netloc not in allowed_domains:
            print(f"Failed to read config for {resource.name}, wrong url domain!")
            print(f"Allowed domains: {pformat(allowed_domains)}")
            continue

        resource.providers['Other'] = Resource.Provider(
            ID     = None,
            fileID = None,
            url    = url)

        lost_resources.remove(resource)

    for resource in lost_resources:
        print("No config entry found for resource:", resource.name)
        modpack_info.overrides.append(resource.file)
        modpack_info.resources.remove(resource)
        