import asyncio
from pathlib import Path
from tempfile import tempdir
from typing import Any
from aiohttp import ClientSession

from .Helpers.resourceAPI import ResourceAPI
from .Helpers.utils import get_hash

class MultiMCManager(object):

    def __init__(self, session: ClientSession, config: dict[str, Any]) -> None:

        from tempfile import TemporaryDirectory
        self.temp_dir = Path(TemporaryDirectory().__enter__())

        self.session = session
        self.config = config

        self.resource_manager = ResourceAPI(self.session)

        super().__init__()

    def __del__(self):
        self.temp_dir.__exit__(None, None, None)

    async def add_resource(self, path: Path) -> None:

        data = {}

        if resource := await self.resource_manager.get(path):
        
            data = {
                
                "provider": resource.resourceProvider,
                "name": resource.resourceName,
                "slug": resource.resourceSlug,

                "ID": resource.resourceID,
                "fileID": resource.fileID,

                "side": {
                    "client": resource.resourceSide.client,
                    "server": resource.resourceSide.server,
                    "summary": resource.resourceSide.summary
                },

                "file": {
                    "filename": resource.file.filename,
                    "relative_path": path.parent.name,
                    "url": resource.file.url,

                    "hash": {
                        "type": resource.file.hash.type,
                        "hash": resource.file.hash.value
                    }
                }
            }

        elif path.name in [item['filename'] for item in self.config['Resource']]:

            resource = [item for item in self.config['Resource'] if item['filename'] == path.name][0]

            data = {

                "provider": "Other",
                "name": resource['name'],
                "slug": resource['slug'],
                
                "side": {
                    "client": "optional",
                    "server": "optional",
                    "summary": "both"
                },

                "file": {
                    "filename": path.name,
                    "relative_path": path.parent.name,
                    "url": resource['url'],

                    "hash": {
                        "type": "sha256",
                        "hash": get_hash(path)
                    }
                }
            }

            self.config['Resource'].remove(resource)

        else: 
            print(f"File {path.name} not found of CF or MR")
            return self.add_override(path)

        self.config['resources'].append(data)

    def add_override(self, path: Path) -> None: 

        root_dir_id = path.parts.index(".minecraft")
        relative_path = path.relative_to(*path.parts[:root_dir_id + 1]).parent

        data = {
            "filename": path.name,
            "full_path": path.as_posix(),
            "relative_path": relative_path.as_posix(),

            "hash": {
                "type": "sha256",
                "hash": get_hash(path)
            }
        }
        
        self.config['overrides'].append(data)

    async def parse(self, path: Path) -> None:

        downloadable_content = ("resourcepacks", "shaderpacks", "mods")

        from shutil import unpack_archive
        from os import walk
        
        unpack_archive(path, self.temp_dir)

        futures = list()
        overrides = list()

        for folder_path, _, filenames in walk(self.temp_dir):
            if ".minecraft" not in folder_path: continue
            for filename in filenames:
                filepath = Path(folder_path) / filename
                if folder_path.endswith(downloadable_content): 
                    future = self.add_resource(filepath)
                    futures.append(future)
                else: overrides.append(filepath)

        await asyncio.gather(*futures)
        for override in overrides:
            self.add_override(override)

        del self.config['Resource']

        modpack_dir = next(self.temp_dir.iterdir())
        if not self.config['name']: self.config['name'] = modpack_dir.name

        from json import load

        with open(modpack_dir / "mmc-pack.json") as file:
            json = load(file)

        for component in json['components']:
            if component['cachedName'] == "Minecraft":
                if not self.config['minecraft']: 
                    self.config['minecraft'] = component['cachedVersion']
            elif component['cachedName'] == "Fabric Loader":
                if not self.config['modloader']['type']: 
                    self.config['modloader']['type'] = "fabric"
                    self.config['modloader']['version'] = component['cachedVersion']
            elif component['cachedName'] == "Forge":
                if not self.config['modloader']['type']: 
                    self.config['modloader']['type'] = "forge"
                    self.config['modloader']['version'] = component['cachedVersion']

        return self.config

    def write(self): raise NotImplementedError("MultiMC write is not inmplemented yet!")