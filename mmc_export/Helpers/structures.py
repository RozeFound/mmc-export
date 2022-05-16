from math import fabs
from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

@dataclass
class File:
    
    name: str = None

    @dataclass
    class Hash:
        sha1: str = None
        sha256: str = None
        sha512: str = None
        murmur2: int = None

        def as_dict(self):  
            return {
                "sha1": self.sha1,
                "sha256": self.sha256,
                "sha512": self.sha512,
                "murmur2": self.murmur2
            }

    hash: Hash = field(default_factory=Hash)

    path: Path = None
    relativePath: str = None

@dataclass
class Resource:

    "Represents downloadable item i.e. mod, resourcepack, shaderpack etc."
    
    name: str = None

    @dataclass
    class Provider:
     
        ID: str | int = None
        fileID: str | int = None
        url: str = None

        slug: str = None
        author: str = None
        
    file: File = field(default_factory=File)
    providers: dict[Literal['Modrinth', 'CurseForge', 'Other'], Provider] = field(default_factory=dict)

@dataclass
class Intermediate:

    name: str = None
    author: str = None
    version: str = None
    description: str = None

    @dataclass
    class ModLoader:
        type: str = None
        version: str = None

    minecraft_version: str = None
    modloader: ModLoader = field(default_factory=ModLoader)

    resources: list[Resource] = field(default_factory=list)
    overrides: list[File] = field(default_factory=list)
        

class Format(ABC):

    def __init__(self, path: Path) -> None:

        from tempfile import TemporaryDirectory
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)

        self.modpack_path = path

    def __del__(self) -> None:
        self._temp_dir.cleanup()

class Writer(Format):

    def __init__(self, path: Path, modpack_info: Intermediate) -> None:

        self.modpack_info = modpack_info

        super().__init__(path)

    @abstractmethod
    def write(self) -> None:
        raise NotImplementedError()