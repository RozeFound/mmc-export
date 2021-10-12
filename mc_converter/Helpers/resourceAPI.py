from typing import Any
from pathlib import Path
from dataclasses import dataclass
from aiohttp import ClientSession

@dataclass
class Resource:

    "Represents downloadable item i.e. mod, resourcepack, shaderpack etc."

    resourceProvider: str # Can be modrinth or curseforge

    resourceName: str

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
                response.raise_for_status()
                if response.status == 200:
                    json = await response.json()
                    return await self._get_modrinth(json)

        murmur2_hash = get_hash(path, "murmur2")
        async with self.session.post("https://addons-ecs.forgesvc.net/api/v2/fingerprint", data = f"[{murmur2_hash}]") as response:
            response.raise_for_status()
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

            client = json['client_side']
            server = json['server_side']
            summary = "both"

            if client == "required": summary = "client"
            elif server == "required": summary = "server"

            resource = Resource(
                resourceProvider = "Modrinth",
                resourceName = name,
                resourceID = ID,
                fileID = fileID
            )

            resource.resourceSide(client, server, summary)
            file = resource.file(filename, url)
            file.hash(hash_type, hash)
            
            return resource

    async def _get_curseforge(self, json: dict[str, Any], hash: str | int) -> Resource:
  
        ID = json['id']
        fileID = json['file']['id']

        filename = json['file']['fileName']
        url = json['file']['downloadUrl']

        hash_type = "murmur2"
        hash = str(hash)

        async with self.session.get(f"https://addons-ecs.forgesvc.net/api/v2/addon/{ID}") as response:

            json = await response.json()

            name = json['name']

            resource = Resource(
                resourceProvider = "CurseForge",
                resourceName = name,
                resourceID = ID,
                fileID = fileID
            )

            resource.resourceSide("optional", "optional", "both")
            file = resource.file(filename, url)
            file.hash(hash_type, hash)

            return resource
            