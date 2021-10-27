import asyncio
from pathlib import Path
from aiohttp.client import ClientSession

from tomli import load as parse_toml
from pytoml import dump as write_toml

from .Helpers.abstractions import ModpackManager
from .Helpers.utils import get_hash

class packwizManager(ModpackManager):

    def __init__(self, path: Path | str, session: ClientSession, config: dict[str]) -> None:

        self.pack_info = dict()

        self.index = {
            "hash-format": "sha256",
            "Files": []
        }

        super().__init__(path, session, config)

    async def get_resource(self, resource: dict[str]) -> None:

        toml_path: Path = self.temp_dir / resource['file']
        with open(toml_path, "rb") as file:
            toml_data = parse_toml(file)

        data = {
            "name": toml_data["name"],
            "filename": toml_data['filename'],

            "hashes": {
                toml_data['download']['hash-format']: toml_data['download']['hash']
            },

            "relative_path": toml_path.parts[-2],

            "side": {
                "client": "required" if toml_data['side'] == "client" else "optional",
                "server": "required" if toml_data['side'] == "server" else "optional",
                "summary": toml_data['side']
            },

            "downloads": {}
        }

        if "update" in toml_data:

            match toml_data['update']:

                case {"curseforge": cf}:

                    data['downloads']['CurseForge'] = {
                        "ID": cf['project-id'],
                        "fileID": cf['file-id'],
                        "url": toml_data['download']['url'],
                        "slug": toml_path.stem,
                        "author": await self.resource_manager.get_author(cf['project-id'], "CurseForge")
                    }

                case {"modrinth": mr}:

                    data['downloads']['Modrinth'] = {
                        "ID": mr['mod-id'],
                        "fileID": mr['version'],
                        "url": toml_data['download']['url'],
                        "slug": toml_path.stem,
                        "author": await self.resource_manager.get_author(mr['mod-id'], "Modrinth")
                    }
        else: 
            data['downloads']['Other'] = {
                "url": toml_data['download']['url'],
                "slug": toml_path.stem,
                "author": "Unknown"
            }

        self.config['resources'].append(data)

    def get_override(self, file: dict[str]) -> None:

        relaitve_path = Path(file['file'])
        full_path = self.temp_dir / relaitve_path

        data = {
            "filename": relaitve_path.name,

            "hashes": {
                "sha256": file['hash']
            },

            "full_path": full_path.as_posix(),
            "relative_path": relaitve_path.parent.as_posix()
        }

        self.config['overrides'].append(data)
    
    async def parse(self) -> None:

        if self.modpack_path.is_dir():
            self.temp_dir = self.modpack_path
        else:
            from shutil import unpack_archive
            unpack_archive(self.modpack_path, self.temp_dir)

        with open(self.temp_dir / "pack.toml", "rb") as file:
            self.pack_info = parse_toml(file)

        with open(self.temp_dir / self.pack_info['index']['file'], "rb") as file:
            self.index = parse_toml(file)

        for info_type in ("author", "name", "version", "description"):
            if info_type in self.pack_info and not self.config[info_type]:
                self.config[info_type] = self.pack_info[info_type]

        self.config['minecraft'] = self.pack_info['versions']['minecraft']

        match self.pack_info['versions']:
                case {'fabric': fabric_version}: 
                    self.config['modloader']['type'] = "fabric"
                    self.config['modloader']['version'] = fabric_version
                case {'forge': forge_version}:
                    self.config['modloader']['type'] = "forge"
                    self.config['modloader']['version'] = forge_version

        futures = []

        for file in self.index['files']:
            if "metafile" in file and file['metafile'] == True:
                futures.append(self.get_resource(file))
            else: self.get_override(file)

        await asyncio.gather(*futures)

    def write_pack_info(self) -> None:
        
        self.pack_info = {
            "name": self.config['name'],
            "author": self.config['author'],
            "version": self.config['version'],

            "index": {
                "file": "index.toml",
                "hash-format": "sha256",
                "hash": "placeholder"
            },

            "versions": {
                self.config['modloader']['type']: self.config['modloader']['version'],
                "minecraft": self.config['minecraft']
            }
        }

    def add_resource(self, resource: dict[str]) -> None:

        data = {
            "name": resource['name'],
            "filename": resource['filename'],
            "side": resource['side']['summary']
        }

        for provider in ("Modrinth", "CurseForge", "Other"):
            if provider in resource['downloads']:
                provider_data = resource['downloads'][provider]

                slug = provider_data['slug']

                match provider:
                    case "Modrinth": 
                        hash_format = "sha512" if "sha512" in resource['hashes'] else "sha1"
                        data['update'] = {
                            "modrinth": {
                                "mod-id": provider_data['ID'],
                                "version": provider_data['fileID']
                            }
                        }
                    case "CurseForge":
                        hash_format = "murmur2"
                        data['update'] = {
                            "curseforge": {
                                "file-id": provider_data['fileID'],
                                "project-id": provider_data['ID'],
                                "release-channel": "beta"
                            } 
                        }
                    case "Other": hash_format = "sha256"

                data['download'] = {
                    "url": provider_data['url'],
                    "hash-format": hash_format,
                    "hash": resource['hashes'][hash_format]
                }

                break
        
        toml_path = self.temp_dir / resource['relative_path'] / (slug + ".toml")
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        with open(toml_path, "w") as file:
            write_toml(data, file)

        index_data = {
            "file": toml_path.relative_to(self.temp_dir).as_posix(),
            "hash": get_hash(toml_path),
            "metafile": True
        }
        
        self.index['Files'].append(index_data)

    def add_override(self, file: dict[str]) -> None:

        file_path = self.temp_dir / file['relative_path']
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file['full_path'], file_path)

        data = {
            "path": file['relative_path'] + "/" + file['filename'],
            "hash": file['hashes']['sha256']
        }
        
        self.index['Files'].append(data)

    def write(self) -> None:

        for override in self.config['overrides']:
            self.add_override(override)

        for resource in self.config['resources']:
            self.add_resource(resource)

        index_path = self.temp_dir / "index.toml"
        with open(index_path, "w") as file:
            write_toml(self.index, file)

        self.write_pack_info()
        self.pack_info['index']['hash'] = get_hash(index_path)

        with open(self.temp_dir / "pack.toml", "w") as file:
            write_toml(self.pack_info, file)

        from shutil import make_archive
        make_archive(self.modpack_path / ("PW_" + self.config['name']), 'zip', self.temp_dir, '.')
