import asyncio
import tenacity as tn
from pathlib import Path
from zipfile import ZipFile
from aiohttp import ClientSession
from json import loads as parse_json

from .structures import Intermediate, Resource

class ResourceAPI(object):

    modrinth_search_type: str

    def __init__(self, session: ClientSession, modpack_info: Intermediate) -> None:

        self.session = session
        self.modpack_info = modpack_info

        self.session.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) Gecko/20100101 Firefox/42.0"
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Content-Type"] = "application/json"

        self.github = "https://api.github.com"
        self.modrinth = "https://api.modrinth.com/v2"
        self.curseforge = "https://addons-ecs.forgesvc.net/api/v2"

        self.github_exeeded_rate_limit = False

        super().__init__()
    
    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def get(self, path: Path) -> Resource:

        try:
            with ZipFile(path) as modArchive:
                data = modArchive.read("fabric.mod.json")
                meta = parse_json(data, strict=False)
        except KeyError:
            meta = {
                "name": path.stem,
                "id": "unknown",
                "version": "0.0.0"
            }

        resource = Resource(meta['name'])
        resource.file.path = path
        resource.file.name = path.name
        resource.file.relativePath = path.parent.name
        resource.side = Resource.Side("both", "optional", "optional")

        from .utils import get_hash

        resource.file.hash.sha1 = get_hash(path, "sha1")
        resource.file.hash.sha256 = get_hash(path, "sha256")
        resource.file.hash.sha512 = get_hash(path, "sha512")
        resource.file.hash.murmur2 = get_hash(path, "murmur2")

        futures = (
            self._get_curseforge(meta, resource),
            self._get_modrinth(meta, resource),
            self._get_github(meta, resource)
        )

        await asyncio.gather(*futures)
        return resource

    async def _get_curseforge(self, meta: dict, resource: Resource) -> None:

        async with self.session.post(f"{self.curseforge}/fingerprint", data = f"[{resource.file.hash.murmur2}]") as response:
            json = await response.json()
            if matches := json['exactMatches']:
                version_info = matches[0]
            else: return

        async with self.session.get(f"{self.curseforge}/addon/{version_info['id']}") as response:

            addon_info = await response.json()

            resource.name = addon_info['name']

            resource.providers['CurseForge'] = Resource.Provider(
                ID     = version_info['id'],
                fileID = version_info['file']['id'],
                url    = version_info['file']['downloadUrl'],
                slug   = addon_info['slug'] if 'slug' in addon_info else meta['id'],
                author = addon_info['authors'][0]['name'])

    async def _get_modrinth_loose(self, meta: dict, resource: Resource) -> None:

        if self.modrinth_search_type == "loose":      
            async with self.session.get(f"{self.modrinth}/search?query={resource.name}") as response: 
                if response.status != 200 and response.status != 504: return
                json = await response.json()
                if hits := json['hits']: addon_id = hits[0]['project_id']
                else: return
        elif self.modrinth_search_type == "accurate": addon_id = meta['id']
        else: return

        async with self.session.get(f"{self.modrinth}/project/{addon_id}") as response: 
            if response.status != 200 and response.status != 504: return

            addon_info = await response.json()

            resource.name = addon_info['title']

            resource.side.client = addon_info['client_side']
            resource.side.server = addon_info['server_side']

            if resource.side.client == "required": resource.side.summary = "client"
            elif resource.side.server == "required": resource.side.summary = "server"

            url = f'{self.modrinth}/project/{addon_id}/version?loaders=["{self.modpack_info.modloader.type}"]&game_versions=["{self.modpack_info.minecraft_version}"]'

            async with self.session.get(url) as response:

                versions_info = await response.json()

                for version_info in versions_info:

                    if meta['version'] in version_info['version_number']:

                        resource.providers['Modrinth'] = Resource.Provider(
                            ID     = addon_id,
                            fileID = version_info['id'],
                            url    = version_info['files'][0]['url'],
                            slug   = addon_info['slug'] if 'slug' in addon_info else meta['id'],
                            author = None)

                        return

    async def _get_modrinth(self, meta: dict, resource: Resource) -> None:

        modrinth_links = (
            f"{self.modrinth}/version_file/{resource.file.hash.sha512}?algorithm=sha512",
            f"{self.modrinth}/version_file/{resource.file.hash.sha1}?algorithm=sha1"
        )
        
        for url in modrinth_links:
            async with self.session.get(url) as response:
                if response.status == 200 or response.status == 504:
                    version_info = await response.json()
                    break
        else: 
            if self.modrinth_search_type != "exact": await self._get_modrinth_loose(meta, resource)
            return

        async with self.session.get(f"{self.modrinth}/project/{version_info['project_id']}") as response:       

            addon_info = await response.json()

            resource.name = addon_info['title']

            resource.side.client = addon_info['client_side']
            resource.side.server = addon_info['server_side']

            if resource.side.client == "required": resource.side.summary = "client"
            elif resource.side.server == "required": resource.side.summary = "server"

            resource.providers['Modrinth'] = Resource.Provider(
                ID     = version_info['project_id'],
                fileID = version_info['id'],
                url    = version_info['files'][0]['url'],
                slug   = addon_info['slug'] if 'slug' in addon_info else meta['id'],
                author = None)

    async def _get_github(self, meta: dict, resource: Resource) -> None:

        from urllib.parse import urlparse

        if "contact" not in meta or self.github_exeeded_rate_limit: return
        for link in meta['contact'].values():
            parsed_link = urlparse(link)

            if parsed_link.netloc == "github.com":
                owner, repo = parsed_link.path[1:].split('/')[:2]
                repo = repo.removesuffix(".git")
                break
        else: return

        async with self.session.get(f"https://api.github.com/repos/{owner}/{repo}/releases") as response:

            if response.status != 200:
                if int(response.headers.get("X-RateLimit-Remaining")) <= 0:
                    print("You exeeded github rate limit, authorize or try again in an hour.")
                    self.github_exeeded_rate_limit = True
                return

            for release in await response.json():
                for asset in release['assets']:
                    if asset['name'] == resource.file.name:
                        url = asset['browser_download_url']
                        author = release['author']['login']
                        break
                else: continue
                break
            else: return

            resource.providers['Github'] = Resource.Provider(
                ID     = None,
                fileID = None,
                url    = url,
                slug   = meta['id'],
                author = author)