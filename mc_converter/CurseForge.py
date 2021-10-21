from pathlib import Path
from aiohttp import ClientSession
from .Helpers.abstractions import ModpackManager

class CurseForgeManager(ModpackManager):

    def __init__(self, path: Path | str, session: ClientSession, config: dict[str]) -> None:

        self.manifest = dict()
        self.modlist = list()

        super().__init__(path, session, config)

    def get_resource(self, resource: dict[str]):
        return super().get_resource(resource)

    def get_override(self, file: dict[str]):
        return super().get_override(file)

    def parse(self) -> None:
        return super().parse()

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

    def add_resource(self, resource: dict[str]):

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
