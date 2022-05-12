import asyncio
from pathlib import Path
from aiohttp import ClientSession
from json import loads as parse_json
from configparser import ConfigParser

from .Helpers.structures import Intermediate, Format, File
from .Helpers.resourceAPI import ResourceAPI
from .Helpers.utils import get_hash

class Parser(Format):

    def __init__(self, path: Path, session: ClientSession) -> None:

        self.intermediate = Intermediate()
        self.resourceAPI = ResourceAPI(session, self.intermediate)

        super().__init__(path)

    def get_basic_info(self):

        data = next(self.temp_dir.glob("**/instance.cfg")).read_text()

        cfg = ConfigParser()
        cfg.read_string("[dummy_section]\n" + data)

        if "name" in cfg['dummy_section']: self.intermediate.name = cfg['dummy_section']['name']

        bdata = next(self.temp_dir.glob("**/mmc-pack.json")).read_bytes()
        pack_info = parse_json(bdata)        

        for component in pack_info['components']:

            match component:

                case {'cachedName': "Minecraft", 'version': version}: 
                    self.intermediate.minecraft_version = version
                case {'cachedName': "Fabric Loader", 'version': version}: 
                    self.intermediate.modloader.type = "fabric"
                    self.intermediate.modloader.version = version
                case {'cachedName': "Quilt Loader", 'version': version}: 
                    self.intermediate.modloader.type = "quilt"
                    self.intermediate.modloader.version = version
                case {'cachedName': "Forge", 'version': version}: 
                    self.intermediate.modloader.type = "forge"
                    self.intermediate.modloader.version = version

    async def get_resource(self, path: Path):

        resource = await self.resourceAPI.get(path)
        self.intermediate.resources.append(resource)

    def get_override(self, path: Path):

        if "minecraft" not in path.parts: return
        root_dir_id = path.parts.index("minecraft")
        relative_path = path.relative_to(*path.parts[:root_dir_id + 1]).parent

        file = File(
            name = path.name,
            hash = File.Hash(sha256=get_hash(path)),
            path = path.as_posix(),
            relativePath = relative_path)
        
        self.intermediate.overrides.append(file)

    async def parse(self) -> Intermediate:
        
        downloadable_content = ("resourcepacks", "shaderpacks", "mods")

        from shutil import unpack_archive        
        unpack_archive(self.modpack_path, self.temp_dir)
        self.get_basic_info()

        futures = list()
        overrides = list()

        for file in [file for file in self.temp_dir.glob("**/*") if file.is_file()]:
            if file.parent.name in downloadable_content and file.suffix != ".txt": 
                future = self.get_resource(file)
                futures.append(future)
            else: overrides.append(file)

        await asyncio.gather(*futures)
        for override in overrides:
            self.get_override(override)

        return self.intermediate