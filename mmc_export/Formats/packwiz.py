from pathlib import Path
from pytoml import dump as write_toml

from ..Helpers.structures import Writer, Intermediate, Resource, File
from ..Helpers.utils import get_hash

class packwiz(Writer):

    def __init__(self, path: Path, modpack_info: Intermediate) -> None:

        self.pack_info = dict()

        self.index = {
            "hash-format": "sha256",
            "files": []
        }

        super().__init__(path, modpack_info)

    def add_resource(self, resource: Resource) -> None:

        data = {
            "name": resource.name,
            "filename": resource.file.name,

            "update": {}
        }

        for provider_tuple in resource.providers.items():

            match provider_tuple:

                case "CurseForge", provider:

                    slug = provider.slug

                    data['update']['curseforge'] = {
                        "file-id": provider.fileID,
                        "project-id": provider.ID,
                        "release-channel": "beta"
                    }

                    data['download'] = {
                        "url": provider.url,
                        "hash-format": "murmu2",
                        "hash": resource.file.hash.murmur2
                    }

                case "Modrinth", provider: 

                    slug = provider.slug

                    data['update']['modrinth'] = {
                        "mod-id": provider.ID,
                        "version": provider.fileID
                    }

                    if "download" not in data:
                        data['download'] = {
                            "url": provider.url,
                            "hash-format": "sha512",
                            "hash": resource.file.hash.sha512
                        }

                case "Other", provider: 

                    slug = provider.slug

                    if "download" not in data:
                        data['download'] = {
                            "url": provider.url,
                            "hash-format": "sha256",
                            "hash": resource.file.hash.sha256
                        }

        from werkzeug.utils import secure_filename
        if slug is None: slug = secure_filename(resource.name)
        
        toml_path = self.temp_dir / resource.file.relativePath / (slug + ".toml")
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        with open(toml_path, "w") as file:
            write_toml(data, file)

        index_data = {
            "file": toml_path.relative_to(self.temp_dir).as_posix(),
            "hash": get_hash(toml_path),
            "metafile": True
        }
        
        self.index['files'].append(index_data)

    def add_override(self, file: File) -> None:

        file_path = self.temp_dir / file.relativePath
        file_path.mkdir(parents=True, exist_ok=True)

        from shutil import copy2 as copy_file
        copy_file(file.path, file_path)

        data = {
            "file": Path(file.relativePath) / file.name,
            "hash": file.hash.sha256
        }
        
        self.index['files'].append(data)

    def write(self) -> None:

        for override in self.modpack_info.overrides:
            self.add_override(override)

        for resource in self.modpack_info.resources:
            self.add_resource(resource)

        index_path = self.temp_dir / "index.toml"
        with open(index_path, "w") as file:
            write_toml(self.index, file)

        self.pack_info = {
            "name": self.modpack_info.name,
            "author": self.modpack_info.author,
            "version": self.modpack_info.version,

            "index": {
                "file": "index.toml",
                "hash-format": "sha256",
                "hash": get_hash(index_path)
            },

            "versions": {
                self.modpack_info.modloader.type: self.modpack_info.modloader.version,
                "minecraft": self.modpack_info.minecraft_version
            }
        }

        with open(self.temp_dir / "pack.toml", "w") as file:
            write_toml(self.pack_info, file)

        from shutil import make_archive
        make_archive(self.modpack_path / ("PW_" + self.modpack_info.name), 'zip', self.temp_dir, '.')