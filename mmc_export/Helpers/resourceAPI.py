import pickle
import asyncio
import re
import tenacity as tn
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import urlparse
from aiohttp import ClientSession
from collections import namedtuple
from json import loads as parse_json

from .utils import delete_github_token, get_hash, get_github_token
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

        meta, resource = self._get_raw_info(path)

        futures = (
            self._get_curseforge(meta, resource),
            self._get_modrinth(meta, resource),
            self._get_github(meta, resource)
        )

        await asyncio.gather(*futures)
        return resource

    def _get_raw_info(self, path: Path) -> tuple[dict, Resource]:

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
            file_data = path.read_bytes()
            resource.file.hash.sha1 = get_hash(file_data, "sha1")
            resource.file.hash.sha256 = get_hash(file_data, "sha256")
            resource.file.hash.sha512 = get_hash(file_data, "sha512")
            resource.file.hash.murmur2 = get_hash(file_data, "murmur2")

            data = pickle.dumps((meta, resource))
            cache_file.write_bytes(data)

        resource.file.path = path
        resource.file.name = path.name
        resource.file.relativePath = path.parent.name

        return meta, resource
    
    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_curseforge(self, meta: dict, resource: Resource) -> None:

        if "CurseForge" in self.excluded_providers: return

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
    async def _get_modrinth(self, meta: dict, resource: Resource) -> None:

        if "Modrinth" in self.excluded_providers: return

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

        placeholder = f'{self.modrinth}/project/{addon_id}/version?loaders=["{{}}"]&game_versions=["{{}}"]'
        url = placeholder.format(self.modpack_info.modloader.type, self.modpack_info.minecraft_version)

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

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_github(self, meta: dict, resource: Resource) -> None:

        if "contact" not in meta or "GitHub" in self.excluded_providers: return
        
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


