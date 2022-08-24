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
        sha256: str = field(default_factory=str)
        sha512: str = field(default_factory=str)
        murmur2: str = field(default_factory=str)

    hash: Hash = field(default_factory=Hash)
    size: int = field(default_factory=int)

    path: Path = field(default_factory=Path)
    relativePath: str = field(default_factory=str)


@dataclass
class Resource:

    "Represents downloadable item i.e. mod, resourcepack, shaderpack etc."

    name: str = field(default_factory=str)
    links: list[str] = field(default_factory=list)
    optional: bool = False

    @dataclass
    class Provider:

        ID: str | int | None = None
        fileID: str | int | None = None
        url: str = field(default_factory=str)

        slug: str = field(default_factory=str)
        author: str = field(default_factory=str)

    file: File = field(default_factory=File)
    providers: dict[Literal["Modrinth", "CurseForge", "Other"], Provider] = field(default_factory=dict)


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
