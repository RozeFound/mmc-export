from pathlib import Path
from cryptography.fernet import Fernet
from os import environ

_token = b'gAAAAABifAIMNFaSNF8epJIDWIv2nSe3zxARkMmViCa1ZCvtwoRqhuB1LYjjJsAstwTvP4dEOSm6Wj0SRDWr3PPwZz5eEBt_1fU8uIaninakGYFNSarEduD6YfoA-rm28qUQHYpVcuae3lj8sYrs_87P6F4s3gBrYg=='
_key = b'ywE5qRot_nuWfLnbEXXcAPKaW10us3YpWEkDXgm9was='

CURSEFORGE_API_TOKEN = Fernet(_key).decrypt(_token).decode()
OAUTH_GITHUB_CLIENT_ID = "8011f22f502b091464de"

CACHE_HOME = environ.get("XDG_CACHE_HOME", Path().home() / ".cache")
DEFAULT_CACHE_DIR = Path(CACHE_HOME) / "mmc-export"

output_naming_scheme = "{abbr}_{name}"