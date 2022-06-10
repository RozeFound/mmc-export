from configparser import ConfigParser
from json import loads as parse_json
from pathlib import Path

from aiohttp_client_cache.session import CachedSession

from .Helpers.resourceAPI import ResourceAPI_Batched
from .Helpers.structures import File, Format, Intermediate
from .Helpers.utils import get_hash


class Parser(Format):

    def __init__(self, path: Path, session: CachedSession) -> None:

        self.intermediate = Intermediate()
        self.resourceAPI = ResourceAPI_Batched(session, self.intermediate)

        super().__init__(path)

    def get_basic_info(self):

        data = next(self.temp_dir.glob("**/instance.cfg")).read_text()

        cfg = ConfigParser()
        cfg.read_string("[dummy_section]\n" + data)
        if name := cfg['dummy_section'].get('name'):
            self.intermediate.name = name

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

    def get_override(self, path: Path):

        if "minecraft" not in path.parts: return
        root_dir_id = path.parts.index("minecraft")
        relative_path = path.relative_to(*path.parts[:root_dir_id + 1]).parent

        file = File(
            name = path.name,
            hash = File.Hash(sha256=get_hash(path)),
            path = path,
            relativePath = relative_path.as_posix())
        
        self.intermediate.overrides.append(file)

    async def parse(self) -> Intermediate:
        
        downloadable_content = ("resourcepacks", "shaderpacks", "mods")

        from shutil import unpack_archive        
        unpack_archive(self.modpack_path, self.temp_dir)
        self.get_basic_info()

        overrides = list()

        for file in [file for file in self.temp_dir.glob("**/*") if file.is_file()]:
            if file.parent.name in downloadable_content and file.suffix != ".txt": 
                self.resourceAPI.queue_resource(file)
            else: overrides.append(file)

        self.intermediate.resources = await self.resourceAPI.gather()

        for override in overrides:
            self.get_override(override)

        return self.intermediate
