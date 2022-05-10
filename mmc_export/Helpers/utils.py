from werkzeug.utils import secure_filename
from tomli import loads as parse_toml
from ctypes import ArgumentError
from pathlib import Path

from .structures import Intermediate

def get_hash(path: Path, type: str = "sha256") -> str:
        
    from hashlib import sha1, sha256, sha512
    from murmurhash2 import murmurhash2 as murmur2

    with open(path, "rb") as file:
        data = file.read()

    match(type):

        case "sha1": hash = sha1(data).hexdigest()
        case "sha256": hash = sha256(data).hexdigest()
        case "sha512": hash = sha512(data).hexdigest()

        case "murmur2": 
            data = bytes([b for b in data if b not in (9, 10, 13, 32)])
            hash = murmur2(data, seed=1)

        case _: raise(ArgumentError("Incorrect hash type!"))

    return str(hash)

def read_config(cfg_path: Path, modpack_info: Intermediate):
 
    config = parse_toml(cfg_path.read_bytes()) if cfg_path is not None else None
    lost_resources = [res for res in modpack_info.resources if not res.providers]

    match config:
        case {'name': name}: modpack_info.name = name
        case {'author': author}: modpack_info.author = author
        case {'version': version}: modpack_info.version = version
        case {'description': description}: modpack_info.description = description

        case {'Resource': resources}: 
            for resource in lost_resources:
                for cfg_resource in resources:
                    if resource.name == cfg_resource['name'] or resource.file.name == cfg_resource['filename']:

                        resource.name = cfg_resource['name']
                        resource.file.name = cfg_resource['filename']

                        resource.providers['Github'](
                            ID     = None,
                            fileID = None,
                            url    = cfg_resource['url'],
                            slug   = secure_filename(resource.name).lower(),
                            author = None)

                        lost_resources.pop(resource)
                        break
    for resource in lost_resources:
        print("No config entry found for resource:", resource.name)
        modpack_info.overrides.append(resource.file)
        modpack_info.resources.remove(resource)
        