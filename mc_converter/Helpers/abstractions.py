from abc import ABC, abstractmethod
from pathlib import Path
from aiohttp import ClientSession

from .resourceAPI import ResourceAPI

class ModpackManager(ABC):

    def __init__(self, path: Path | str, session: ClientSession, config: dict[str]) -> None:

        from tempfile import TemporaryDirectory
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)

        self.modpack_path = Path(path)
        self.session = session
        self.config = config

        self.resource_manager = ResourceAPI(session)

    def __del__(self) -> None:
        self._temp_dir.cleanup()

    async def parse(self) -> None: 
        raise NotImplementedError()

    @abstractmethod
    def write(self) -> None:
        raise NotImplementedError()
