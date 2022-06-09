from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class File:
    
    name: str = field(default_factory=str)

    @dataclass
    class Hash:
        sha1: str = field(default_factory=str)
        sha256: str= field(default_factory=str)
        sha512: str = field(default_factory=str)
        murmur2: str = field(default_factory=str)

    hash: Hash = field(default_factory=Hash)

    path: Path = field(default_factory=Path)
    relativePath: str = field(default_factory=str)

    def to_dict(self):

        data = self.__dict__.copy()
        data['hash'] = self.hash.__dict__
        data['path'] = self.path.as_posix()

        return data


@dataclass
class Resource:

    "Represents downloadable item i.e. mod, resourcepack, shaderpack etc."
    
    name: str = field(default_factory=str)
    links: list[str] = field(default_factory=list)

    @dataclass
    class Provider:
     
        ID: str | int | None = None
        fileID: str | int | None = None
        url: str = field(default_factory=str)

        slug: str = field(default_factory=str)
        author: str = field(default_factory=str)

    file: File = field(default_factory=File)
    providers: dict[Literal['Modrinth', 'CurseForge', 'Other'], Provider] = field(default_factory=dict)

    def to_dict(self):

        data = self.__dict__.copy()
        data['file'] = self.file.to_dict()
        data['providers'] = {name: data.__dict__ for name, data in self.providers.items()}

        return data


@dataclass
class Intermediate:

    name: str = field(default_factory=str)
    author: str = field(default_factory=str)
    version: str = field(default_factory=str)
    description: str = field(default_factory=str)

    @dataclass
    class ModLoader:
        type: str = field(default_factory=str)
        version: str = field(default_factory=str)

    minecraft_version: str = field(default_factory=str)
    modloader: ModLoader = field(default_factory=ModLoader)

    resources: list[Resource] = field(default_factory=list)
    overrides: list[File] = field(default_factory=list)

    def to_dict(self):

        def clean(value):
            if isinstance(value, list): return [clean(x) for x in value if x]
            elif isinstance(value, dict): return {key: clean(val) for key, val in value.items() if val}
            else: return value

        data = self.__dict__.copy()
        data['modloader'] = self.modloader.__dict__
        data['resources'] = [resource.to_dict() for resource in self.resources]
        data['overrides'] = [override.to_dict() for override in self.overrides]

        return clean(data)     

class Format(ABC):

    def __init__(self, path: Path) -> None:

        from tempfile import TemporaryDirectory
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)

        self.modpack_path = path

    def __del__(self) -> None:
        self._temp_dir.cleanup()


class Writer(Format):

    def __init__(self, path: Path, intermediate: Intermediate) -> None:

        self.intermediate = intermediate

        super().__init__(path)

    @abstractmethod
    def write(self) -> None:
        raise NotImplementedError()
