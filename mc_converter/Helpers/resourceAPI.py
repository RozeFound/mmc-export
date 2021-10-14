from typing import Any
from pathlib import Path
from dataclasses import dataclass
from aiohttp import ClientSession

@dataclass
class Resource:

    "Represents downloadable item i.e. mod, resourcepack, shaderpack etc."

    resourceProvider: str # Can be modrinth or curseforge

    resourceName: str
    resourceSlug: str

    @dataclass
    class resourceSide: 
        client: str
        server: str
        summary: str

    resourceID: str
    fileID: str

    @dataclass
    class file:
        filename: str 
        url: str

        @dataclass
        class hash:
            type: str
            value: str | int

class ResourceAPI(object):

    def __init__(self, session: ClientSession) -> None:

        self.session = session

        self.session.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) Gecko/20100101 Firefox/42.0"
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Content-Type"] = "application/json"

        super().__init__()
    
    async def get(self, path: Path) -> Resource | None:

        from .utils import get_hash

        sha512_hash = get_hash(path, "sha512")
        sha1_hash = get_hash(path, "sha1")

        modrinth_links = [
            f"https://api.modrinth.com/api/v1/version_file/{sha512_hash}?algorithm=sha512",
            f"https://api.modrinth.com/api/v1/version_file/{sha1_hash}?algorithm=sha1"
        ]
        
        for url in modrinth_links:
            async with self.session.get(url) as response:
                if response.status == 200:
                    json = await response.json()
                    return await self._get_modrinth(json)

        murmur2_hash = get_hash(path, "murmur2")
        async with self.session.post("https://addons-ecs.forgesvc.net/api/v2/fingerprint", data = f"[{murmur2_hash}]") as response:
            json = await response.json()
            if json['exactMatches']:
                return await self._get_curseforge(json['exactMatches'][0], murmur2_hash)

        return

    async def _get_modrinth(self, json: dict[str, Any]) -> Resource:

        ID = json['mod_id']
        fileID = json['id']

        filename = json['files'][0]['filename']
        url = json['files'][0]['url']

        hash_type = "sha1"

        if("sha512" in json['files'][0]['hashes']):
            hash_type = "sha512"

        hash = json['files'][0]['hashes'][hash_type]

        async with self.session.get(f"https://api.modrinth.com/api/v1/mod/{ID}") as response:

            json = await response.json()

            name = json['title']
            slug = json['slug'] if 'slug' in json else name

            client = json['client_side']
            server = json['server_side']
            summary = "both"

            if client == "required": summary = "client"
            elif server == "required": summary = "server"

            resource = Resource(
                resourceProvider = "Modrinth",
                resourceName = name,
                resourceSlug=slug,
                resourceID = ID,
                fileID = fileID
            )

            resource.resourceSide = Resource.resourceSide(client, server, summary)
            resource.file = Resource.file(filename, url)
            resource.file.hash = Resource.file.hash(hash_type, hash)
            
            return resource

    async def _get_curseforge(self, json: dict[str, Any], hash: str | int) -> Resource:
  
        ID = json['id']
        fileID = json['file']['id']

        filename = json['file']['fileName']
        url = json['file']['downloadUrl']

        hash_type = "murmur2"
        hash = hash

        async with self.session.get(f"https://addons-ecs.forgesvc.net/api/v2/addon/{ID}") as response:

            json = await response.json()

            name = json['name']
            slug = json['slug'] if 'slug' in json else name

            resource = Resource(
                resourceProvider = "CurseForge",
                resourceName = name,
                resourceSlug=slug,
                resourceID = ID,
                fileID = fileID
            )

            resource.resourceSide = Resource.resourceSide("optional", "optional", "both")
            resource.file = Resource.file(filename, url)
            resource.file.hash = Resource.file.hash(hash_type, hash)

            return resource
            