import asyncio
from os import walk
from pathlib import Path
from aiohttp import ClientSession

from mc_converter.Helpers.resourceAPI import Resource
from mc_converter.Helpers.utils import get_hash
from .Helpers.abstractions import ModpackManager

from json import load as parse_json

class CurseForgeManager(ModpackManager):

    def __init__(self, path: Path | str, session: ClientSession, config: dict[str]) -> None:

        self.manifest = dict()
        self.modlist = list()

        super().__init__(path, session, config)

    async def get_resource(self, resource: dict[str]) -> None:
        
        ID = resource['projectID']
        fileID = resource['fileID']

        resource: Resource = await self.resource_manager.get_by_ID(ID, fileID)
        if resource is None: return

        data = {       
            "name": resource.name,
            "filename": resource.filename,

            "hashes": resource.hashes,

            "relative_path": "mods" if Path(resource.filename).suffix == ".jar" else "resourcepacks", # I don't know how to categorize it anyway

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

        with open(self.temp_dir / "manifest.json") as file:
            self.manifest = parse_json(file)

        for entry in ("author", "name", "version"):
            if entry in self.manifest and not self.config[entry]:
                self.config[entry] = self.manifest[entry]

        self.config['minecraft'] = self.manifest['minecraft']['version']

        for loader in self.manifest['minecraft']['modloaders']:

            if "fabric" in loader['id']:
                self.config['modloader']['type'] = "fabric"
            if "forge" in loader['id']:
                self.config['modloader']['type'] = "forge"

            self.config['modloader']['version'] = loader['id'].split("-")[-1]

        futures = []

        for resource in self.manifest['files']:
            futures.append(self.get_resource(resource))

        await asyncio.gather(*futures)

        overrides = [Path(file) for _, _, filenames in walk(self.temp_dir / "overrides") for file in filenames]

        for override in overrides:
            self.get_override(override)

    def write_manifest(self) -> None:

        self.manifest = {
            "minecraft": {
                "version": self.config['minecraft'],
                "modLoaders": [
                    {
                    "id": f"{self.config['modloader']['type']}-{self.config['modloader']['version']}",
                    "primary": True
                    }
                ]
            },
            "manifestType": "minecraftModpack",
            "manifestVersion": 1,
            "name": self.config['name'],
            "version": self.config['version'],
            "author": self.config['author'],

            "files": [],
            "overrides": "overrides"
        }

    def add_resource(self, resource: dict[str]) -> None:

        provider_data = resource['downloads']['CurseForge']

        data = {
            "projectID": provider_data['ID'],
            "fileID": provider_data['fileID'],
            "required": True
        }

        self.manifest['files'].append(data)
        mod_page_url = "https://www.curseforge.com/minecraft/mc-mods/" + provider_data['slug']
        self.modlist.append(f"<li><a href=\"{mod_page_url}\">{resource['name']} (by {provider_data['author']})</a></li>\n")

    def add_override(self, file: dict[str]) -> None:

        if "full_path" not in file: return

        overrides_dir = self.temp_dir / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)

        file_path = overrides_dir / file['relative_path']
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file['full_path'], file_path)

    def write(self) -> None:

        self.write_manifest()

        for resource in self.config['resources']:
            if "CurseForge" in resource['downloads']:
                self.add_resource(resource)
            else: self.add_override(resource)

        for override in self.config['overrides']:
            self.add_override(override)

        from json import dump as write_json
        with open(self.temp_dir / "manifest.json", 'w') as file:
            write_json(self.manifest, file)

        with open(self.temp_dir / "modlist.html", 'w') as file:
            self.modlist.insert(0, "<ul>\n")
            self.modlist.append("</ul>\n")
            file.writelines(self.modlist)

        from shutil import make_archive
        make_archive(self.modpack_path / ("CF_" + self.config['name']), 'zip', self.temp_dir, '.')
