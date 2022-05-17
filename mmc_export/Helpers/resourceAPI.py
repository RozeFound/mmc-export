import pickle
import asyncio
import tenacity as tn
from pathlib import Path
from zipfile import ZipFile
from aiohttp import ClientSession
from json import loads as parse_json

from .utils import get_hash
from .structures import Intermediate, Resource

class ResourceAPI(object):

    modrinth_search_type: str
    excluded_providers: list[str]
    ignore_CF_flag: bool

    def __init__(self, session: ClientSession, modpack_info: Intermediate) -> None:

        self.session = session
        self.modpack_info = modpack_info

        # Not secure but not plain text either, just a compromise.

        token = b'gAAAAABifAIMNFaSNF8epJIDWIv2nSe3zxARkMmViCa1ZCvtwoRqhuB1LYjjJsAstwTvP4dEOSm6Wj0SRDWr3PPwZz5eEBt_1fU8uIaninakGYFNSarEduD6YfoA-rm28qUQHYpVcuae3lj8sYrs_87P6F4s3gBrYg=='
        key = b'ywE5qRot_nuWfLnbEXXcAPKaW10us3YpWEkDXgm9was='
        from cryptography.fernet import Fernet

        self.session.headers["X-Api-Key"] = Fernet(key).decrypt(token).decode()
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["Accept"] = "application/json"

        self.github = "https://api.github.com"
        self.modrinth = "https://api.modrinth.com/v2"
        self.curseforge = "https://api.curseforge.com/v1"

        self.cache_directory = Path().home() / ".cache/mmc-export"
        self.cache_directory.mkdir(parents=True, exist_ok=True)

        super().__init__()
    
    async def get(self, path: Path) -> Resource:

        cache_file = self.cache_directory / get_hash(path, "xxhash")
        if cache_file.exists():
            data = cache_file.read_bytes()
            meta, resource = pickle.loads(data)
        else:
            meta = {"name": path.stem,
                    "id": None,
                    "version": "0.0.0"}

            if path.suffix == ".jar":
                with ZipFile(path) as modArchive:
                    filenames = [Path(file).name for file in modArchive.namelist()]
                    if "fabric.mod.json" in filenames:
                        data = modArchive.read("fabric.mod.json")
                        meta = parse_json(data, strict=False)
                    elif "pack.mcmeta" in filenames:
                        data = modArchive.read("pack.mcmeta")
                        json = parse_json(data, strict=False)
                        meta['name'] = json['pack']['description']
                    

            resource = Resource(meta['name'])
            resource.file.hash.sha1 = get_hash(path, "sha1")
            resource.file.hash.sha256 = get_hash(path, "sha256")
            resource.file.hash.sha512 = get_hash(path, "sha512")
            resource.file.hash.murmur2 = get_hash(path, "murmur2")

            data = pickle.dumps((meta, resource))
            cache_file.write_bytes(data)

        resource.file.path = path
        resource.file.name = path.name
        resource.file.relativePath = path.parent.name

        futures = (
            self._get_curseforge(meta, resource),
            self._get_modrinth(meta, resource),
            self._get_github(meta, resource)
        )

        await asyncio.gather(*futures)
        return resource
    
    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_curseforge(self, meta: dict, resource: Resource) -> None:

        if "cf" in self.excluded_providers: return

        async with self.session.post(f"{self.curseforge}/fingerprints", json={"fingerprints":[resource.file.hash.murmur2]}) as response:
            json = await response.json()
            if matches := json['data']['exactMatches']:
                version_info = matches[0]
            else: return

        async with self.session.get(f"{self.curseforge}/mods/{version_info['id']}") as response:
            if response.status != 200 and response.status != 504: return

            addon_info = await response.json()
            resource.name = addon_info['data']['name']
            if not self.ignore_CF_flag and not addon_info['data']['allowModDistribution']: return

            resource.providers['CurseForge'] = Resource.Provider(
                ID     = version_info['id'],
                fileID = version_info['file']['id'],
                url    = version_info['file']['downloadUrl'],
                slug   = addon_info['data']['slug'] if 'slug' in addon_info['data'] else meta['id'],
                author = addon_info['data']['authors'][0]['name'])

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_incrementing(1, 15, 60))
    async def _get_modrinth_loose(self, meta: dict, resource: Resource) -> None:

        if self.modrinth_search_type == "loose":      
            async with self.session.get(f"{self.modrinth}/search?query={resource.name}") as response: 
                if response.status != 200 and response.status != 504 and response.status != 423: return
                json = await response.json()
                if hits := json['hits']: addon_id = hits[0]['project_id']
                else: return
        elif self.modrinth_search_type == "accurate": addon_id = meta['id']
        else: return

        url = f'{self.modrinth}/project/{addon_id}/version?loaders=["{self.modpack_info.modloader.type}"]&game_versions=["{self.modpack_info.minecraft_version}"]'

        async with self.session.get(url) as response:
            if response.status != 200 and response.status != 504 and response.status != 423: return

            versions_info = await response.json()

            for version_info in versions_info:

                if meta['version'] in version_info['version_number']:

                    resource.providers['Modrinth'] = Resource.Provider(
                        ID     = addon_id,
                        fileID = version_info['id'],
                        url    = version_info['files'][0]['url'],
                        slug   = meta['id'],
                        author = None)

                    return

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_incrementing(1, 15, 60))
    async def _get_modrinth(self, meta: dict, resource: Resource) -> None:

        if "mr" in self.excluded_providers: return

        async with self.session.get(f"{self.modrinth}/version_file/{resource.file.hash.sha1}") as response: 
            if response.status != 200 and response.status != 504 and response.status != 423: 
                if self.modrinth_search_type != "exact":
                    await self._get_modrinth_loose(meta, resource)
                return

            version_info = await response.json()

            resource.providers['Modrinth'] = Resource.Provider(
                    ID     = version_info['project_id'],
                    fileID = version_info['id'],
                    url    = version_info['files'][0]['url'],
                    slug   = meta['id'],
                    author = None)         

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_github(self, meta: dict, resource: Resource) -> None:

        from urllib.parse import urlparse

        if "contact" not in meta or "gh" in self.excluded_providers: return
        for link in meta['contact'].values():
            parsed_link = urlparse(link)

            if parsed_link.netloc == "github.com":
                owner, repo = parsed_link.path[1:].split('/')[:2]
                repo = repo.removesuffix(".git")
                break
        else: return

        async with self.session.get(f"https://api.github.com/repos/{owner}/{repo}/releases") as response:
            if response.status != 200 and response.status != 504: return

            for release in await response.json():
                for asset in release['assets']:
                    if asset['name'] == resource.file.name:
                        url = asset['browser_download_url']
                        author = release['author']['login']
                        break
                else: continue
                break
            else: return

            resource.providers['Other'] = Resource.Provider(
                ID     = None,
                fileID = None,
                url    = url,
                slug   = meta['id'],
                author = author)