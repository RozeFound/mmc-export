from pathlib import Path

from ..Helpers.structures import Writer, Intermediate, Resource, File

class Modrinth(Writer):

    def __init__(self, path: Path, modpack_info: Intermediate) -> None:

        self.index = dict()

        super().__init__(path, modpack_info)

    def add_resource(self, resource: Resource) -> None:
        
        relative_path = Path(resource.file.relativePath) / resource.file.name

        data = {
            "path": relative_path.as_posix(),
            "hashes": resource.file.hash.as_dict(),
            "downloads": [provider.url for _, provider in resource.providers.items()],
            "fileSize": resource.file.path.stat().st_size
        }

        self.index['files'].append(data)

    def add_override(self, file: File) -> None:

        overrides_dir = self.temp_dir / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)

        file_path = overrides_dir / file.relativePath
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file.path, file_path)

    def write(self) -> None:

        match self.modpack_info.modloader.type:
            case "fabric": modloader = "fabric-loader"
            case "quilt": modloader = "quilt-loader"
            case _: modloader = self.modpack_info.modloader.type
        
        self.index = {
            "formatVersion": 1,
            "game": "minecraft",

            "versionId": self.modpack_info.version,
            "name": self.modpack_info.name,
            "summary": self.modpack_info.description,

            "files": [],

            "dependencies": {
                "minecraft": self.modpack_info.minecraft_version,
                modloader: self.modpack_info.modloader.version
            }
        }

        for override in self.modpack_info.overrides:
            self.add_override(override)

        for resource in self.modpack_info.resources:
            self.add_resource(resource)

        from json import dump as write_json
        with open(self.temp_dir / "modrinth.index.json", 'w') as file:
            write_json(self.index, file)

        from shutil import make_archive
        archive_name = make_archive(self.modpack_path / ("MR_" + self.modpack_info.name), 'zip', self.temp_dir, '.')
        Path(archive_name).rename(archive_name.replace("zip", "mrpack"))