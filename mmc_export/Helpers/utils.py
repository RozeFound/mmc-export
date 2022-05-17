from tomli import loads as parse_toml
from urllib.parse import urlparse
from ctypes import ArgumentError
from pprint import pformat
from pathlib import Path

from .structures import Intermediate, Resource

def get_hash(path: Path, type: str = "sha256") -> str:
        
    from xxhash import xxh3_64_hexdigest
    from hashlib import sha1, sha256, sha512
    from murmurhash2 import murmurhash2 as murmur2

    with open(path, "rb") as file:
        data = file.read()

    match(type):
        case "sha1": hash = sha1(data).hexdigest()
        case "sha256": hash = sha256(data).hexdigest()
        case "sha512": hash = sha512(data).hexdigest()
        case "xxhash": hash = xxh3_64_hexdigest(data)
        case "murmur2": hash = murmur2(bytes([b for b in data if b not in (9, 10, 13, 32)]), seed=1)
        case _: raise ArgumentError("Incorrect hash type!")

    return str(hash)

def read_config(cfg_path: Path, modpack_info: Intermediate):

    allowed_domains = ("cdn.modrinth.com", "edge.forgecdn.net", "media.forgecdn.net", "github.com", "raw.githubusercontent.com")
 
    lost_resources = [res for res in modpack_info.resources if not res.providers]

    if cfg_path is not None and cfg_path.exists():
        config = parse_toml(cfg_path.read_text())
        for cfg_tuple in config.items():

            match cfg_tuple:

                case 'name', name: modpack_info.name = name
                case 'author', author: modpack_info.author = author
                case 'version', version: modpack_info.version = version
                case 'description', description: modpack_info.description = description
                case 'Resource', resources: 
                    for resource in lost_resources:
                        for cfg_resource in resources:
                            if resource.name == cfg_resource['name'] or resource.file.name == cfg_resource['filename']:

                                url = cfg_resource['url']

                                if urlparse(url).netloc not in allowed_domains:
                                    print(f"Failed to read config for {resource.name}, wrong url domain!")
                                    print(f"Allowed domains: {pformat(allowed_domains)}")
                                    continue

                                resource.providers['Other'] = Resource.Provider(
                                    ID     = None,
                                    fileID = None,
                                    url    = url,
                                    slug   = None,
                                    author = None)

                                lost_resources.remove(resource)
                                break

    for resource in lost_resources:
        print("No config entry found for resource:", resource.name)
        modpack_info.overrides.append(resource.file)
        modpack_info.resources.remove(resource)
        