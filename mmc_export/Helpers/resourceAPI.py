import asyncio
from collections import namedtuple
from datetime import datetime
from json import loads as parse_json
from pathlib import Path
from re import compile as re_compile
from urllib.parse import urlparse
from zipfile import ZipFile

import tenacity as tn
from httpx import AsyncClient

from .structures import Intermediate, Resource
from .utils import delete_github_token, get_github_token, get_hash
from .. import config


class ResourceAPI(object):

    modrinth_search_type: str
    excluded_providers: list[str]

    def __init__(self, http_client: AsyncClient, intermediate: Intermediate) -> None:

        self.client = http_client
        self.intermediate = intermediate

        self.client.headers["User-Agent"] = "RozeFound/mmc-export/2.7.3"
        self.client.headers["X-Api-Key"] = config.CURSEFORGE_API_TOKEN
        self.client.headers["Content-Type"] = "application/json"
        self.client.headers["Accept"] = "application/json"

        self.github = "https://api.github.com"
        self.modrinth = "https://api.modrinth.com/v2"
        self.curseforge = "https://api.curseforge.com/v1"

        self.cache_directory = config.DEFAULT_CACHE_DIR / "v6"
        self.cache_directory.mkdir(parents=True, exist_ok=True)

        super().__init__()

    def _get_raw_info(self, path: Path) -> tuple[dict, Resource]:

        from pickle import HIGHEST_PROTOCOL
        from pickle import dumps as serialize
        from pickle import loads as deserialize

        cache_file = self.cache_directory / get_hash(path, "xxhash")
        if cache_file.exists():
            data = cache_file.read_bytes()
            meta, resource = deserialize(data)
        else:
            meta = {"name": path.stem,
                    "id": None,
                    "version": "0.0.0"}

            if path.suffix in (".jar", ".disabled"):
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

            resource.file.size = path.stat().st_size

            to_cache = meta, resource
            data = serialize(to_cache, HIGHEST_PROTOCOL)
            cache_file.write_bytes(data)

        resource.file.path = path
        resource.file.name = path.name
        resource.file.relativePath = path.parent.name

        return meta, resource
    
    @tn.retry(stop=tn.stop.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_github(self, meta: dict, resource: Resource) -> None:

        if "contact" not in meta or "GitHub" in self.excluded_providers: return
        
        for link in meta['contact'].values():
            parsed_link = urlparse(link)

            if parsed_link.netloc == "github.com":
                owner, repo = parsed_link.path[1:].split('/')[:2]
                repo = repo.removesuffix(".git")
                resource.links.append(f"https://github.com/{owner}/{repo}")
                break
        else: return

        response = await self.client.get(f"https://api.github.com/repos/{owner}/{repo}/releases")
        if response.status_code != 200 and response.status_code != 504: return

        for release in response.json():
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

    def __init__(self, http_client: AsyncClient, intermediate: Intermediate) -> None:

        self.queue: list[tuple[dict, Resource]] = list()

        super().__init__(http_client, intermediate)

    def queue_resource(self, path: Path) -> None:

        meta, resource = self._get_raw_info(path)
        
        if path.suffix == ".disabled": 
            resource.optional = True
            resource.file.path = path.replace(path.with_suffix(''))
            resource.file.name = resource.file.path.name

        self.queue.append((meta, resource))

    async def gather(self) -> list[Resource]:

        futures = (
            self._get_batched_curseforge(),
            self._get_batched_modrinth(),
            self._get_batched_github()
        )

        await asyncio.gather(*futures)
        resources = [resource for _, resource in self.queue]
        return resources

    @tn.retry(stop=tn.stop.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_batched_curseforge(self) -> None:

        if "CurseForge" in self.excluded_providers: return

        payload = {"fingerprints":[resource.file.hash.murmur2 for _, resource in self.queue]}
        response = await self.client.post(f"{self.curseforge}/fingerprints", json=payload)
        if response.status_code != 200 and response.status_code != 504: return
        if matches := response.json()['data']['exactMatches']:
            versions = {str(version['file']['fileFingerprint']): version for version in matches}
        else: return

        payload = {"modIds": [version['id'] for version in versions.values()]}
        response = await self.client.post(f"{self.curseforge}/mods", json=payload)
        if response.status_code != 200 and response.status_code != 504: return
        if addons_array := response.json()['data']:
            addons = {addon['id']: addon for addon in addons_array}
        else: return

        for _, resource in self.queue:
            if version := versions.get(resource.file.hash.murmur2):
                if addon := addons.get(version['id']):

                    resource.name = addon['name']
                    resource.links.append(addon['links']['websiteUrl'])
                    if srcUrl := addon['links']['sourceUrl']:
                        resource.links.append(srcUrl)

                    resource.providers['CurseForge'] = Resource.Provider(
                        ID     = addon['id'],
                        fileID = version['file']['id'],
                        url    = version['file']['downloadUrl'],
                        slug   = addon['slug'],
                        author = addon['authors'][0]['name'])

    @tn.retry(stop=tn.stop.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_batched_modrinth(self) -> None:

        if "Modrinth" in self.excluded_providers: return
        search_queue: list[tuple[dict, Resource]] = list()

        payload = {"algorithm": "sha1", "hashes": [resource.file.hash.sha1 for _, resource in self.queue]}
        response = await self.client.post(f"{self.modrinth}/version_files", json=payload)
        if response.status_code != 200 and response.status_code != 504 and response.status_code != 423: return
        versions = response.json()

        for meta, resource in self.queue:
            if version := versions.get(resource.file.hash.sha1):

                file = next(file for file in version['files'] 
                    if resource.file.hash.sha1 == file['hashes']['sha1']
                    and resource.file.hash.sha512 == file['hashes']['sha512'])

                resource.providers['Modrinth'] = Resource.Provider(
                ID     = version['project_id'],
                fileID = version['id'],
                url    = file['url'],
                slug   = meta['id'])
            else: search_queue.append((meta, resource))

        if self.modrinth_search_type != "exact": await self._get_batched_modrinth_loose(search_queue)

    @tn.retry(stop=tn.stop.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_batched_modrinth_loose(self, search_queue: list[tuple[dict, Resource]]) -> None:

        version_ids: list[str] = list()
        
        @tn.retry(stop=tn.stop.stop_after_attempt(5), wait=tn.wait.wait_incrementing(1, 15, 60))
        async def get_project_id(meta: dict, resource: Resource):
            if self.modrinth_search_type == "loose":      
                response = await self.client.get(f"{self.modrinth}/search?query={resource.name}&limit=1")
                if response.status_code != 200 and response.status_code != 504 and response.status_code != 423: return resource, None
                if hits := response.json()['hits']: return resource, hits[0]['project_id']
            return resource, meta['id']

        futures = (get_project_id(meta, resource) for meta, resource in search_queue)
        project_ids = {resource.name: id for resource, id in await asyncio.gather(*futures) if id}
        if not project_ids: return

        l2s = lambda l: "[{}]".format(",".join(map('"{}"'.format, l))) # list to string convesion
        response = await self.client.get(f"{self.modrinth}/projects?ids={l2s(project_ids.values())}")
        if response.status_code != 200 and response.status_code != 504 and response.status_code != 423: return
        for project in (projects := response.json()): version_ids.extend(project['versions'])

        if not version_ids: return

        response = await self.client.get(f"{self.modrinth}/versions?ids={l2s(version_ids)}")
        if response.status_code != 200 and response.status_code != 504 and response.status_code != 423: return
        for project in projects: project['versions'] = [version for version in response.json()
                                                                if version['project_id'] == project['id']]

        minecraft_major_version = ".".join(self.intermediate.minecraft_version.split(".")[:2])
        minecraft_versions = minecraft_major_version, self.intermediate.minecraft_version

        for meta, resource in search_queue:
            if project := next((project for project in projects 
            if project['id'] == project_ids.get(resource.name, "")), None):
                for version in project['versions']:
                    if meta['version'] in version['version_number'] \
                    and self.intermediate.modloader.type in version['loaders'] \
                    and any(mv in version['game_versions'] for mv in minecraft_versions):

                        file = next(file for file in version['files'] 
                            if file['filename'] == resource.file.name or file['primary'])

                        resource.providers['Modrinth'] = Resource.Provider(
                            ID     = version['project_id'],
                            fileID = version['id'],
                            url    = file['url'],
                            slug   = meta['id'])

                        resource.file.hash.sha1 = file['hashes']['sha1']
                        resource.file.hash.sha512 = file['hashes']['sha512']
                        resource.file.size = file['size']

                        break

    @tn.retry(stop=tn.stop.stop_after_attempt(5), wait=tn.wait.wait_fixed(1))
    async def _get_batched_github(self) -> None:

        if "GitHub" in self.excluded_providers: return
        
        if not self.client.headers.get('Authorization'):
            if token := get_github_token(): self.client.headers['Authorization'] = f"Bearer {token}"
            else: 
                futures = [self._get_github(meta, resource) for meta, resource in self.queue]
                await asyncio.gather(*futures)

            response = await self.client.get("https://api.github.com/rate_limit")
            ratelimit = response.json()['resources']['core']
            time_remaining = datetime.fromtimestamp(float(ratelimit['reset']))
            if ratelimit['remaining'] == 0: 
                print("You have exceeded the GitHub API rate-limit, only cached results will be used.")
                print(f"Please sign in with `mmc-export gh-login` or try again at {time_remaining:%H:%M}")
                return

        Repository = namedtuple('Repository', ['name', 'owner', 'alias'])
        repositories: list[Repository] = list()
        pattern = re_compile(r"[\W_]+")

        for meta, resource in self.queue:
            if "contact" not in meta: continue
            for link in meta['contact'].values():
                parsed_link = urlparse(link)

                if parsed_link.netloc == "github.com":
                    alias = pattern.sub('', meta['id'])
                    owner, name = parsed_link.path[1:].split('/')[:2]
                    repo = Repository(name.removesuffix(".git"), owner, alias)
                    resource.links.append(f"https://github.com/{repo.owner}/{repo.name}")
                    repositories.append(repo)
                    break
            else: continue

        from gql_query_builder import GqlQuery
        queries: list[str] = list()
        
        for repo in repositories:
            query = GqlQuery().fields(['...repoReleaseAssets']) \
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

        response = await self.client.post(f"{self.github}/graphql", json={"query": payload})
        if response.status_code == 401: delete_github_token(); raise tn.TryAgain
        if response.status_code != 200 and response.status_code != 504: return
        data = response.json()['data']      

        for meta, resource in self.queue:
            if not data.get(alias := pattern.sub('', meta['id']) if meta['id'] else "unknown"): continue
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
                slug   = meta['id'])
