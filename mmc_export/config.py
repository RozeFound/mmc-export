from pathlib import Path
from cryptography.fernet import Fernet

token = b'gAAAAABifAIMNFaSNF8epJIDWIv2nSe3zxARkMmViCa1ZCvtwoRqhuB1LYjjJsAstwTvP4dEOSm6Wj0SRDWr3PPwZz5eEBt_1fU8uIaninakGYFNSarEduD6YfoA-rm28qUQHYpVcuae3lj8sYrs_87P6F4s3gBrYg=='
key = b'ywE5qRot_nuWfLnbEXXcAPKaW10us3YpWEkDXgm9was='

CURSEFORGE_API_TOKEN = Fernet(key).decrypt(token).decode()
DEFAULT_CACHE_DIR = Path().home() / ".cache/mmc-export"
output_naming_scheme = "{abbr}_{name}"