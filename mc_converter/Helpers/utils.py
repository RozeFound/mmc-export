from ctypes import ArgumentError
from os import walk
from pathlib import Path
from typing import Any

def get_hash(path: Path, type: str = "sha256") -> str | int:
        
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

    return hash

def get_pack_format(path: Path) -> str:

    # Key modpack identifiers:
    # Modrinth has index.json
    # MultiMC has mmc-pack.json and instance.cfg
    # CurseForge has manifest.json and modlist.html
    # packwiz is a folder, and has index.toml and pack.toml
    # So.. That was easier then I thought

    if path.is_dir():
        files = [file for _, _, filenames in walk(path) for file in filenames]
        if "index.toml" in files and "pack.toml" in files: return "packwiz"

    if str(path).endswith("zip"):
        from zipfile import ZipFile
        with ZipFile(path) as zip:

            filenames = [Path(file).name for file in zip.namelist()]

            if "index.json" in filenames: return "modrinth"
            elif "mmc-pack.json" in filenames and "instance.cfg" in filenames: return "multimc"
            elif "manifest.json" in filenames and "modlist.html" in filenames: return "curseforge"

    return "Unknown"

def get_default_config() -> dict[str, Any]:

    config = {
                "author": str(),
                "name": str(),
                "version": str(),
                "description": str(),

                "minecraft": str(),
                "modloader": {
                    "type": str(),
                    "version": str()
                },

                "resources": [],
                "overrides": []
            }

    return config

from mc_converter.multimc import MultiMCManager
from mc_converter.curseforge import CurseForgeManager
from mc_converter.modrinth import ModrinthManager
from mc_converter.packwiz import packwizManager

def get_pack_manager(pack_format: str):

    match pack_format:

        case "multimc": return MultiMCManager
        case "curseforge": return CurseForgeManager
        case "modrinth": return ModrinthManager
        case "packwiz": return packwizManager