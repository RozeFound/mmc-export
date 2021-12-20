from os import walk
from pathlib import Path
from aiohttp import ClientSession

from json import load as parse_json

import asyncio

from .Helpers.abstractions import ModpackManager
from .Helpers.resourceAPI import Resource
from .Helpers.utils import get_hash

class ModrinthManager(ModpackManager):

    def __init__(self, path: Path | str, session: ClientSession, config: dict[str]) -> None:

        self.index = dict()

        super().__init__(path, session, config)

    async def get_resource(self, file: dict[str]) -> None:

        resource: Resource = None

        for k, v in file['hashes']:
            temp_resource = await self.resource_manager.get_by_hash(k, v)

            if resource is not None:
                resource.downloads.update(temp_resource.downloads)
                resource.hashes.update(temp_resource.hashes)
                continue

            resource = temp_resource

        if resource is None: return

        path = Path(file['path'])

        data = {
                
                "name": resource.name,
                "filename": resource.filename,

                "hashes": resource.hashes,

                "relative_path": path.parent.name,

                "side": resource.side,
                "downloads": resource.downloads
            }

        self.config['resources'].append(data)  

    def get_override(self, path: Path) -> None:

        overrides_dir = self.temp_dir / "overrides"
        relative_path = path.relative_to(overrides_dir)

        data = {
            "filename": path.name,

            "hashes": {
                "sha256": get_hash(path)
            },

            "full_path": path.as_posix(),
            "relative_path": relative_path.as_posix(),
        }
        
        self.config['overrides'].append(data)

    async def parse(self) -> None:

        from shutil import unpack_archive
        unpack_archive(self.modpack_path, self.temp_dir)

        with open(self.temp_dir / "modrinth.index.json") as file:
            self.index = parse_json(file)

        self.config['name'] = self.index['name']
        self.config['version'] = self.index['versionId']
        if "summary" in self.index:
            self.config['description'] = self.index['summary']

        self.config['minecraft'] = self.index['dependencies']['minecraft']

        match self.index['dependencies']:
            case {'fabric-loader': fabric_version}: 
                self.config['modloader']['type'] = "fabric"
                self.config['modloader']['version'] = fabric_version
            case {'forge': forge_version}: 
                self.config['modloader']['type'] = "forge"
                self.config['modloader']['version'] = forge_version

        futures = []

        for resource in self.index['files']:
            futures.append(self.get_resource(resource))

        await asyncio.gather(*futures)

        overrides = [Path(file) for _, _, filenames in walk(self.temp_dir / "overrides") for file in filenames]

        for override in overrides:
            self.get_override(override)

    def write_index(self): 

        match self.config['modloader']['type']:

            case "fabric": modloader = "fabric-loader"
            case _: modloader = self.config['modloader']['type']

        if self.config['modloader']['type'] == "fabric":
            modloader = "fabric-loader"
        
        self.index = {
            "formatVersion": 1,
            "game": "minecraft",

            "versionId": self.config['version'],
            "name": self.config['name'],
            "summary": self.config['description'],

            "files": [],

            "dependencies": {
                "minecraft": self.config['minecraft'],
                modloader: self.config['modloader']['version']
            }
        }

    def add_resource(self, resource: dict[str]) -> None:
        
        relative_path: Path = Path(resource['relative_path']) / resource['filename']

        data = {
            "path": relative_path.as_posix(),
            "hashes": resource['hashes'],
            "downloads": [resource['downloads'][provider]['url'] for provider in resource['downloads']]
        }

        self.index['files'].append(data)

    def add_override(self, file: dict[str]) -> None:

        overrides_dir = self.temp_dir / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)

        file_path = overrides_dir / file['relative_path']
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file['full_path'], file_path)

    def write(self) -> None:

        self.write_index()

        for override in self.config['overrides']:
            self.add_override(override)

        for resource in self.config['resources']:
            self.add_resource(resource)

        from json import dump as write_json
        with open(self.temp_dir / "modrinth.index.json", 'w') as file:
            write_json(self.index, file)

        from shutil import make_archive
        archive_name = make_archive(self.modpack_path / ("MR_" + self.config['name']), 'zip', self.temp_dir, '.')
        Path(archive_name).rename(archive_name.replace("zip", "mrpack"))
