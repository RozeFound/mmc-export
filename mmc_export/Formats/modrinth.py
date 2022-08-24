from pathlib import Path

from ..Helpers.structures import File, Intermediate, Resource, Writer
from ..Helpers.utils import get_name_from_scheme


class Modrinth(Writer):

    def __init__(self, path: Path, intermediate: Intermediate) -> None:

        self.index = dict()

        super().__init__(path, intermediate)

    def add_resource(self, resource: Resource) -> None:
        
        relative_path = Path(resource.file.relativePath) / resource.file.name

        data = {
            "path": relative_path.as_posix(),
            "hashes": {"sha1": resource.file.hash.sha1, "sha512": resource.file.hash.sha512},
            "downloads": sorted(provider.url for provider in resource.providers.values()),
            "fileSize": resource.file.size
        }

        if resource.optional: data['env'] = {"client": "optional", "server": "optional"}

        self.index['files'].append(data)

    def add_override(self, file: File) -> None:

        overrides_dir = self.temp_dir / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)

        file_path = overrides_dir / file.relativePath
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file.path, file_path)

    def write_index(self) -> None:
        
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

    def print_bundled(self, bundled_files: list[Resource]) -> None: 

        gh_links = []
        other_links = []

        for resource in bundled_files:

            if resource.links:
                link = sorted(set(resource.links), reverse=True)[-1]
                md_link = f"* [{resource.name}]({link})"
            else: md_link = f"* {resource.name} (link unknown)"; link = ""

            if link.startswith("https://github.com"): 
                gh_links.append(md_link)
            else: other_links.append(md_link)

        newline = '\n'
        message = "Sources for bundled mods:\n\n"
        if gh_links: message +=f"GitHub links\n{newline.join(gh_links)}\n"
        if other_links: message +=f"\nOther links\n{newline.join(other_links)}\n"

        message +="\nAlways check the licenses to see if they allow distribution!"

        md_file = self.modpack_path / "bundled_links.md"
        if gh_links or other_links: md_file.write_text(message)

    def write(self) -> None:

        self.write_index()

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

        self.print_bundled(bundled_files)

        from json import dump as write_json
        with open(self.temp_dir / "modrinth.index.json", 'w') as file:
            write_json(self.index, file, indent=4)

        from shutil import make_archive
        name = get_name_from_scheme("MR", "Modrinth", self.intermediate)
        archive = Path(make_archive((self.modpack_path / name).as_posix(), 'zip', self.temp_dir, '.'))
        archive.replace(archive.with_suffix(".mrpack"))
