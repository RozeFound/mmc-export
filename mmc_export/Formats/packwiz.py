from contextlib import suppress
from pathlib import Path

from tomli_w import dump as write_toml
from tomli_w import dumps as encode_toml

from ..Helpers.structures import File, Intermediate, Resource, Writer
from ..Helpers.utils import get_hash, get_name_from_scheme
from .. import config


class packwiz(Writer):

    def __init__(self, path: Path, intermediate: Intermediate) -> None:

        self.pack_info = dict()

        self.index = {
            "hash-format": "sha256",
            "files": []
        }

        super().__init__(path, intermediate)

    def add_resource(self, resource: Resource) -> None:

        if not resource.providers: return self.add_override(resource.file)
    
        data = {
            "name": resource.name,
            "filename": resource.file.name,
            "side": "both",

            "download": {},
            "update": {}
        }

        slug = None

        for prior in config.providers_priority:  

            if prior == "CurseForge" and (provider := resource.providers.get("CurseForge")):

                slug = provider.slug
                
                data['update']['curseforge'] = {
                    "file-id": provider.fileID,
                    "project-id": provider.ID,
                    "release-channel": "beta"
                }

                data['download'] = {
                    "hash-format": "sha1",
                    "hash": resource.file.hash.sha1,
                    "mode": "metadata:curseforge"
                }

                break

            if  prior == "Modrinth" and (provider := resource.providers.get("Modrinth")):

                slug = provider.slug

                data['update']['modrinth'] = {
                    "mod-id": provider.ID,
                    "version": provider.fileID
                }

                data['download'] = {
                    "url": provider.url,
                    "hash-format": "sha512",
                    "hash": resource.file.hash.sha512
                }

                break

            if prior == "Other" and (provider := resource.providers.get("Other")):

                slug = provider.slug

                data['download'] = {
                    "url": provider.url,
                    "hash-format": "sha256",
                    "hash": resource.file.hash.sha256
                }

                break

        if resource.optional: data['option'] = {"optional": True}

        from werkzeug.utils import secure_filename
        if not slug: slug = secure_filename(resource.name)

        toml_path = self.temp_dir / resource.file.relativePath / (slug + ".pw.toml")
        toml_path.parent.mkdir(parents=True, exist_ok=True)

        with open(toml_path, "w", encoding="utf-8") as file:

            if not data['update']: del data['update']
            toml_data = encode_toml(data)

            with suppress(ValueError):
                index = toml_data.index("[update")
                toml_data = toml_data[:index] + "[update]\n" + toml_data[index:]

            file.write(toml_data)

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
            "file": Path(file.relativePath).joinpath(file.name).as_posix(),
            "hash": file.hash.sha256
        }
        
        self.index['files'].append(data)

    def write(self) -> None:

        for override in self.intermediate.overrides:
            self.add_override(override)

        for resource in self.intermediate.resources:
            self.add_resource(resource)

        index_path = self.temp_dir / "index.toml"
        with open(index_path, "wb") as file:
            write_toml(self.index, file)

        self.pack_info = {
            "name": self.intermediate.name,
            "author": self.intermediate.author,
            "version": self.intermediate.version,
            "pack-format": "packwiz:1.1.0",

            "index": {
                "file": "index.toml",
                "hash-format": "sha256",
                "hash": get_hash(index_path)
            },

            "versions": {
                self.intermediate.modloader.type: self.intermediate.modloader.version,
                "minecraft": self.intermediate.minecraft_version
            }
        }

        with open(self.temp_dir / "pack.toml", "wb") as file:
            write_toml(self.pack_info, file)

        from shutil import make_archive
        name = get_name_from_scheme("PW", "Packwiz", self.intermediate)
        make_archive((self.modpack_path / name).as_posix(), 'zip', self.temp_dir, '.')
