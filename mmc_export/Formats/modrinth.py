from pathlib import Path

from ..Helpers.structures import File, Intermediate, Resource, Writer


class Modrinth(Writer):

    def __init__(self, path: Path, intermediate: Intermediate) -> None:

        self.index = dict()

        super().__init__(path, intermediate)

    def add_resource(self, resource: Resource) -> None:
        
        relative_path = Path(resource.file.relativePath) / resource.file.name

        data = {
            "path": relative_path.as_posix(),
            "hashes": {"sha1": resource.file.hash.sha1, "sha512": resource.file.hash.sha512},
            "downloads": sorted([provider.url for provider in resource.providers.values()]),
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

        match self.intermediate.modloader.type:
            case "fabric": modloader = "fabric-loader"
            case "quilt": modloader = "quilt-loader"
            case _: modloader = self.intermediate.modloader.type
        
        self.index = {
            "formatVersion": 1,
            "game": "minecraft",

            "versionId": self.intermediate.version,
            "name": self.intermediate.name,
            "summary": self.intermediate.description,

            "files": [],

            "dependencies": {
                "minecraft": self.intermediate.minecraft_version,
                modloader: self.intermediate.modloader.version
            }
        }

        for override in self.intermediate.overrides:
            self.add_override(override)

        bundled_files: list[Resource] = list()
        from copy import deepcopy as copy_object

        for resource in self.intermediate.resources:
            resource_copy = copy_object(resource)
            resource_copy.providers.pop('CurseForge', None)

            if not resource_copy.providers:
                self.add_override(resource.file)
                bundled_files.append(resource)
            else: self.add_resource(resource_copy)

        print("Sources for bundled mods:\n")
        for res in [res for res in bundled_files if res.links]:
            link = sorted(res.links, reverse=True)[-1]
            print(f"* [{res.name}]({link})")

        no_links = [res.name for res in bundled_files if not res.links]
        if no_links: print("\n"); print(f"Links for {','.join(no_links)} was not found")

        from json import dump as write_json
        with open(self.temp_dir / "modrinth.index.json", 'w') as file:
            write_json(self.index, file)

        from shutil import make_archive
        base = self.modpack_path / ("MR_" + self.intermediate.name)
        archive = Path(make_archive(base.as_posix(), 'zip', self.temp_dir, '.'))
        archive.replace(archive.with_suffix(".mrpack"))
