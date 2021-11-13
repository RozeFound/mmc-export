import asyncio
from pathlib import Path

from .Helpers.abstractions import ModpackManager
from .Helpers.utils import get_hash

class MultiMCManager(ModpackManager):

    async def get_resource(self, path: Path) -> None:

        data = {}

        if resource := await self.resource_manager.get(path):

            data = {
                
                "name": resource.name,
                "filename": resource.filename,

                "hashes": resource.hashes,

                "relative_path": path.parent.name,
                "full_path": path.as_posix(),

                "side": resource.side,
                "downloads": resource.downloads
            }

        elif "Resource" in self.config and path.name in [item['filename'] for item in self.config['Resource']]:

            resource = [item for item in self.config['Resource'] if item['filename'] == path.name][0]

            data = {

                "name": resource['name'],
                "filename": path.name,

                "hashes": {
                    "sha256": get_hash(path)
                },
                
                "relative_path": path.parent.name,
                "full_path": path.as_posix(),

                "side": {
                    "client": "optional",
                    "server": "optional",
                    "summary": "both"
                },

                "downloads": {
                    "Other": {
                        "url": resource['url'],
                        "slug": resource['slug'],
                        "author": "Unknown"
                    }
                }
            }

            self.config['Resource'].remove(resource)

        else: 
            print(f"File {path.name} not found of CF or MR")
            return self.get_override(path)

        self.config['resources'].append(data)

    def get_override(self, path: Path) -> None: 

        root_dir_id = path.parts.index(".minecraft")
        relative_path = path.relative_to(*path.parts[:root_dir_id + 1]).parent

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

        downloadable_content = ("resourcepacks", "shaderpacks", "mods")

        from shutil import unpack_archive
        from os import walk
        
        unpack_archive(self.modpack_path, self.temp_dir)

        futures = list()
        overrides = list()

        for folder_path, _, filenames in walk(self.temp_dir):
            if ".minecraft" not in folder_path: continue
            for filename in filenames:
                filepath = Path(folder_path) / filename
                if folder_path.endswith(downloadable_content): 
                    future = self.get_resource(filepath)
                    futures.append(future)
                else: overrides.append(filepath)

        await asyncio.gather(*futures)
        for override in overrides:
            self.get_override(override)

        modpack_dir = next(self.temp_dir.iterdir())
        if not self.config['name']: self.config['name'] = modpack_dir.name

        from json import load as parse_json

        with open(modpack_dir / "mmc-pack.json") as file:
            json = parse_json(file)

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


    def write(self) -> None:
        return super().write()