class ResourceAPI_Batched(ResourceAPI):

    def __init__(self, session: ClientSession, modpack_info: Intermediate) -> None:

        self.queue: list[tuple[dict, Resource]] = list()

        super().__init__(session, modpack_info)

    def queue_resource(self, path: Path) -> None:

        meta, resource = self._get_raw_info(path)
        self.queue.append((meta, resource))

    async def gather(self) -> list[Resource]:

        futures = (
            self._get_curseforge(),
            self._get_modrinth(),
            self._get_github()
        )

        await asyncio.gather(*futures)
        resources = [resource for _, resource in self.queue]
        return resources

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_curseforge(self) -> None:

        if "CurseForge" in self.excluded_providers: return

        payload = {"fingerprints":[resource.file.hash.murmur2 for _, resource in self.queue]}
        async with self.session.post(f"{self.curseforge}/fingerprints", json=payload) as response:
            if response.status != 200 and response.status != 504: return
            if matches := (await response.json())['data']['exactMatches']:
                versions = {str(version['file']['fileFingerprint']): version for version in matches}
            else: return

        payload = {"modIds": [version['id'] for version in versions.values()]}
        async with self.session.post(f"{self.curseforge}/mods", json=payload) as response:
            if response.status != 200 and response.status != 504: return
            if addons_array := (await response.json())['data']:
                addons = {addon['id']: addon for addon in addons_array}
            else: return

        for meta, resource in self.queue:
            if version := versions.get(resource.file.hash.murmur2):
                if addon := addons.get(version['id']):

                    resource.name = addon['name']
                    if not self.ignore_CF_flag and not addon['allowModDistribution']: continue

                    resource.providers['CurseForge'] = Resource.Provider(
                        ID     = addon['id'],
                        fileID = version['file']['id'],
                        url    = version['file']['downloadUrl'],
                        slug   = addon['slug'] if 'slug' in addon else meta['id'],
                        author = addon['authors'][0]['name'])

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_modrinth(self) -> None:

        if "Modrinth" in self.excluded_providers: return
        search_queue: list[tuple[dict, Resource]] = list()

        payload = {"algorithm": "sha1", "hashes": [resource.file.hash.sha1 for _, resource in self.queue]}
        async with self.session.post(f"{self.modrinth}/version_files", json=payload) as response:
            if response.status != 200 and response.status != 504 and response.status != 423: return
            versions = {v[1]['files'][0]['hashes']["sha1"]: v[1] for v in await response.json()}

            for meta, resource in self.queue:
                if version := versions.get(resource.file.hash.sha1):

                    resource.providers['Modrinth'] = Resource.Provider(
                    ID     = version['project_id'],
                    fileID = version['id'],
                    url    = version['files'][0]['url'],
                    slug   = meta['id'],
                    author = None)
                else: search_queue.append((meta, resource))

        if self.modrinth_search_type != "exact": await self._get_modrinth_loose(search_queue)

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_modrinth_loose(self, search_queue: list[tuple[dict, Resource]]) -> None:

        version_ids: list[str] = list()
        
        @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_incrementing(1, 15, 60))
        async def get_project_id(meta: dict, resource: Resource) -> str:
            if self.modrinth_search_type == "loose":      
                async with self.session.get(f"{self.modrinth}/search?query={resource.name}") as response: 
                    if response.status != 200 and response.status != 504 and response.status != 423: return
                    if hits := (await response.json())['hits']: return hits[0]['project_id']
            return meta['id']

        futures = (get_project_id(meta, resource) for meta, resource in search_queue)
        project_ids = await asyncio.gather(*futures)
        if not project_ids: return

        l2s = lambda l: "[{}]".format(",".join(map('"{}"'.format, l))) # list to string convesion
        async with self.session.get(f"{self.modrinth}/projects?ids={l2s(project_ids)}") as response:
            if response.status != 200 and response.status != 504 and response.status != 423: return
            for project in await response.json(): version_ids.extend(project['versions'])

        if not version_ids: return

        async with self.session.get(f"{self.modrinth}/versions?ids={l2s(version_ids)}") as response:
            if response.status != 200 and response.status != 504 and response.status != 423: return
            versions = await response.json()
            for meta, resource in search_queue:
                for version_info in versions:

                    if meta['version'] in version_info['version_number'] \
                        and self.modpack_info.minecraft_version in version_info['game_versions'] \
                        and self.modpack_info.modloader.type in version_info['loaders']:

                        resource.providers['Modrinth'] = Resource.Provider(
                            ID     = version_info['project_id'],
                            fileID = version_info['id'],
                            url    = version_info['files'][0]['url'],
                            slug   = meta['id'],
                            author = None)

                        break

    @tn.retry(stop=tn.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_github(self) -> None:

        if "GitHub" in self.excluded_providers: return
        
        if not self.session.headers.get('Authorization'):
            if token := await get_github_token(self.session):
                self.session.headers['Authorization'] = f"Bearer {token}"
            else: 
                futures = [super()._get_github(meta, resource) for meta, resource in self.queue]
                await asyncio.gather(*futures)
                return

        Repository = namedtuple('Repository', ['name', 'owner', 'alias'])
        repositories: list[Repository] = list()

        for meta, _ in self.queue:
            if "contact" not in meta: continue
            for link in meta['contact'].values():
                parsed_link = urlparse(link)

                if parsed_link.netloc == "github.com":
                    alias = re.sub('[\W_]+', '', meta['id'])
                    owner, name = parsed_link.path[1:].split('/')[:2]
                    repo = Repository(name.removesuffix(".git"), owner, alias)
                    repositories.append(repo)
                    break
            else: continue

        from gql_query_builder import GqlQuery
        queries: list[str] = list()
        
        for repo in repositories:
            query = GqlQuery() \
                .fields(['...repoReleaseAssets']) \
                .query('repository', alias=repo.alias, input={"name": f'"{repo.name}"', "owner": f'"{repo.owner}"'}) \
                .generate()
            queries.append(query)

        payload = """
        fragment repoReleaseAssets on Repository {
            releases(last: 100) { edges { node {
                releaseAssets(last: 10) { nodes {
                    name
                    downloadUrl
        } } } } } } """ + GqlQuery().operation(queries=queries).generate()

        async with self.session.post(f"{self.github}/graphql", json={"query": payload}) as response:
            if response.status == 401: delete_github_token()
            if response.status != 200 and response.status != 504: return
            data = (await response.json())['data']      

            for meta, resource in self.queue:
                if not data.get(alias := re.sub('[\W_]+', '', meta['id']) if meta['id'] else "unknown"): continue
                for release in data.get(alias, {}).get('releases', {}).get('edges', []):
                    for asset in release.get('node', {}).get('releaseAssets', {}).get('nodes', []):
                        if asset['name'] == resource.file.name: url = asset['downloadUrl']; break
                    else: continue
                    break
                else: continue

                resource.providers['Other'] = Resource.Provider(
                    ID     = None,
                    fileID = None,
                    url    = url,
                    slug   = meta['id'],
                    author = None)