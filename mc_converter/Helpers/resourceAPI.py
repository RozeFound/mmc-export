from pathlib import Path
from dataclasses import dataclass
from aiohttp import ClientSession

@dataclass
class Provider:
    
    ID: str | int
    fileID: str | int
    url: str

    slug: str
    author: str

    def to_dict(self):
        
        data = {
            "ID": self.ID,
            "fileID": self.fileID,
            "url": self.url,
            "slug": self.slug,
            "author": self.author
        }

        return data

@dataclass
class Side:
    
    client: str
    server: str
    summary: str

    def to_dict(self):
        
        data = {
            "client": self.client,
            "server": self.server,
            "summary": self.summary,
        }

        return data

@dataclass
class Resource:

    "Represents downloadable item i.e. mod, resourcepack, shaderpack etc."

    name: str
    filename: str

    side: dict[str, dict[str]]
    hashes: dict[str, str | int]
    downloads: dict[str, dict[str]]

class ResourceAPI(object):

    def __init__(self, session: ClientSession) -> None:

        self.session = session

        self.session.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) Gecko/20100101 Firefox/42.0"
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Content-Type"] = "application/json"

        super().__init__()
    
    async def get(self, path: Path) -> Resource | None:

        from .utils import get_hash

        murmur2_hash = get_hash(path, "murmur2")
        sha512_hash = get_hash(path, "sha512")
        sha1_hash = get_hash(path, "sha1")

        modrinth_links = [
            f"https://api.modrinth.com/api/v1/version_file/{sha512_hash}?algorithm=sha512",
            f"https://api.modrinth.com/api/v1/version_file/{sha1_hash}?algorithm=sha1"
        ]
        
        modrinth = None
        for url in modrinth_links:
            async with self.session.get(url) as response:
                if response.status == 200:
                    json = await response.json()
                    modrinth = await self._get_modrinth(json)
                    break

        curseforge = None
        async with self.session.post("https://addons-ecs.forgesvc.net/api/v2/fingerprint", data = f"[{murmur2_hash}]") as response:
            json = await response.json()
            if json['exactMatches']:
                curseforge = await self._get_curseforge(json['exactMatches'][0], murmur2_hash)

        if modrinth: 
            resource = modrinth
            if curseforge: 
                resource.downloads.update(curseforge.downloads)
                resource.hashes.update(curseforge.hashes)

        elif curseforge: resource = curseforge
        else: return

        return resource


    async def _get_modrinth(self, json: dict[str]) -> Resource:

        ID = json['mod_id']
        fileID = json['id']

        filename = json['files'][0]['filename']
        url = json['files'][0]['url']

        hashes = json['files'][0]['hashes']

        async with self.session.get(f"https://api.modrinth.com/api/v1/mod/{ID}") as response:

            json = await response.json()

            name = json['title']
            #author = json['author']
            slug = json['slug'] if 'slug' in json else name

            client = json['client_side']
            server = json['server_side']
            summary = "both"

            if client == "required": summary = "client"
            elif server == "required": summary = "server"

            resource = Resource (
                name = name,
                filename=filename,
                side=Side(client, server, summary).to_dict(),
                hashes=hashes,
                downloads={"Modrinth": Provider(ID, fileID, url, slug, "Unknown").to_dict()}
            )
            
            return resource

    async def _get_curseforge(self, json: dict[str], hash: str | int) -> Resource:
  
        ID = json['id']
        fileID = json['file']['id']

        filename = json['file']['fileName']
        url = json['file']['downloadUrl']

        async with self.session.get(f"https://addons-ecs.forgesvc.net/api/v2/addon/{ID}") as response:

            json = await response.json()

            name = json['name']
            author = json['authors'][0]['name']
            slug = json['slug'] if 'slug' in json else name

            resource = Resource (
                name = name,
                filename=filename,
                side=Side("optional", "optional", "both").to_dict(),
                hashes={"murmur2": hash},
                downloads={"CurseForge": Provider(ID, fileID, url, slug, author).to_dict()}
            )

            return resource
