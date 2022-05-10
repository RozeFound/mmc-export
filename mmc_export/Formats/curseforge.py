from pathlib import Path

from ..Helpers.structures import Writer, Intermediate, Resource, File

class CurseForge(Writer):

    def __init__(self, path: Path, modpack_info: Intermediate) -> None:

        self.manifest = dict()
        self.modlist = list()

        super().__init__(path, modpack_info)

    def add_resource(self, resource: Resource) -> None:

        provider = resource.providers['CurseForge']

        data = {
            "projectID": provider.ID,
            "fileID": provider.fileID,
            "required": True
        }

        self.manifest['files'].append(data)
        mod_page_url = "https://www.curseforge.com/minecraft/mc-mods/" + provider.slug
        self.modlist.append(f"<li><a href=\"{mod_page_url}\">{resource.name} (by {provider.author})</a></li>\n")

    def add_override(self, file: File) -> None:

        overrides_dir = self.temp_dir / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)

        file_path = overrides_dir / file.relativePath
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file.path, file_path)

    def write(self) -> None:

        self.manifest = {
            
            "minecraft": {
                "version": self.modpack_info.minecraft_version,
                "modLoaders": [
                    {
                    "id": f"{self.modpack_info.modloader.type}-{self.modpack_info.modloader.version}",
                    "primary": True
                    }
                ]
            },
            "manifestType": "minecraftModpack",
            "manifestVersion": 1,
            "name": self.modpack_info.name,
            "version": self.modpack_info.version,
            "author": self.modpack_info.author,

            "files": [],
            "overrides": "overrides"
        }

        for resource in self.modpack_info.resources:
            if "CurseForge" in resource.providers:
                self.add_resource(resource)
            else: self.add_override(resource.file)

        for override in self.modpack_info.overrides:
            self.add_override(override)

        from json import dump as write_json
        with open(self.temp_dir / "manifest.json", 'w') as file:
            write_json(self.manifest, file)

        with open(self.temp_dir / "modlist.html", 'w') as file:
            self.modlist.insert(0, "<ul>\n")
            self.modlist.append("</ul>\n")
            file.writelines(self.modlist)

        from shutil import make_archive
        make_archive(self.modpack_path / ("CF_" + self.modpack_info.name), 'zip', self.temp_dir, '.')