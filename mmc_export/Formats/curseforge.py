from pathlib import Path

from ..Helpers.structures import File, Intermediate, Resource, Writer
from ..Helpers.utils import get_name_from_scheme


class CurseForge(Writer):

    def __init__(self, path: Path, intermediate: Intermediate) -> None:

        self.manifest = dict()
        self.modlist = list()

        super().__init__(path, intermediate)

    def add_resource(self, resource: Resource) -> None:

        if provider := resource.providers.get('CurseForge'):

            data = {
                "projectID": provider.ID,
                "fileID": provider.fileID,
                "required": not resource.optional
            }

            self.manifest['files'].append(data)
            mod_page_url = sorted(set(resource.links))[-1]
            self.modlist.append(f"<li><a href=\"{mod_page_url}\">{resource.name} (by {provider.author})</a></li>\n")

        else: self.add_override(resource.file)

    def add_override(self, file: File) -> None:

        overrides_dir = self.temp_dir / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)

        file_path = overrides_dir / file.relativePath
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file.path, file_path)

    def write_manifest(self) -> None:

        self.manifest = {
            
            "minecraft": {
                "version": self.intermediate.minecraft_version,
                "modLoaders": [
                    {
                    "id": f"{self.intermediate.modloader.type}-{self.intermediate.modloader.version}",
                    "primary": True
                    }
                ]
            },
            "manifestType": "minecraftModpack",
            "manifestVersion": 1,
            "name": self.intermediate.name,
            "version": self.intermediate.version,
            "author": self.intermediate.author,

            "files": [],
            "overrides": "overrides"
        }


    def write(self) -> None:

        self.write_manifest()

        for resource in self.intermediate.resources:
            self.add_resource(resource)

        for override in self.intermediate.overrides:
            self.add_override(override)

        from json import dump as write_json
        with open(self.temp_dir / "manifest.json", 'w') as file:
            write_json(self.manifest, file, indent=4)

        with open(self.temp_dir / "modlist.html", 'w') as file:
            self.modlist.insert(0, "<ul>\n")
            self.modlist.append("</ul>\n")
            file.writelines(self.modlist)

        from shutil import make_archive
        name = get_name_from_scheme("CF", "CurseForge", self.intermediate)
        make_archive((self.modpack_path / name).as_posix(), 'zip', self.temp_dir, '.')
